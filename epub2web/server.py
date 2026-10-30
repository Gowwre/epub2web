"""Serve a generated site on localhost for preview."""

from __future__ import annotations

import http.server
import logging
import threading
import webbrowser
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import ClassVar
from urllib.parse import quote

from .paths import normalize_base_path

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
    on_ready: Callable[[str], None] | None = None,
) -> None:
    """Serve *directory* on 127.0.0.1 and block until Ctrl+C.

    ``on_ready`` is called with the final URL as soon as the server is bound,
    before ``serve_forever`` blocks. The desktop app uses it to report the
    preview URL over its structured event stream instead of relying on the
    printed banner, which can sit in a buffered pipe in frozen builds.
    """
    directory = Path(directory).resolve()
    if not (directory / "index.html").exists():
        raise FileNotFoundError(f"no index.html in {directory}")
    base_path = normalize_base_path(base_path)
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

    try:
        if on_ready is not None:
            on_ready(url)
        logger.info(
            "preview server started",
            extra={"url": url, "directory": str(directory), "base_path": base_path},
        )
        print(flush=True)
        print("  epub2web preview", flush=True)
        print("  " + "-" * 40, flush=True)
        print(f"  {url}", flush=True)
        print("  Listening on this computer only (127.0.0.1).", flush=True)
        print("  Press Ctrl+C to stop.", flush=True)
        print(flush=True)
        if open_browser:
            timer = threading.Timer(0.4, lambda: webbrowser.open(url))
            timer.daemon = True
            timer.start()
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.", flush=True)
    finally:
        server.server_close()
