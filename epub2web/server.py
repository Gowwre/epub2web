"""Serve a generated site on localhost for preview."""

from __future__ import annotations

import http.server
import logging
import threading
import webbrowser
from functools import partial
from pathlib import Path
from typing import ClassVar
from urllib.parse import quote

logger = logging.getLogger(__name__)


def _make_server(handler, port: int) -> http.server.ThreadingHTTPServer:
    candidates = [0] if port == 0 else range(port, min(port + 50, 65536))
    error: OSError | None = None
    for candidate in candidates:
        try:
            return http.server.ThreadingHTTPServer(("127.0.0.1", candidate), handler)
        except OSError as exc:
            error = exc
    raise OSError(f"could not bind a preview server on port {port}") from error


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
    base_url = quote(base_path, safe="/%")

    class Handler(http.server.SimpleHTTPRequestHandler):
        extensions_map: ClassVar[dict[str, str]] = {
            **http.server.SimpleHTTPRequestHandler.extensions_map,
            ".woff2": "font/woff2",
            ".woff": "font/woff",
            ".webp": "image/webp",
            ".avif": "image/avif",
            ".svg": "image/svg+xml",
        }

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
            if path == base_url:
                self.send_response(301)
                self.send_header("Location", base_url + "/")
                self.end_headers()
                return False
            if path in ("", "/") or path.startswith("/?"):
                self.send_response(302)
                self.send_header("Location", base_url + "/")
                self.end_headers()
                return False
            if not (path.startswith(base_url + "/") or path.startswith(base_url + "?")):
                self.send_error(404, f"Not found under {base_url}")
                return False
            self.path = path[len(base_url) :] or "/"
            return True

    handler = partial(Handler, directory=str(directory))
    server = _make_server(handler, port)
    url = f"http://127.0.0.1:{server.server_address[1]}{base_url}/"

    logger.info(
        "preview server started",
        extra={"url": url, "directory": str(directory), "base_path": base_path},
    )
    print()
    print("  epub2web preview")
    print("  " + "-" * 40)
    print(f"  {url}")
    print("  Listening on this computer only (127.0.0.1).")
    print("  Press Ctrl+C to stop.")
    print()
    if open_browser:
        timer = threading.Timer(0.4, lambda: webbrowser.open(url))
        timer.daemon = True
        timer.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
