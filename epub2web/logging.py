"""Persistent, structured run diagnostics for epub2web.

Every command gets a run id, a human-readable log, a JSONL event stream, and
optional JSON artifacts (fidelity and link reports). Logging failures must
never stop a build: if a log file cannot be written, the command continues
with console warnings.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import platform
import re
import shlex
import sys
import time
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

LOGGER_NAME = "epub2web"
_RESERVED = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}
DEFAULT_KEEP_RUNS = 20
MAX_LOG_BYTES = 5 * 1024 * 1024
MAX_LOG_BACKUPS = 5


def default_log_dir() -> Path:
    """Return the platform-friendly default log directory."""
    override = os.environ.get("EPUB2WEB_LOG_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".epub2web" / "logs"


def _short(value: Any, limit: int = 500) -> str:
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, ensure_ascii=False, default=str)
        except Exception:
            text = repr(value)
    text = text.replace("\n", "\\n")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-") or "artifact"


class _HumanFormatter(logging.Formatter):
    def __init__(self, *args, timestamps: bool = True, show_logger: bool = True, **kwargs):
        super().__init__(*args, **kwargs)
        self.timestamps = timestamps
        self.show_logger = show_logger

    def format(self, record: logging.LogRecord) -> str:
        parts = []
        if self.timestamps:
            parts.append(self.formatTime(record, self.datefmt))
        parts.append(f"{record.levelname:<7}")
        if self.show_logger:
            parts.append(f"{record.name}:")
        line = " ".join(parts) + " " + record.getMessage()
        extras = []
        for key, value in record.__dict__.items():
            if key in _RESERVED or key.startswith("_"):
                continue
            extras.append(f"{key}={_short(value)}")
        if extras:
            line += " " + " ".join(extras)
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


class _JsonFormatter(logging.Formatter):
    def __init__(self, run_id: str):
        super().__init__()
        self.run_id = run_id

    def format(self, record: logging.LogRecord) -> str:
        data: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "run_id": self.run_id,
        }
        for key, value in record.__dict__.items():
            if key in _RESERVED or key.startswith("_"):
                continue
            data[key] = value
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        try:
            return json.dumps(data, ensure_ascii=False, default=str)
        except Exception:
            return json.dumps(
                {
                    "ts": data["ts"],
                    "level": data["level"],
                    "logger": data["logger"],
                    "message": data["message"],
                    "run_id": self.run_id,
                    "serialization_error": True,
                }
            )


@dataclass
class LogSession:
    run_id: str
    logger: logging.Logger
    started: float
    path: Path | None = None
    jsonl_path: Path | None = None
    context: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, Path] = field(default_factory=dict)
    _handlers: list[logging.Handler] = field(default_factory=list)
    _closed: bool = False

    def debug(self, message: str, **fields: Any) -> None:
        self.logger.debug(message, extra=fields)

    def info(self, message: str, **fields: Any) -> None:
        self.logger.info(message, extra=fields)

    def warning(self, message: str, **fields: Any) -> None:
        self.logger.warning(message, extra=fields)

    def error(self, message: str, **fields: Any) -> None:
        self.logger.error(message, extra=fields)

    def exception(self, message: str, **fields: Any) -> None:
        self.logger.exception(message, extra=fields)

    def write_artifact(
        self,
        name: str,
        data: Any,
        *,
        filename: str | None = None,
    ) -> Path | None:
        if self.path is None:
            return None
        target = (
            self.path.parent / filename
            if filename
            else self.path.parent / f"{self.path.stem}-{_safe_name(name)}.json"
        )
        try:
            target.write_text(
                json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            self.warning("could not write log artifact", artifact=name, error=str(exc))
            return None
        self.artifacts[name] = target
        self.info("log artifact written", artifact=str(target))
        return target

    def flush(self) -> None:
        for handler in self._handlers:
            with contextlib.suppress(Exception):
                handler.flush()

    def current_log_lines(self) -> list[str]:
        """Return this run's section of the log, not older runs in a shared file."""
        if self.path is None or not self.path.exists():
            return []
        try:
            lines = self.path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return []
        marker = f"run_id={self.run_id}"
        start = 0
        for index, line in enumerate(lines):
            if "run started" in line and marker in line:
                start = index
        return lines[start:]

    def write_support_bundle(
        self,
        *,
        status: str,
        exit_code: int,
        error: str = "",
        report_dir: str | Path | None = None,
        filename: str | None = None,
    ) -> Path | None:
        """Create one ZIP that an end user can attach to a bug report."""
        self.flush()
        self.context.setdefault("run_id", self.run_id)
        self.context.setdefault("status", status)
        self.context.setdefault("exit_code", exit_code)
        self.context.setdefault("generated", datetime.now(timezone.utc).isoformat())
        if error:
            self.context["error"] = error

        directory = (
            Path(report_dir).expanduser()
            if report_dir
            else Path(os.environ.get("EPUB2WEB_REPORT_DIR", Path.cwd() / "epub2web-reports"))
        )
        if not directory.is_absolute():
            directory = Path.cwd() / directory
        directory = directory.resolve()
        target = directory / (
            filename or f"epub2web-report-{time.strftime('%Y%m%d-%H%M%S')}-{self.run_id}.zip"
        )

        environment = self.context.get("environment", {})
        command = environment.get("argv") if isinstance(environment, dict) else None
        if isinstance(command, list):
            command = shlex.join(str(part) for part in command)
        run_lines = self.current_log_lines()
        log_tail = "\n".join(run_lines[-120:]) if run_lines else "Log file unavailable."
        readme = f"""epub2web support report
=====================

Run ID:       {self.run_id}
Status:       {status}
Exit code:    {exit_code}
Generated:    {self.context["generated"]}
Command:      {command or "(unknown)"}
Working dir:  {environment.get("cwd", Path.cwd()) if isinstance(environment, dict) else Path.cwd()}
Python:       {environment.get("python", "unknown") if isinstance(environment, dict) else "unknown"}
Platform:     {environment.get("platform", "unknown") if isinstance(environment, dict) else "unknown"}

What to do
----------
Attach this ZIP file to the issue or message you send to the maintainer.
It contains the full run log, JSONL events, the run summary, and gate reports
when those gates ran. Do not paste individual files unless asked; the ZIP is
the report.

Privacy
-------
These diagnostics can contain local file paths, book metadata, and short
excerpts from failed text comparisons. Review the contents before sharing
them publicly.

Error
-----
{error or "(see the log and summary in this bundle)"}

Recent log
----------
{log_tail}
"""
        try:
            directory.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("README.txt", readme)
                archive.writestr(
                    "context.json",
                    json.dumps(self.context, ensure_ascii=False, indent=2, default=str) + "\n",
                )
                if run_lines:
                    archive.writestr("run.log", "\n".join(run_lines) + "\n")
                if self.jsonl_path is not None and self.jsonl_path.exists():
                    try:
                        events = self.jsonl_path.read_text(
                            encoding="utf-8", errors="replace"
                        ).splitlines()
                    except OSError:
                        events = []
                    current = (
                        [line for line in events if json.loads(line).get("run_id") == self.run_id]
                        if events
                        else []
                    )
                    if current or events:
                        archive.writestr("events.jsonl", "\n".join(current or events[-120:]) + "\n")
                for artifact_name, artifact_path in self.artifacts.items():
                    if artifact_path.exists():
                        archive.write(artifact_path, arcname=f"{_safe_name(artifact_name)}.json")
        except Exception as exc:
            print(f"warning: could not create support report: {exc}", file=sys.stderr)
            with contextlib.suppress(OSError):
                target.unlink(missing_ok=True)
            return None

        self.info("support report written", report=str(target))
        return target

    def finish(self, status: str, **fields: Any) -> None:
        fields.pop("duration_s", None)
        self.info(
            "run finished",
            status=status,
            duration_s=round(time.monotonic() - self.started, 3),
            **fields,
        )

    def close(self) -> None:
        if self._closed:
            return
        for handler in list(self._handlers):
            try:
                handler.flush()
                handler.close()
            finally:
                self.logger.removeHandler(handler)
        self._handlers.clear()
        self._closed = True


