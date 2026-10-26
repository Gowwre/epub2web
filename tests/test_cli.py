from pathlib import Path

from epub2web.cli import main


def test_cli_build(tiny_epub, tmp_path: Path, capsys):
    site = tmp_path / "site"
    code = main([str(tiny_epub), "-o", str(site), "--force"])
    assert code == 0
    output = capsys.readouterr().out
    assert "Verify:  PASS" in output
    assert "Links:   PASS" in output
    assert (site / "index.html").exists()
    assert (site / "search-index.json").exists()


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
