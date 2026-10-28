from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from epub2web import __version__

ROOT = Path(__file__).resolve().parents[1]

CHANGELOG = """# Changelog

## Unreleased

### Added
- A future change.

## 1.2.3 - 2026-11-04

### Added
- New export command.

### Fixed
- Fixed the broken link.

## 1.2.2 — 2026-10-01

- An older note.
"""


def _release_notes_module():
    path = ROOT / "scripts" / "release_notes.py"
    spec = importlib.util.spec_from_file_location("release_notes", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def release_notes():
    return _release_notes_module()


def test_extracts_exact_version_section(release_notes):
    notes = release_notes.extract_release_notes(CHANGELOG, "1.2.3")
    assert notes == ("### Added\n- New export command.\n\n### Fixed\n- Fixed the broken link.")


def test_current_package_version_has_release_notes(release_notes):
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert release_notes.extract_release_notes(changelog, __version__)


@pytest.mark.parametrize(
    "heading",
    [
        "## 1.2.3",
        "## 1.2.3 - 2026-11-04",
        "## 1.2.3 — 2026-11-04",
        "## 1.2.3 \u2013 2026-11-04",
        "## 1.2.3 (2026-11-04)",
        "## [1.2.3] - 2026-11-04",
        "## [1.2.3](https://example.test/compare) - 2026-11-04",
        "## v1.2.3 - 2026-11-04",
    ],
)
def test_accepts_common_changelog_headings(release_notes, heading):
    changelog = f"# Changelog\n\n{heading}\n\n### Fixed\n- A fix.\n"
    assert release_notes.extract_release_notes(changelog, "1.2.3") == "### Fixed\n- A fix."


def test_version_argument_may_have_v_prefix(release_notes):
    assert "New export command." in release_notes.extract_release_notes(CHANGELOG, "v1.2.3")


def test_ignores_level_two_headings_inside_code_fences(release_notes):
    changelog = """# Changelog

## 1.2.3 - 2026-11-04

```markdown
## 9.9.9 - not a release
```

### Fixed
- A fix.
"""
    notes = release_notes.extract_release_notes(changelog, "1.2.3")
    assert "## 9.9.9 - not a release" in notes
    assert notes.endswith("### Fixed\n- A fix.")


def test_missing_version_raises(release_notes):
    with pytest.raises(release_notes.ReleaseNotesError, match=r"no '## 9\.9\.9'"):
        release_notes.extract_release_notes(CHANGELOG, "9.9.9")


def test_empty_version_section_raises(release_notes):
    changelog = "# Changelog\n\n## 1.2.3 - 2026-11-04\n\n## 1.2.2 - 2026-10-01\n\n- Older.\n"
    with pytest.raises(release_notes.ReleaseNotesError, match="is empty"):
        release_notes.extract_release_notes(changelog, "1.2.3")


def test_cli_writes_notes_file(release_notes, tmp_path: Path):
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(CHANGELOG, encoding="utf-8")
    output = tmp_path / "release-notes.md"
    code = release_notes.main(
        [
            "--version",
            "1.2.3",
            "--changelog",
            str(changelog),
            "--output",
            str(output),
        ]
    )
    assert code == 0
    assert output.read_text(encoding="utf-8").startswith("### Added")


def test_cli_returns_two_for_missing_section(release_notes, tmp_path: Path):
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(CHANGELOG, encoding="utf-8")
    code = release_notes.main(["--version", "9.9.9", "--changelog", str(changelog)])
    assert code == 2