def _file_handler(path: Path, *, rotate: bool) -> logging.Handler:
    if rotate:
        return RotatingFileHandler(
            path,
            maxBytes=MAX_LOG_BYTES,
            backupCount=MAX_LOG_BACKUPS,
            encoding="utf-8",
        )
    return logging.FileHandler(path, encoding="utf-8")


def _prune_runs(directory: Path, keep: int) -> None:
    if keep <= 0:
        return

    def mtime(path: Path) -> float:
        try:
            return path.stat().st_mtime
        except OSError:
            return 0.0

    logs = sorted(directory.glob("epub2web-*.log"), key=mtime, reverse=True)
    for old in logs[keep:]:
        for target in (
            old,
            old.with_suffix(".jsonl"),
            *directory.glob(f"{old.stem}-*.json"),
        ):
            with contextlib.suppress(OSError):
                target.unlink(missing_ok=True)


def setup_logging(
    log_dir: str | Path | None = None,
    log_file: str | Path | None = None,
    *,
    filename: str | None = None,
    rotate: bool = False,
    keep: int | None = None,
    console_level: int = logging.CRITICAL,
) -> LogSession:
    """Configure the package logger and return this run's session."""
    run_id = uuid.uuid4().hex[:10]
    session = LogSession(
        run_id=run_id, logger=logging.getLogger(LOGGER_NAME), started=time.monotonic()
    )
    logger = session.logger
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    console = logging.StreamHandler(sys.stderr)
    console.setLevel(console_level)
    console.setFormatter(_HumanFormatter(timestamps=False, show_logger=False))
    logger.addHandler(console)
    session._handlers.append(console)

    directory = Path(log_dir).expanduser() if log_dir else default_log_dir()
    if log_file is not None:
        path = Path(log_file).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
    else:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        path = directory / (filename or f"epub2web-{stamp}-{run_id}.log")

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        human = _file_handler(path, rotate=rotate)
        human.setLevel(logging.DEBUG)
        human.setFormatter(_HumanFormatter())
        logger.addHandler(human)
        session._handlers.append(human)
        session.path = path

        jsonl_path = path.with_suffix(".jsonl")
        if jsonl_path == path:
            jsonl_path = path.with_name(path.name + ".jsonl")
        structured = _file_handler(jsonl_path, rotate=rotate)
        structured.setLevel(logging.DEBUG)
        structured.setFormatter(_JsonFormatter(run_id))
        logger.addHandler(structured)
        session._handlers.append(structured)
        session.jsonl_path = jsonl_path
    except OSError as exc:
        session.path = None
        session.jsonl_path = None
        print(f"warning: file logging disabled: {exc}", file=sys.stderr)

    if session.path is not None and not rotate and log_file is None:
        env_keep = os.environ.get("EPUB2WEB_LOG_KEEP")
        try:
            limit = int(env_keep) if env_keep else (keep or DEFAULT_KEEP_RUNS)
        except ValueError:
            limit = keep or DEFAULT_KEEP_RUNS
        _prune_runs(session.path.parent, limit)

    session.context.update({"run_id": run_id, "status": "running"})
    session.info(
        "run started",
        run_id=run_id,
        log_file=str(session.path) if session.path else None,
        jsonl_file=str(session.jsonl_path) if session.jsonl_path else None,
    )
    return session


def log_environment(session: LogSession, argv: list[str] | None = None, **fields: Any) -> None:
    """Log the runtime context that makes a failure reproducible."""
    environment = {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "cwd": str(Path.cwd()),
        "executable": sys.executable,
        "argv": argv if argv is not None else sys.argv,
        **fields,
    }
    session.context["environment"] = environment
    session.info("environment", **environment)


def log_path_for_user(session: LogSession) -> str | None:
    if session.path is None:
        return None
    try:
        return str(session.path.relative_to(Path.cwd()))
    except ValueError:
        return str(session.path)
