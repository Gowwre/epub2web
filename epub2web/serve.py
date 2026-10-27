"""Local preview server for generated sites.

The preview is intentionally small: serve the static site on loopback, open a
browser, and stay out of the way. The site is generated output, so a reader
should never have to know how to run or stop an HTTP server separately.
"""

from __future__ import annotations

import contextlib
import functools
import http.server
import sys
import threading
import webbrowser
from pathlib import Path

DEFAULT_PORT = 8000
PORT_ATTEMPTS = 50


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    """Serve files without filling the terminal with request logs."""

    def log_message(self, format: str, *args: object) -> None:
        pass

    def end_headers(self) -> None:
        # A rebuild should be visible immediately; local previews are cheap.
        self.send_header("Cache-Control", "no-store, max-age=0")
        super().end_headers()


def _create_server(directory: Path, port: int) -> http.server.ThreadingHTTPServer:
    handler = functools.partial(_QuietHandler, directory=str(directory))
    last_error: OSError | None = None
    last_port = min(port + PORT_ATTEMPTS - 1, 65535)
    for candidate in range(port, last_port + 1):
        try:
            return http.server.ThreadingHTTPServer(("127.0.0.1", candidate), handler)
        except OSError as exc:
            last_error = exc
    raise OSError(f"no free local port between {port} and {last_port}") from last_error


def _open_browser(url: str) -> None:
    with contextlib.suppress(Exception):
        webbrowser.open(url, new=2)


def serve_site(
    site: Path,
    *,
    title: str = "",
    port: int = DEFAULT_PORT,
    open_browser: bool = True,
) -> int:
    """Serve *site* on loopback until the reader presses Ctrl+C."""
    site = site.expanduser().resolve()
    if not (site / "index.html").is_file():
        print(f"Could not preview the site: {site / 'index.html'} is missing.", file=sys.stderr)
        return 1

    try:
        server = _create_server(site, port)
    except OSError as exc:
        print(f"Could not start the preview server: {exc}", file=sys.stderr)
        print(f"The site is still saved here: {site}", file=sys.stderr)
        return 1

    actual_port = server.server_address[1]
    url = f"http://127.0.0.1:{actual_port}/"
    print()
    print(f"  {title or 'Your book is ready'}")
    print("  " + "-" * min(max(len(title) + 2, 30), 64))
    print(f"  Open:   {url}")
    print("  This preview is available only on this computer.")
    print(f"  Saved:  {site}")
    print("  Press Ctrl+C to stop the preview. The site stays saved.")

    if open_browser:
        threading.Thread(target=_open_browser, args=(url,), daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nPreview stopped. Your site is still saved on disk.")
    finally:
        server.server_close()
    return 0
