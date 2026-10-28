from pathlib import Path

import pytest
from epub2web.cli import main
from epub2web.render import SITE_MARKER


def test_cli_build(tiny_epub, tmp_path: Path, capsys):
    site = tmp_path / "site"
    code = main([str(tiny_epub), "-o", str(site), "--force"])
    assert code == 0
    output = capsys.readouterr().out
    assert "Verify:  PASS" in output
    assert "Links:   PASS" in output
    assert (site / "index.html").exists()
    assert (site / "search-index.json").exists()


def test_rerun_refreshes_existing_site_without_force(tiny_epub, tmp_path: Path, capsys):
    site = tmp_path / "site"
    assert main([str(tiny_epub), "-o", str(site)]) == 0
    capsys.readouterr()

    assert main([str(tiny_epub), "-o", str(site)]) == 0
    output = capsys.readouterr().out
    assert "refreshing the existing site" in output
    assert (site / "index.html").exists()
    assert (site / "search-index.json").exists()


def test_empty_output_directory_is_allowed(tiny_epub, tmp_path: Path):
    site = tmp_path / "site"
    site.mkdir()

    assert main([str(tiny_epub), "-o", str(site)]) == 0
    assert (site / "index.html").exists()


def test_existing_unrelated_directory_is_refused(tiny_epub, tmp_path: Path, capsys):
    site = tmp_path / "site"
    site.mkdir()
    keep = site / "keep.txt"
    keep.write_text("not an epub2web site", encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        main([str(tiny_epub), "-o", str(site)])

    assert exc.value.code == 2
    assert "was not created by epub2web" in capsys.readouterr().err
    assert keep.read_text(encoding="utf-8") == "not an epub2web site"


def test_legacy_site_needs_force_once_to_gain_marker(tiny_epub, tmp_path: Path, capsys):
    site = tmp_path / "site"
    assert main([str(tiny_epub), "-o", str(site)]) == 0
    (site / SITE_MARKER).unlink()
    capsys.readouterr()

    with pytest.raises(SystemExit) as exc:
        main([str(tiny_epub), "-o", str(site)])
    assert exc.value.code == 2
    assert "--force once" in capsys.readouterr().err

    assert main([str(tiny_epub), "-o", str(site), "--force"]) == 0
    assert (site / SITE_MARKER).is_file()


def test_cli_title_override_splits_dash_subtitle(tiny_epub, tmp_path: Path):
    site = tmp_path / "site"
    assert main([str(tiny_epub), "-o", str(site), "--title", "Book \u2014 A Novel"]) == 0
    index = (site / "index.html").read_text(encoding="utf-8")
    assert '<span class="line">Book</span>' in index
    assert "A Novel" in index


def test_cli_can_skip_gates_for_development(tiny_epub, tmp_path: Path, capsys):
    site = tmp_path / "site"
    code = main(
        [
            str(tiny_epub),
            "-o",
            str(site),
            "--no-verify",
            "--no-links",
        ]
    )
    assert code == 0
    output = capsys.readouterr().out
    assert "Verify:  skipped" in output
    assert "Links:   skipped" in output


def test_cli_base_path(tiny_epub, tmp_path: Path):
    site = tmp_path / "site"
    code = main(
        [
            str(tiny_epub),
            "-o",
            str(site),
            "--base-path",
            "shelf",
            "--site-url",
            "https://example.com",
            "--force",
        ]
    )
    assert code == 0
    index = (site / "index.html").read_text(encoding="utf-8")
    assert 'data-base="/shelf"' in index
    assert 'href="/shelf/assets/styles.css"' in index
