"""Create a portable offline distribution of the built site.

The package contains:
  site/          the complete static build (including Pagefind)
  serve.py       a local-only HTTP server that opens the browser
  start.sh       Linux / generic launcher
  start.command  macOS double-click launcher
  start.bat      Windows launcher
  README.txt     recipient instructions

No hosting, no internet connection, no external services.
"""

from __future__ import annotations

import shutil
import stat
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
RELEASE = ROOT / "release"
PKG = RELEASE / "doet-browser-edition"
ZIP = RELEASE / "doet-browser-edition.zip"

SERVE_PY = r'''#!/usr/bin/env python3
"""Serve the bundled book on 127.0.0.1 and open a browser."""
from __future__ import annotations

import argparse
import http.server
import socket
import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "site"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(SITE), **kwargs)

    def log_message(self, fmt, *args):
        pass


def available_port(start: int) -> int:
    for port in range(start, start + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve the local browser edition.")
    parser.add_argument("--port", type=int, default=8000, help="port to try first (default: 8000)")
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser automatically")
    args = parser.parse_args()

    if not (SITE / "index.html").exists():
        print("The site/ folder is missing. Please unzip the whole package and try again.")
        return 1

    port = available_port(args.port)
    if port == 0:
        print("Could not find a free local port.")
        return 1

    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print()
    print("  The Design of Everyday Things — local browser edition")
    print("  " + "-" * 54)
    print(f"  Open: {url}")
    print("  The server listens on this computer only (127.0.0.1).")
    print("  Press Ctrl+C to stop.")
    print()
    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

START_SH = """#!/usr/bin/env sh
cd "$(dirname "$0")"
exec python3 serve.py "$@"
"""

START_COMMAND = """#!/bin/sh
cd "$(dirname "$0")"
python3 serve.py "$@"
"""

START_BAT = """@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 serve.py %*
) else (
  python serve.py %*
)
if errorlevel 1 pause
"""

README = """The Design of Everyday Things — local browser edition
======================================================

This package contains the complete browser edition. It runs entirely on
your computer; it does not need the internet or a web server.

HOW TO OPEN IT
--------------

macOS:
  Double-click "start.command".
  If macOS refuses to open it, right-click it and choose Open, or run:
      bash start.command

Windows:
  Double-click "start.bat".
  Requires Python 3: https://www.python.org/downloads/
  (During installation, tick "Add Python to PATH".)

Linux:
  Double-click / run "start.sh", or:
      ./start.sh
  If needed: chmod +x start.sh

The browser opens at http://127.0.0.1:8000/ and the local server keeps
running in a small terminal window. Press Ctrl+C there to stop it.

Do NOT open site/index.html directly. The edition uses root-relative
links and a static search index, so it needs the tiny local server. The
server listens on 127.0.0.1 only; it is not reachable from the network.

WHAT IS INCLUDED
----------------

site/          the complete static site: chapters, figures, notes,
               references, index, search index, fonts, and images
serve.py       the local-only server
start.*        one-click launchers for each platform
README.txt     this file

RIGHTS
------

The text is (c) 2013 Don Norman, published by Basic Books. This local
edition is intended for personal reading. Do not publish or redistribute
the book without permission from the rights holder.
"""


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def executable(path: Path) -> None:
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def main() -> None:
    if not (DIST / "index.html").exists():
        raise SystemExit("dist/index.html not found. Run `npm run build` first.")

    if RELEASE.exists():
        shutil.rmtree(RELEASE)
    PKG.mkdir(parents=True)

    shutil.copytree(DIST, PKG / "site")
    write_text(PKG / "serve.py", SERVE_PY)
    write_text(PKG / "start.sh", START_SH)
    write_text(PKG / "start.command", START_COMMAND)
    write_text(PKG / "start.bat", START_BAT.replace("\n", "\r\n"))
    write_text(PKG / "README.txt", README)
    executable(PKG / "serve.py")
    executable(PKG / "start.sh")
    executable(PKG / "start.command")

    with zipfile.ZipFile(ZIP, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(PKG.rglob("*")):
            if path.is_dir():
                continue
            arcname = Path("doet-browser-edition") / path.relative_to(PKG)
            info = zipfile.ZipInfo.from_file(path, str(arcname))
            info.compress_type = zipfile.ZIP_DEFLATED
            mode = 0o755 if path.name in ("serve.py", "start.sh", "start.command") else 0o644
            info.external_attr = (mode & 0xFFFF) << 16
            with path.open("rb") as fh:
                zf.writestr(info, fh.read())

    size_mb = ZIP.stat().st_size / (1024 * 1024)
    print(f"Created {ZIP} ({size_mb:.1f} MB)")
    print(f"  folder: {PKG}")
    print("  recipients: unzip, then run start.command / start.bat / start.sh")


if __name__ == "__main__":
    main()
