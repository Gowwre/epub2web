"""Toolkit-independent build controller for the desktop GUI.

The GUI never imports the converter directly. It starts a worker process and
consumes a small stream of events. That keeps the Tkinter layer replaceable
with another toolkit, or with a future in-process build API, without changing
the process lifecycle.

The controller deliberately uses the same CLI entry point as end users. A
packaged desktop app cannot use ``sys.executable -m epub2web`` (in a frozen
app, ``sys.executable`` is the app itself), so the worker command switches to
the app's hidden ``--worker`` mode when ``sys.frozen`` is set.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import re
import signal
import subprocess
import sys
import threading
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from .progress import PROGRESS_PREFIX

logger = logging.getLogger(__name__)

PREVIEW_URL_RE = re.compile(r"^https?://(?:127\.0\.0\.1|localhost):\d+(?:/\S*)?$")
SITE_RE = re.compile(r"^Site:\s+(.+)$")
REPORT_RE = re.compile(r"^Report:\s+(.+)$")
LOG_RE = re.compile(r"^Log:\s+(.+)$")
VERIFY_RE = re.compile(r"^Verify:\s+(PASS|FAIL)\b")
LINKS_RE = re.compile(r"^Links:\s+(PASS|FAIL)\b")
ERROR_RE = re.compile(r"^(?:epub2web:\s*)?error:\s*(.+)$")
PAGES_RE = re.compile(r"^Pages:\s+(\d+)$")
WORDS_RE = re.compile(r"^Words:\s+([\d,]+)$")
TIME_RE = re.compile(r"^Time:\s+([\d.]+)s$")
FOLDER_UNSAFE_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class BuildState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    STOPPED = "stopped"


@dataclass(frozen=True)
class BuildEvent:
    """One message from the worker process."""

    kind: str
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)


def documents_dir() -> Path:
    """Return the user's Documents folder, or home if it does not exist."""
    documents = Path.home() / "Documents"
    return documents if documents.is_dir() else Path.home()


def default_output_dir(epub: str | Path, *, title: str = "") -> Path:
    """Choose a stable, user-visible destination for a book's site."""
    name = (title or Path(epub).stem).strip()
    name = unicodedata.normalize("NFC", name)
    name = FOLDER_UNSAFE_RE.sub("-", name)
    name = re.sub(r"\s+", " ", name)
    name = re.sub(r"-{2,}", "-", name).strip(" .-")
    if not name:
        name = "book"
    name = name[:80].rstrip(" .-") or "book"
    return documents_dir() / "epub2web" / f"{name}-site"


