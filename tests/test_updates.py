from __future__ import annotations

import json
import urllib.error

import pytest
from epub2web import updates


class _Response:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args) -> bool:
        return False

    def read(self, _size: int = -1) -> bytes:
        return self.payload


def _payload(**overrides) -> bytes:
    data = {
        "tag_name": "v0.4.0",
        "body": "## Added\n\n- A thing.",
    }
    data.update(overrides)
    return json.dumps(data).encode("utf-8")


def _respond_with(payload: bytes):
    def fake(_request, *, timeout):
        return _Response(payload)

    return fake


@pytest.mark.parametrize(
    ("latest", "current", "expected"),
    [
        ("0.4.0", "0.3.0", True),
        ("v0.4.0", "v0.3.0", True),
        ("1.0.0", "0.9.9", True),
        ("0.10.0", "0.9.0", True),
        ("0.3.0", "0.3.0", False),
        ("0.3", "0.3.0", False),
        ("0.2.9", "0.3.0", False),
        ("0.4.0-rc.1", "0.3.0", False),
        ("nightly", "0.3.0", False),
    ],
)
def test_is_newer_compares_stable_versions(latest, current, expected):
    assert updates.is_newer(latest, current) is expected


def test_is_newer_defaults_to_running_version():
    assert updates.is_newer("999.0.0") is True
    assert updates.is_newer(updates.__version__) is False


def test_fetch_latest_release_parses_release(monkeypatch):
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return _Response(_payload())

    monkeypatch.setattr(updates.urllib.request, "urlopen", fake_urlopen)

    release = updates.fetch_latest_release(timeout=1.5)

    assert release == updates.ReleaseInfo(
        version="0.4.0",
        notes="## Added\n\n- A thing.",
    )
    request, timeout = requests[0]
    assert request.full_url == updates.LATEST_RELEASE_API
    assert timeout == 1.5
    headers = {key.lower(): value for key, value in request.header_items()}
    assert headers["user-agent"] == updates.USER_AGENT
    assert headers["accept"] == "application/vnd.github+json"


def test_fetch_latest_release_tolerates_missing_notes(monkeypatch):
    monkeypatch.setattr(
        updates.urllib.request,
        "urlopen",
        _respond_with(_payload(body=None)),
    )

    assert updates.fetch_latest_release() == updates.ReleaseInfo("0.4.0", "")


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"not json",
        b"[]",
        b'{"tag_name": 4}',
        b'{"tag_name": "nightly"}',
        b'{"tag_name": "v0.4.0-rc.1"}',
    ],
)
def test_fetch_latest_release_rejects_invalid_payloads(monkeypatch, payload):
    monkeypatch.setattr(
        updates.urllib.request,
        "urlopen",
        _respond_with(payload),
    )

    assert updates.fetch_latest_release() is None


def test_fetch_latest_release_rejects_oversized_response(monkeypatch):
    payload = b"x" * (updates.MAX_RESPONSE_BYTES + 1)
    monkeypatch.setattr(
        updates.urllib.request,
        "urlopen",
        _respond_with(payload),
    )

    assert updates.fetch_latest_release() is None


def test_fetch_latest_release_ignores_network_errors(monkeypatch):
    def fail(_request, *, timeout):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(updates.urllib.request, "urlopen", fail)

    assert updates.fetch_latest_release() is None


def test_download_url_points_at_site_download_page():
    assert updates.DOWNLOAD_URL == "https://gowwre.github.io/epub2web/download/"
