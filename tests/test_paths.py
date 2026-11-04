from __future__ import annotations

import sys
from pathlib import Path

from epub2web import logging as app_logging
from epub2web.controller import default_log_dir as controller_log_dir
from epub2web.paths import app_data_dir


def test_linux_app_data_honors_xdg_data_home(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    assert app_data_dir() == tmp_path / "xdg" / "epub2web"


def test_linux_app_data_falls_back_to_local_share(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    assert app_data_dir() == tmp_path / "home" / ".local" / "share" / "epub2web"


def test_macos_app_data_uses_application_support(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    assert app_data_dir() == tmp_path / "home" / "Library" / "Application Support" / "epub2web"


def test_windows_app_data_prefers_local_app_data(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    assert app_data_dir() == tmp_path / "LocalAppData" / "epub2web"


def test_windows_app_data_falls_back_to_app_data(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    assert app_data_dir() == tmp_path / "Roaming" / "epub2web"


def test_log_dirs_follow_app_data(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    monkeypatch.delenv("EPUB2WEB_LOG_DIR", raising=False)
    assert app_logging.default_log_dir() == tmp_path / "xdg" / "epub2web" / "logs"
    assert controller_log_dir() == tmp_path / "xdg" / "epub2web" / "logs"


def test_log_dir_environment_override(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("EPUB2WEB_LOG_DIR", str(tmp_path / "custom-logs"))
    assert app_logging.default_log_dir() == tmp_path / "custom-logs"
