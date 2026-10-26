import json
from pathlib import Path

from epub2web.generic import GenericExtractor
from epub2web.links import check_site_links
from epub2web.render import render_site
from epub2web.verify import verify_site


def test_build_and_verify(tiny_epub, tmp_path: Path):
    content = tmp_path / "content"
    images = tmp_path / "images"
    site = tmp_path / "site"

    book = GenericExtractor(tiny_epub, content, images).run()
    assert book["meta"]["title"] == "A Tiny Book"
    assert len(book["pages"]) == 2

    render_site(content, site, site_url="http://localhost:8000")
    assert (site / "index.html").exists()
    assert (site / "read" / "1" / "index.html").exists()
    assert (site / "search-index.json").exists()

    search = json.loads((site / "search-index.json").read_text(encoding="utf-8"))
    assert search
    assert any("Hello" in entry["text"] for entry in search)

    verified = verify_site(content, site, verbose=False)
    assert verified["pass"], verified

    links = check_site_links(site)
    assert links["ok"], links


def test_base_path_build(tiny_epub, tmp_path: Path):
    content = tmp_path / "content"
    images = tmp_path / "images"
    site = tmp_path / "site"

    GenericExtractor(tiny_epub, content, images).run()
    render_site(content, site, site_url="https://example.com", base_path="shelf")

    index = (site / "index.html").read_text(encoding="utf-8")
    assert 'data-base="/shelf"' in index
    assert 'href="/shelf/assets/styles.css"' in index
    assert 'href="/contents/"' not in index
    assert "https://example.com/shelf/" in (site / "sitemap.xml").read_text(encoding="utf-8")
    assert "https://example.com/shelf/sitemap.xml" in (site / "robots.txt").read_text(
        encoding="utf-8"
    )

    links = check_site_links(site, base_path="/shelf")
    assert links["ok"], links
