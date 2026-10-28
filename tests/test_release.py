from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_release_module():
    path = ROOT / "scripts" / "release.py"
    spec = importlib.util.spec_from_file_location("release_script", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def release_script():
    return _load_release_module()


def _write_repo(root: Path, *, unreleased: str | None = "- New thing.\n") -> None:
    package = root / "epub2web"
    package.mkdir()
    (package / "__init__.py").write_text('__version__ = "0.3.0"\n', encoding="utf-8")
    entries = f"### Added\n\n{unreleased}\n" if unreleased else ""
    (root / "CHANGELOG.md").write_text(
        f"# Changelog\n\n## Unreleased\n\n{entries}## 0.3.0 - 2026-10-28\n\n- Old release.\n",
        encoding="utf-8",
    )


def test_prepare_release_updates_version_and_changelog(release_script, tmp_path: Path):
    _write_repo(tmp_path)

    notes = release_script.prepare_release(tmp_path, "0.4.0", "2026-11-01")

    assert "New thing" in notes
    assert (tmp_path / "epub2web" / "__init__.py").read_text(encoding="utf-8").strip() == (
        '__version__ = "0.4.0"'
    )
    changelog = (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## Unreleased\n\n## 0.4.0 - 2026-11-01" in changelog
    assert "- New thing." in changelog
    assert "## 0.3.0 - 2026-10-28" in changelog


def test_prepare_release_dry_run_leaves_files_untouched(release_script, tmp_path: Path):
    _write_repo(tmp_path)
    before = (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")

    release_script.prepare_release(tmp_path, "0.4.0", "2026-11-01", dry_run=True)

    assert (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8") == before
    assert '__version__ = "0.3.0"' in (tmp_path / "epub2web" / "__init__.py").read_text(
        encoding="utf-8"
    )


def test_prepare_release_rejects_empty_unreleased(release_script, tmp_path: Path):
    _write_repo(tmp_path, unreleased=None)

    with pytest.raises(release_script.ReleaseError, match="no entries"):
        release_script.prepare_release(tmp_path, "0.4.0", "2026-11-01")


def test_prepare_release_rejects_same_or_older_version(release_script, tmp_path: Path):
    _write_repo(tmp_path)

    with pytest.raises(release_script.ReleaseError, match="must be greater"):
        release_script.prepare_release(tmp_path, "0.3.0", "2026-11-01")

    with pytest.raises(release_script.ReleaseError, match="must be greater"):
        release_script.prepare_release(tmp_path, "0.2.9", "2026-11-01")


def test_prepare_release_rejects_bad_date(release_script, tmp_path: Path):
    _write_repo(tmp_path)

    with pytest.raises(release_script.ReleaseError, match="invalid release date"):
        release_script.prepare_release(tmp_path, "0.4.0", "tomorrow")


def test_ship_is_a_dry_run_by_default(release_script, tmp_path: Path, monkeypatch, capsys):
    package = tmp_path / "epub2web"
    package.mkdir()
    (package / "__init__.py").write_text('__version__ = "0.4.0"\n', encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## 0.4.0 - 2026-11-01\n\n### Added\n\n- A release.\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-m",
            "Release 0.4.0",
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    monkeypatch.setattr(release_script, "ROOT", tmp_path)

    release_script.ship_release("0.4.0", execute=False, skip_checks=True)

    output = capsys.readouterr().out
    assert "Dry run" in output
    assert "git tag v0.4.0" in output
