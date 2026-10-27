"""Launcher for the epub2web desktop GUI.

The Tkinter implementation lives in :mod:`epub2web.tk_app`. Keeping it out of
this module means a frozen app can handle its hidden ``--worker`` mode without
loading a GUI toolkit, and the worker can run in environments without Tk.
"""

from __future__ import annotations

import sys

TK_HELP = """\
The epub2web desktop GUI needs Tkinter, which is not available in this Python.

Linux:  install the Tk package for your distribution, for example:
        sudo apt install python3-tk
macOS/Windows:
        use a python.org Python installer or a distribution that includes Tk.

The command-line version still works: epub2web book.epub --serve
"""


def _print_error(text: str) -> None:
    stream = sys.stderr or sys.__stderr__
    if stream is not None:
        print(text, file=stream)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)

    # A frozen desktop app cannot be started with `python -m epub2web`; the
    # controller spawns the same executable with this hidden flag instead.
    if args and args[0] == "--worker":
        from .worker import main as worker_main

        return worker_main(args[1:])

    try:
        from .tk_app import run
    except ImportError as exc:
        _print_error(TK_HELP)
        _print_error(f"Details: {exc}")
        return 2

    return run()


if __name__ == "__main__":
    raise SystemExit(main())
