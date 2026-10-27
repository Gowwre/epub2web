"""Internal worker process used by the desktop GUI.

This module stays free of GUI imports so it can run in a frozen app, on a
headless machine, or from the command line for diagnostics.
"""

from __future__ import annotations

import io
import os
import sys

from .cli import main as cli_main


def _ensure_standard_streams() -> None:
    """Restore stdout/stderr in a windowed PyInstaller worker.

    PyInstaller's windowed mode can set ``sys.stdout`` and ``sys.stderr`` to
    ``None``. The GUI launches the worker with pipes, so the underlying file
    descriptors are still valid; attach text streams to them so the CLI can
    report progress back to the controller.
    """
    if sys.stdout is None:
        try:
            sys.stdout = os.fdopen(
                1,
                "w",
                encoding="utf-8",
                errors="replace",
                buffering=1,
                closefd=False,
            )
        except OSError:
            sys.stdout = io.StringIO()
    if sys.stderr is None:
        try:
            sys.stderr = os.fdopen(
                2,
                "w",
                encoding="utf-8",
                errors="replace",
                buffering=1,
                closefd=False,
            )
        except OSError:
            sys.stderr = sys.stdout


def main(argv: list[str] | None = None) -> int:
    _ensure_standard_streams()
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "--worker":
        args = args[1:]
    return cli_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
