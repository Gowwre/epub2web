"""Run the DOET build pipeline with persistent, structured diagnostics."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from epub2web.logging import (  # noqa: E402
    log_environment,
    log_path_for_user,
    setup_logging,
)

LOG_DIR = ROOT / "logs"


class StageFailed(RuntimeError):
    def __init__(self, stage: str, code: int):
        super().__init__(f"stage {stage!r} failed with exit code {code}")
        self.stage = stage
        self.code = code


def executable_command(path: str | Path) -> list[str]:
    path = str(path)
    if os.name == "nt" and path.lower().endswith((".cmd", ".bat")):
        return ["cmd", "/c", path]
    return [path]


def pagefind_command() -> list[str]:
    local = ROOT / "node_modules" / ".bin" / ("pagefind.cmd" if os.name == "nt" else "pagefind")
    if local.exists():
        return executable_command(local)
    npx = shutil.which("npx")
    if npx is None:
        raise FileNotFoundError("Pagefind is not installed and npx is not available")
    return [*executable_command(npx), "pagefind"]


def plan_stages(only: str | None, links: bool, package: bool) -> list[tuple[str, list[str]]]:
    python = sys.executable
    stages: dict[str, tuple[str, list[str]]] = {
        "extract": ("extract", [python, "scripts/extract.py"]),
        "build": ("render", [python, "scripts/build.py"]),
        "search": (
            "search",
            [*pagefind_command(), "--site", "dist", "--output-subdir", "pagefind"],
        ),
        "verify": ("verify", [python, "scripts/verify.py"]),
        "links": ("links", [python, "scripts/check_links.py"]),
        "package": ("package", [python, "scripts/package_offline.py"]),
    }
    if only:
        return [stages[only]]
    order = ["extract", "build", "search", "verify"]
    if links:
        order.append("links")
    if package:
        order.append("package")
    return [stages[name] for name in order]


def run_stage(
    session,
    name: str,
    command: list[str],
    summary: dict,
) -> None:
    session.info("stage started", stage=name, command=shlex.join(command))
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    started = time.monotonic()
    lines = 0
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        bufsize=1,
    )
    assert process.stdout is not None
    for line in process.stdout:
        lines += 1
        print(line, end="", flush=True)
        session.info("stage output", stage=name, line=line.rstrip("\n"))
    code = process.wait()
    elapsed = round(time.monotonic() - started, 3)
    summary["stages"].append(
        {
            "name": name,
            "command": shlex.join(command),
            "exit": code,
            "duration_s": elapsed,
            "lines": lines,
        }
    )
    session.info("stage finished", stage=name, exit=code, duration_s=elapsed, lines=lines)
    if code != 0:
        raise StageFailed(name, code)


def write_fidelity_artifact(session, since: float) -> None:
    report = ROOT / "content" / "fidelity-report.json"
    if not report.exists():
        return
    try:
        if report.stat().st_mtime < since - 1:
            return
    except OSError:
        return
    try:
        data = json.loads(report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        session.warning("could not read fidelity report", error=str(exc))
        return
    session.write_artifact("fidelity", data, filename="fidelity-report.json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the DOET browser edition with logs.")
    parser.add_argument("--links", action="store_true", help="also run the internal link gate")
    parser.add_argument(
        "--package", action="store_true", help="also create the portable offline package"
    )
    parser.add_argument(
        "--only",
        choices=("extract", "build", "search", "verify", "links", "package"),
        help="run one stage against existing files",
    )
    args = parser.parse_args(argv)

    session = setup_logging(log_dir=LOG_DIR, filename="build.log", rotate=True)
    log_environment(
        session,
        argv=[sys.argv[0], *sys.argv[1:]] if argv is None else [sys.argv[0], *argv],
    )
    started = time.monotonic()
    stages: list[tuple[str, list[str]]] = []
    summary = {
        "status": "error",
        "exit_code": 2,
        "duration_s": 0,
        "site_url": os.environ.get("SITE_URL", "http://localhost:4321"),
        "stages": [],
        "log": str(session.path) if session.path else None,
        "jsonl": str(session.jsonl_path) if session.jsonl_path else None,
    }
    status = "error"
    exit_code = 2
    try:
        stages = plan_stages(args.only, args.links, args.package)
        session.info(
            "pipeline started",
            stages=[name for name, _ in stages],
            site_url=summary["site_url"],
            log=str(session.path) if session.path else None,
        )
        for name, command in stages:
            run_stage(session, name, command, summary)
        status = "ok"
        exit_code = 0
        print(f"\nBuild pipeline complete in {time.monotonic() - started:.2f}s.")
        return 0
    except StageFailed as exc:
        status = "failed"
        exit_code = 1
        session.error("stage failed", stage=exc.stage, exit=exc.code)
        print(f"\nBuild failed in stage {exc.stage!r} (exit {exc.code}).", file=sys.stderr)
        return 1
    except Exception as exc:
        status = "error"
        exit_code = 2
        session.exception("pipeline crashed", error=str(exc))
        print(f"\nBuild pipeline error: {exc}", file=sys.stderr)
        return 2
    finally:
        summary["status"] = status
        summary["exit_code"] = exit_code
        summary["duration_s"] = round(time.monotonic() - started, 3)
        write_fidelity_artifact(session, started)
        session.write_artifact("summary", summary, filename="build-summary.json")
        session.finish(status, exit_code=exit_code)
        log_path = log_path_for_user(session)
        if log_path:
            print(f"Log:     {log_path}", file=sys.stderr if exit_code else sys.stdout)
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
