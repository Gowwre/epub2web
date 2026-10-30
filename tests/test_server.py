from __future__ import annotations

from pathlib import Path

import pytest
from epub2web.server import serve_directory


def test_serve_directory_announces_url_before_blocking(tmp_path: Path):
    (tmp_path / "index.html").write_text("<!doctype html><title>ok</title>", encoding="utf-8")
    announced: list[str] = []

    class StopServing(Exception):
        pass

    def on_ready(url: str) -> None:
        announced.append(url)
        raise StopServing

    with pytest.raises(StopServing):
        serve_directory(tmp_path, port=0, open_browser=False, on_ready=on_ready)

    assert len(announced) == 1
    assert announced[0].startswith("http://127.0.0.1:")
    assert announced[0].endswith("/")
