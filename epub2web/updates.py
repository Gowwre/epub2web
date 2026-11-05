"""Best-effort update checks for the desktop GUI.

The converter itself never uses the network. The GUI checks GitHub Releases
shortly after launch and then periodically while it stays open, so it can offer
a newer desktop build; failures are ignored and book builds continue to work
offline.
"""

from __future__ import annotations

import http.client
import json
import re
import ssl
import urllib.request
from dataclasses import dataclass

import certifi

from . import __version__

GITHUB_REPO = "Gowwre/epub2web"
GITHUB_URL = f"https://github.com/{GITHUB_REPO}"
LATEST_RELEASE_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
DOWNLOAD_URL = "https://gowwre.github.io/epub2web/download/"
USER_AGENT = f"epub2web/{__version__} ({GITHUB_URL})"
MAX_RESPONSE_BYTES = 512 * 1024
DEFAULT_TIMEOUT = 7.0
_VERSION_RE = re.compile(r"^[vV]?(\d+(?:\.\d+)*)$")


@dataclass(frozen=True)
class ReleaseInfo:
    """A published release worth offering to the user."""

    version: str
    notes: str


def _ssl_context() -> ssl.SSLContext | None:
    """Return a TLS context with certifi's Mozilla CA bundle.

    Frozen builds bundle the OpenSSL libraries from the build machine, whose
    compiled-in default certificate directory may not exist on the user's
    distribution. certifi keeps public certificate roots available regardless
    of the host's OpenSSL configuration.
    """
    try:
        context = ssl.create_default_context()
        context.load_verify_locations(cafile=certifi.where())
    except (OSError, ssl.SSLError):
        return None
    return context


def _version_parts(value: str) -> tuple[int, ...] | None:
    match = _VERSION_RE.match(value.strip())
    if match is None:
        return None
    parts = tuple(int(part) for part in match.group(1).split("."))
    while len(parts) > 1 and parts[-1] == 0:
        parts = parts[:-1]
    return parts


def is_newer(latest: str, current: str = __version__) -> bool:
    """Return whether *latest* is a stable version newer than *current*."""
    latest_parts = _version_parts(latest)
    current_parts = _version_parts(current)
    if latest_parts is None or current_parts is None:
        return False
    return latest_parts > current_parts


def fetch_latest_release(timeout: float = DEFAULT_TIMEOUT) -> ReleaseInfo | None:
    """Return the latest stable GitHub release, or None when unavailable.

    This is intentionally silent: offline machines, rate limits, malformed
    responses, and API changes must never interrupt the application.
    """
    request = urllib.request.Request(
        LATEST_RELEASE_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=_ssl_context()) as response:
            payload = response.read(MAX_RESPONSE_BYTES + 1)
    except (OSError, ValueError, http.client.HTTPException):
        return None
    if len(payload) > MAX_RESPONSE_BYTES:
        return None
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    tag = data.get("tag_name")
    if not isinstance(tag, str):
        return None
    match = _VERSION_RE.match(tag.strip())
    if match is None:
        return None
    notes = data.get("body")
    return ReleaseInfo(
        version=match.group(1),
        notes=notes if isinstance(notes, str) else "",
    )
