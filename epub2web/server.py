"""Serve a generated site on localhost for preview."""

from __future__ import annotations

import http.server
import socket
import threading
import webbrowser
from functools import partial
from pathlib import Path


def _available_port(start: int) -> int:
    if start == 0:
        return 0
    for port in range(start, start + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    return 0


def serve_directory(
    directory: str | Path,
    port: int = 8000,
    open_browser: bool = True,
    base_path: str = "",
) -> None:
    """Serve *directory* on 127.0.0.1 and block until Ctrl+C."""
    directory = Path(directory).resolve()
    if not (directory / "index.html").exists():
        raise FileNotFoundError(f"no index.html in {directory}")
    base_path = "" if not base_path or base_path.strip("/") == "" else "/" + base_path.strip("/")

    class Handler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self) -> None:
            if self._apply_base():
                super().do_GET()

        def do_HEAD(self) -> None:
            if self._apply_base():
                super().do_HEAD()

        def _apply_base(self) -> bool:
            if not base_path:
                return True
            path = self.path
            if path == base_path:
                self.send_response(301)
                self.send_header("Location", base_path + "/")
                self.end_headers()
                return False
            if path in ("", "/") or path.startswith("/?"):
                self.send_response(302)
                self.send_header("Location", base_path + "/")
                self.end_headers()
                return False
            if not (path.startswith(base_path + "/") or path.startswith(base_path + "?")):
                self.send_error(404, f"Not found under {base_path}")
                return False
            self.path = path[len(base_path) :] or "/"
            return True

    chosen = _available_port(port)
    handler = partial(Handler, directory=str(directory))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", chosen), handler)
    url = f"http://127.0.0.1:{server.server_address[1]}{base_path}/"

    print()
    print("  epub2web preview")
    print("  " + "-" * 40)
    print(f"  {url}")
    print("  Listening on this computer only (127.0.0.1).")
    print("  Press Ctrl+C to stop.")
    print()
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
