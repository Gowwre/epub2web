"""Shared path helpers for generated site routes and platform data folders."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def app_data_dir() -> Path:
    """Return the platform-appropriate per-user data directory for epub2web.

    Linux follows ``XDG_DATA_HOME`` (default ``~/.local/share``), macOS uses
    ``~/Library/Application Support``, and Windows uses ``LOCALAPPDATA`` with
    ``APPDATA`` as a fallback. Tests and portable setups can override the
    result by setting the relevant environment variable.
    """
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        root = Path(base).expanduser() if base else Path.home() / "AppData" / "Local"
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        base = os.environ.get("XDG_DATA_HOME")
        root = Path(base).expanduser() if base else Path.home() / ".local" / "share"
    return root / "epub2web"


def route_to_file(dist: Path, route: str) -> Path:
    """Map a site route such as ``/read/1/`` to its index file."""
    if route == "/":
        return dist / "index.html"
    return dist / route.strip("/") / "index.html"


def normalize_base_path(value: str) -> str:
    """Return a canonical subpath such as ``/epub2web`` (or ``""`` for root)."""
    value = (value or "").strip()
    if not value or value == "/":
        return ""
    if (
        "://" in value
        or "?" in value
        or "#" in value
        or "\\" in value
        or value.startswith("//")
        or any(c.isspace() for c in value)
        or any(c in "<>\"'`" for c in value)
        or any(ord(c) < 32 or ord(c) == 127 for c in value)
    ):
        raise ValueError(f"invalid base path: {value!r}")
    segments = [segment for segment in value.strip("/").split("/") if segment]
    if not segments or any(segment in (".", "..") for segment in segments):
        raise ValueError(f"invalid base path: {value!r}")
    return "/" + "/".join(segments)


def strip_base_path(value: str, base_path: str) -> str:
    """Strip an already-normalized base path from a root-relative URL path."""
    if base_path and (value == base_path or value.startswith(base_path + "/")):
        return value[len(base_path) :] or "/"
    return value