def app_data_dir() -> Path:
    """Return a platform-appropriate directory for logs and support reports."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        root = Path(base).expanduser() if base else Path.home() / "AppData" / "Local"
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        base = os.environ.get("XDG_DATA_HOME")
        root = Path(base).expanduser() if base else Path.home() / ".local" / "share"
    return root / "epub2web"


def default_log_dir() -> Path:
    return app_data_dir() / "logs"


def default_report_dir() -> Path:
    return app_data_dir() / "reports"


def worker_command(
    epub: str | Path,
    output: str | Path,
    *,
    serve: bool = True,
    port: int = 0,
    open_browser: bool = True,
    log_dir: str | Path | None = None,
    report_dir: str | Path | None = None,
    progress: bool = True,
) -> list[str]:
    """Build the command that converts a book in a separate process."""
    python = sys.executable or ("python.exe" if os.name == "nt" else "python3")
    if getattr(sys, "frozen", False):
        command = [python, "--worker"]
    else:
        command = [python, "-m", "epub2web.worker"]

    command.extend([str(Path(epub).expanduser()), "-o", str(Path(output).expanduser())])
    if log_dir is not None:
        command.extend(["--log-dir", str(Path(log_dir).expanduser())])
    if report_dir is not None:
        command.extend(["--report-dir", str(Path(report_dir).expanduser())])
    if progress:
        command.append("--progress")
    if serve:
        command.extend(["--serve", "--port", str(port)])
        if not open_browser:
            command.append("--no-browser")
    return command


def _child_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["PYTHONUNBUFFERED"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["PYTHONUTF8"] = "1"
    if not getattr(sys, "frozen", False):
        # The GUI can be run straight from a checkout without being installed.
        # The worker runs from the output folder, so make the package root
        # importable for `python -m epub2web.worker`.
        package_root = str(Path(__file__).resolve().parent.parent)
        existing = environment.get("PYTHONPATH")
        environment["PYTHONPATH"] = (
            os.pathsep.join([package_root, existing]) if existing else package_root
        )
    return environment


def _hidden_window_kwargs() -> dict[str, Any]:
    """Keep a Windows GUI from flashing a console window for its worker."""
    if os.name != "nt":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    kwargs: dict[str, Any] = {"startupinfo": startupinfo}
    create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if create_no_window:
        kwargs["creationflags"] = create_no_window
    return kwargs


class BuildController:
    """Run one conversion worker and publish parsed progress events.

    ``on_event`` is called from the worker-reader thread. A GUI should hand
    events to its own main-thread queue instead of touching widgets directly.
    """

    def __init__(
        self,
        on_event: Callable[[BuildEvent], None] | None = None,
        *,
        serve: bool = True,
        port: int = 0,
        open_browser: bool = True,
        log_dir: str | Path | None = None,
        report_dir: str | Path | None = None,
    ) -> None:
        self.on_event = on_event
        self.serve = serve
        self.port = port
        self.open_browser = open_browser
        self.log_dir = (
            Path(log_dir).expanduser().resolve() if log_dir is not None else default_log_dir()
        )
        self.report_dir = (
            Path(report_dir).expanduser().resolve()
            if report_dir is not None
            else default_report_dir()
        )
        self._lock = threading.Lock()
        self._proc: subprocess.Popen[str] | None = None
        self._thread: threading.Thread | None = None
        self._state = BuildState.IDLE
        self._stop_requested = False
        self._preview_url: str | None = None
        self._site_path: Path | None = None
        self._report_path: Path | None = None
        self._log_path: Path | None = None
        self._error = ""
        self._verify_ok: bool | None = None
        self._links_ok: bool | None = None
        self._pages: int | None = None
        self._words: int | None = None
        self._elapsed: float | None = None
        self._success_emitted = False
        self._command: list[str] = []

    @property
    def state(self) -> BuildState:
        return self._state

    @property
    def command(self) -> list[str]:
        return list(self._command)

    @property
    def preview_url(self) -> str | None:
        return self._preview_url

    @property
    def site_path(self) -> Path | None:
        return self._site_path

    @property
    def report_path(self) -> Path | None:
        return self._report_path

    @property
    def log_path(self) -> Path | None:
        return self._log_path

    @property
    def is_running(self) -> bool:
        proc = self._proc
        return proc is not None and proc.poll() is None

    def start(self, epub: str | Path, output: str | Path) -> None:
        """Start converting *epub* into *output*."""
        with self._lock:
            if self.is_running:
                raise RuntimeError("a conversion is already running")
            epub_path = Path(epub).expanduser().resolve()
            output_path = Path(output).expanduser().resolve()
            if not epub_path.is_file():
                raise FileNotFoundError(f"EPUB not found: {epub_path}")

            output_path.parent.mkdir(parents=True, exist_ok=True)
            self.log_dir.mkdir(parents=True, exist_ok=True)
            self.report_dir.mkdir(parents=True, exist_ok=True)
            self._reset()

            command = worker_command(
                epub_path,
                output_path,
                serve=self.serve,
                port=self.port,
                open_browser=self.open_browser,
                log_dir=self.log_dir,
                report_dir=self.report_dir,
            )
            self._command = command
            try:
                proc = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    cwd=str(output_path.parent),
                    env=_child_environment(),
                    **_hidden_window_kwargs(),
                )
            except Exception:
                self._state = BuildState.FAILED
                raise
            self._proc = proc
            self._state = BuildState.RUNNING
            self._thread = threading.Thread(
                target=self._read_output,
                name="epub2web-worker",
                daemon=True,
            )

        # Start the reader and call the callback outside the lock so a callback
        # is free to stop or inspect the controller.
        assert self._thread is not None
        self._thread.start()

    def stop(self, timeout: float = 8.0) -> None:
        """Terminate a running build or preview, then wait for its reader."""
        with self._lock:
            proc = self._proc
            thread = self._thread
            if proc is None:
                return
            if proc.poll() is None:
                self._stop_requested = True

        if proc.poll() is None:
            # On POSIX, SIGINT lets the CLI run its own cleanup and remove
            # staging directories. Windows falls back to a hard terminate.
            with contextlib.suppress(OSError):
                if os.name == "nt":
                    proc.terminate()
                else:
                    proc.send_signal(signal.SIGINT)
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                with contextlib.suppress(OSError):
                    proc.terminate()
                with contextlib.suppress(subprocess.TimeoutExpired):
                    proc.wait(timeout=5)
                if proc.poll() is None:
                    with contextlib.suppress(OSError):
                        proc.kill()
                    with contextlib.suppress(subprocess.TimeoutExpired):
                        proc.wait(timeout=5)
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=timeout)

    def wait(self, timeout: float | None = None) -> int | None:
        """Wait for the worker to finish and return its exit code."""
        thread = self._thread
        if thread is not None:
            thread.join(timeout)
        proc = self._proc
        return proc.returncode if proc is not None else None

    # -- worker output ----------------------------------------------------
    def _read_output(self) -> None:
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        try:
            for raw in proc.stdout:
                self._handle_line(raw)
        except Exception as exc:  # pragma: no cover - defensive against pipe errors
            logger.exception("could not read converter output")
            self._error = self._error or f"Could not read converter output: {exc}"
        finally:
            try:
                code = proc.wait()
            except Exception:  # pragma: no cover - defensive
                code = -1
            self._finish(code)

    def _handle_line(self, raw: str) -> None:
        text = raw.rstrip("\r\n").strip()
        if not text:
            return
        if text.startswith(PROGRESS_PREFIX):
            try:
                payload = json.loads(text[len(PROGRESS_PREFIX) :])
            except (TypeError, ValueError):
                self._emit(BuildEvent("log", text))
                return
            if isinstance(payload, dict):
                self._emit(BuildEvent("progress", data=payload))
            return
        self._emit(BuildEvent("log", text))

        match = REPORT_RE.match(text)
        if match:
            self._report_path = self._path_from_output(match.group(1))
            self._emit(BuildEvent("report", data={"report": str(self._report_path)}))
            return

        match = LOG_RE.match(text)
        if match:
            self._log_path = self._path_from_output(match.group(1))
            return

        match = SITE_RE.match(text)
        if match:
            self._site_path = self._path_from_output(match.group(1))
            self._emit(BuildEvent("site", data={"site": str(self._site_path)}))
            return

        match = VERIFY_RE.match(text)
        if match:
            self._verify_ok = match.group(1) == "PASS"
            if not self._verify_ok and not self._error:
                self._error = "Build rejected by the fidelity gate."
            return

        match = LINKS_RE.match(text)
        if match:
            self._links_ok = match.group(1) == "PASS"
            if not self._links_ok and not self._error:
                self._error = "Build rejected by the internal-link gate."
            return

        match = ERROR_RE.match(text)
        if match:
            self._error = match.group(1).strip()
            return

        match = PAGES_RE.match(text)
        if match:
            self._pages = int(match.group(1))
            return

        match = WORDS_RE.match(text)
        if match:
            self._words = int(match.group(1).replace(",", ""))
            return

        match = TIME_RE.match(text)
        if match:
            self._elapsed = float(match.group(1))
            return

        if PREVIEW_URL_RE.match(text) and not self._preview_url:
            self._preview_url = text
            self._state = BuildState.SUCCEEDED
            self._success_emitted = True
            data = self._summary_data()
            self._emit(BuildEvent("preview", text, data))
            self._emit(BuildEvent("success", "Preview running.", data))

    def _finish(self, code: int) -> None:
        with self._lock:
            stop_requested = self._stop_requested
            success_emitted = self._success_emitted

        if stop_requested:
            self._state = BuildState.STOPPED
            self._emit(BuildEvent("stopped", "Stopped.", self._summary_data()))
            return

        if code == 0:
            if success_emitted:
                # With --serve, a clean exit means the preview server was
                # stopped by someone else (for example, Ctrl+C in a terminal).
                self._state = BuildState.STOPPED
                self._emit(BuildEvent("stopped", "Preview server stopped.", self._summary_data()))
            else:
                self._state = BuildState.SUCCEEDED
                self._success_emitted = True
                self._emit(BuildEvent("success", "Conversion complete.", self._summary_data()))
            return

        self._state = BuildState.FAILED
        reasons = []
        if self._verify_ok is False:
            reasons.append("fidelity")
        if self._links_ok is False:
            reasons.append("internal-link")
        if reasons:
            gate = " and ".join(reasons)
            message = f"Build rejected by the {gate} gate" + ("s" if len(reasons) > 1 else "") + "."
        else:
            message = self._error or f"Conversion failed (exit code {code})."
        data = {**self._summary_data(), "exit_code": code}
        self._emit(BuildEvent("failure", message, data))

    def _summary_data(self) -> dict[str, Any]:
        return {
            "url": self._preview_url or "",
            "site": str(self._site_path) if self._site_path else "",
            "report": str(self._report_path) if self._report_path else "",
            "log": str(self._log_path) if self._log_path else "",
            "pages": self._pages,
            "words": self._words,
            "elapsed": self._elapsed,
            "verify": self._verify_ok,
            "links": self._links_ok,
        }

    @staticmethod
    def _path_from_output(value: str) -> Path:
        path = Path(value.strip())
        if not path.is_absolute():
            path = Path.home() / path
        return path

    def _reset(self) -> None:
        self._proc = None
        self._thread = None
        self._state = BuildState.IDLE
        self._stop_requested = False
        self._preview_url = None
        self._site_path = None
        self._report_path = None
        self._log_path = None
        self._error = ""
        self._verify_ok = None
        self._links_ok = None
        self._pages = None
        self._words = None
        self._elapsed = None
        self._success_emitted = False
        self._command = []

    def _emit(self, event: BuildEvent) -> None:
        callback = self.on_event
        if callback is None:
            return
        try:
            callback(event)
        except Exception:  # pragma: no cover - a broken view must not kill the worker reader
            logger.exception("GUI event callback failed")
