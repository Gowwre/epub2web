from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from epub2web import __version__

ROOT = Path(__file__).resolve().parents[1]


def _build_gui_module():
    path = ROOT / "scripts" / "build_gui.py"
    spec = importlib.util.spec_from_file_location("build_gui", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def build_gui():
    return _build_gui_module()


def test_project_version_matches_package(build_gui):
    assert build_gui.project_version() == __version__


def test_artifact_stem_is_platform_and_arch_specific(build_gui):
    assert build_gui.artifact_stem("1.2.3", "windows", "x64") == "epub2web-gui-1.2.3-windows-x64"
    assert build_gui.artifact_stem("1.2.3", "macos", "arm64") == "epub2web-gui-1.2.3-macos-arm64"
    assert build_gui.artifact_stem("1.2.3", "linux", "x86_64") == "epub2web-gui-1.2.3-linux-x86_64"


def test_appimage_arch_uses_appimage_names(build_gui):
    assert build_gui.appimage_arch("x86_64") == "x86_64"
    assert build_gui.appimage_arch("aarch64") == "aarch64"
    assert build_gui.appimage_arch("armv7l") == "armhf"


@pytest.mark.parametrize(
    ("name", "extra"),
    [
        ("linux", []),
        ("windows", ["--windowed"]),
        ("macos", ["--windowed", "--osx-bundle-identifier"]),
    ],
)
def test_pyinstaller_command_bundles_data_and_worker(build_gui, tmp_path: Path, name, extra):
    command = build_gui.pyinstaller_command(tmp_path, one_file=False, icon=None, name=name)
    assert "--collect-data" in command
    assert command[command.index("--collect-data") + 1] == "epub2web"
    assert "--collect-submodules" in command
    assert command[command.index("--collect-submodules") + 1] == "epub2web"
    assert str(build_gui.ENTRY_POINT) == command[-1]
    for flag in extra:
        assert flag in command
    assert "--onefile" not in command


def test_pyinstaller_command_can_build_one_file(build_gui, tmp_path: Path):
    command = build_gui.pyinstaller_command(tmp_path, one_file=True, icon=None, name="linux")
    assert "--onefile" in command
    assert "--windowed" not in command


def test_built_and_frozen_paths_per_platform(build_gui, tmp_path: Path):
    dist = tmp_path / "pyinstaller-dist"

    windows = dist / "epub2web-gui"
    assert build_gui._built_path(tmp_path, False, "windows") == windows
    assert build_gui._frozen_executable(windows, False, "windows") == windows / "epub2web-gui.exe"

    windows_one = dist / "epub2web-gui.exe"
    assert build_gui._built_path(tmp_path, True, "windows") == windows_one
    assert build_gui._frozen_executable(windows_one, True, "windows") == windows_one

    mac = dist / "epub2web-gui.app"
    assert build_gui._built_path(tmp_path, False, "macos") == mac
    assert (
        build_gui._frozen_executable(mac, False, "macos")
        == mac / "Contents" / "MacOS" / "epub2web-gui"
    )

    linux = dist / "epub2web-gui"
    assert build_gui._built_path(tmp_path, False, "linux") == linux
    assert build_gui._frozen_executable(linux, False, "linux") == linux / "epub2web-gui"


def test_portable_readme_includes_platform_specific_guidance(build_gui):
    windows = build_gui._portable_readme("1.2.3", "windows", "x64")
    macos = build_gui._portable_readme("1.2.3", "macos", "arm64")
    linux = build_gui._portable_readme("1.2.3", "linux", "x86_64")
    assert "Windows protected your PC" in windows
    assert "More info" in windows
    assert "Run anyway" in windows
    assert "Applications" in macos
    assert "Open Anyway" in macos
    assert "macOS 14" in macos
    assert "xattr -dr com.apple.quarantine" in macos
    assert "appimage-extract-and-run" in linux


def test_license_bundle_includes_project_and_dependency_texts(build_gui, tmp_path: Path):
    bundle = build_gui._write_license_bundle(
        tmp_path,
        "linux",
        "x86_64",
        [("Example dependency", "Example license text.")],
    )
    assert (tmp_path / "LICENSE").is_file()
    assert (tmp_path / "THIRD_PARTY_NOTICES.md").is_file()
    text = bundle.read_text(encoding="utf-8")
    assert "Example dependency" in text
    assert "Example license text." in text
    assert build_gui._collect_license_texts()
