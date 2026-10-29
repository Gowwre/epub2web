import json
import shutil
from pathlib import Path

from bs4 import BeautifulSoup
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

    font_css = (site / "assets" / "fonts.css").read_text(encoding="utf-8")
    assert "literata-latin.woff2" in font_css
    assert "noto-" not in font_css
    assert not (site / "assets" / "fonts" / "cjk").exists()

    verified = verify_site(content, site, verbose=False)
    assert verified["pass"], verified

    links = check_site_links(site)
    assert links["ok"], links


def test_reading_id_is_stable_and_file_specific(tiny_epub, epub_factory, tmp_path: Path):
    content = tmp_path / "content"
    images = tmp_path / "images"
    book = GenericExtractor(tiny_epub, content, images).run()
    reading_id = book["meta"]["reading_id"]

    assert len(reading_id) == 64
    assert all(character in "0123456789abcdef" for character in reading_id)

    copy_path = tmp_path / "copy.epub"
    shutil.copyfile(tiny_epub, copy_path)
    copy_book = GenericExtractor(
        copy_path,
        tmp_path / "copy-content",
        tmp_path / "copy-images",
    ).run()
    assert copy_book["meta"]["reading_id"] == reading_id

    variant = epub_factory(
        "variant.epub",
        replacements={"OEBPS/ch1.xhtml": [(b"Hello", b"Hello again")]},
    )
    variant_book = GenericExtractor(
        variant,
        tmp_path / "variant-content",
        tmp_path / "variant-images",
    ).run()
    assert variant_book["meta"]["reading_id"] != reading_id


def test_rendered_pages_expose_reading_progress(tiny_epub, tmp_path: Path):
    content = tmp_path / "content"
    images = tmp_path / "images"
    site = tmp_path / "site"

    book = GenericExtractor(tiny_epub, content, images).run()
    reading_id = book["meta"]["reading_id"]
    render_site(content, site, site_url="http://localhost:8000")

    home = BeautifulSoup((site / "index.html").read_text(encoding="utf-8"), "lxml")
    assert home.html["data-reading-id"] == reading_id
    start = home.find(attrs={"data-reading-start": True})
    assert start is not None
    assert start.find(attrs={"data-reading-label": True}).get_text(strip=True) == "Start reading"
    restart = home.find(attrs={"data-reading-restart": True})
    assert restart is not None
    assert restart.has_attr("hidden")

    map_script = home.find("script", id="epub2web-reading-map")
    assert map_script is not None
    reading_map = json.loads(map_script.get_text())
    assert len(reading_map) == 2
    assert {entry["route"] for entry in reading_map} == {"/read/1/", "/read/2/"}
    assert {entry["label"] for entry in reading_map} == {"Chapter 1", "Chapter 2"}

    page1 = BeautifulSoup((site / "read" / "1" / "index.html").read_text(encoding="utf-8"), "lxml")
    page2 = BeautifulSoup((site / "read" / "2" / "index.html").read_text(encoding="utf-8"), "lxml")

    page_keys = {entry["key"] for entry in reading_map}
    for page, chapter in ((page1, 1), (page2, 2)):
        assert page.html["data-reading-id"] == reading_id
        assert page.body["data-reading"] == "true"
        assert len(page.body["data-page-key"]) == 16
        assert page.body["data-page-key"] in page_keys
        assert page.body["data-chapter-key"]
        assert f"Chapter {chapter} of 2" in page.get_text(" ", strip=True)

    start1 = float(page1.body["data-progress-start"])
    end1 = float(page1.body["data-progress-end"])
    start2 = float(page2.body["data-progress-start"])
    end2 = float(page2.body["data-progress-end"])
    assert 0 <= start1 < end1 <= 1
    assert abs(start2 - end1) < 1e-9
    assert end2 == 1.0


def test_rendered_site_has_reading_controls(tiny_epub, tmp_path: Path):
    content = tmp_path / "content"
    images = tmp_path / "images"
    site = tmp_path / "site"

    GenericExtractor(tiny_epub, content, images).run()
    render_site(content, site, site_url="http://localhost:8000")

    home = BeautifulSoup((site / "index.html").read_text(encoding="utf-8"), "lxml")
    assert home.find(attrs={"data-reader-open": True}) is not None
    reader = home.find("dialog", id="epub2web-reader-dialog")
    assert reader is not None
    assert {input["value"] for input in reader.select('input[name="reader-size"]')} == {
        "small",
        "default",
        "large",
        "x-large",
    }
    assert {input["value"] for input in reader.select('input[name="reader-spacing"]')} == {
        "compact",
        "default",
        "relaxed",
    }

    page = BeautifulSoup((site / "read" / "1" / "index.html").read_text(encoding="utf-8"), "lxml")
    menu = page.find("dialog", id="epub2web-menu-dialog")
    assert menu is not None
    current = menu.find("a", attrs={"aria-current": "page"})
    assert current is not None
    assert menu.find(attrs={"data-menu-current": True}) is not None
    details = menu.find("details", class_="menu-sections-details")
    assert details is not None
    assert not details.has_attr("open")
    assert details.find("summary").get_text(" ", strip=True).startswith("Sections")

    search_hint = page.find("p", class_="search-hint").get_text(" ", strip=True)
    assert "to choose a result" in search_hint
    assert "Enter" in search_hint


def test_multilingual_fonts_are_selected_and_copied(epub_factory, tmp_path: Path):
    multilingual = "Γειά σου. Привет. مرحبا. שלום. नमस्ते. สวัสดี. 你好。こんにちは。안녕하세요."  # noqa: RUF001
    epub = epub_factory(
        "multilingual.epub",
        replacements={
            "OEBPS/ch1.xhtml": [
                (b"<p>Hello <em>world</em>.</p>", f"<p>{multilingual}</p>".encode()),
            ]
        },
    )
    content = tmp_path / "content"
    images = tmp_path / "images"
    site = tmp_path / "site"

    book = GenericExtractor(epub, content, images).run()
    assert book["stats"]["characters"] > 0
    assert book["pages"][0]["reading_units"] > 0
    render_site(content, site, site_url="http://localhost:8000")

    home = BeautifulSoup((site / "index.html").read_text(encoding="utf-8"), "lxml")
    assert home.html["dir"] == "ltr"

    css = (site / "assets" / "fonts.css").read_text(encoding="utf-8")
    for filename in (
        "literata-greek.woff2",
        "literata-cyrillic.woff2",
        "noto-naskh-arabic-arabic.woff2",
        "noto-serif-hebrew-hebrew.woff2",
        "noto-serif-devanagari-devanagari.woff2",
        "noto-serif-thai-thai.woff2",
    ):
        assert filename in css
        assert (site / "assets" / "fonts" / filename).is_file()
    assert "epub2web-cjk" in css
    for region in ("jp", "kr", "sc"):
        assert f"cjk/{region}/" in css
        assert (site / "assets" / "fonts" / "cjk" / region).is_dir()

    verified = verify_site(content, site, verbose=False)
    assert verified["pass"], verified


def test_rtl_book_sets_direction(epub_factory, tmp_path: Path):
    epub = epub_factory(
        "arabic.epub",
        replacements={
            "OEBPS/content.opf": [
                (b"<dc:language>en</dc:language>", b"<dc:language>ar</dc:language>"),
            ],
            "OEBPS/ch1.xhtml": [
                (
                    b"<p>Hello <em>world</em>.</p>",
                    "<p>مرحبا بالعالم.</p>".encode(),
                ),
            ],
        },
    )
    content = tmp_path / "content"
    images = tmp_path / "images"
    site = tmp_path / "site"

    book = GenericExtractor(epub, content, images).run()
    assert book["meta"]["language"] == "ar"
    render_site(content, site, site_url="http://localhost:8000")

    home = BeautifulSoup((site / "index.html").read_text(encoding="utf-8"), "lxml")
    page = BeautifulSoup((site / "read" / "1" / "index.html").read_text(encoding="utf-8"), "lxml")
    assert home.html["dir"] == "rtl"
    assert page.html["dir"] == "rtl"
    assert "noto-naskh-arabic-arabic.woff2" in (site / "assets" / "fonts.css").read_text(
        encoding="utf-8"
    )


def test_base_path_build(tiny_epub, tmp_path: Path):
    content = tmp_path / "content"
    images = tmp_path / "images"
    site = tmp_path / "site"

    book = GenericExtractor(tiny_epub, content, images).run()
    render_site(content, site, site_url="https://example.com", base_path="shelf")

    index = (site / "index.html").read_text(encoding="utf-8")
    assert 'data-base="/shelf"' in index
    assert f'data-reading-id="{book["meta"]["reading_id"]}"' in index
    assert 'href="/shelf/assets/styles.css"' in index
    assert 'href="/contents/"' not in index
    soup = BeautifulSoup(index, "lxml")
    reading_map = json.loads(soup.find("script", id="epub2web-reading-map").get_text())
    assert reading_map[0]["route"] == "/read/1/"
    assert "https://example.com/shelf/" in (site / "sitemap.xml").read_text(encoding="utf-8")
    assert "https://example.com/shelf/sitemap.xml" in (site / "robots.txt").read_text(
        encoding="utf-8"
    )

    links = check_site_links(site, base_path="/shelf")
    assert links["ok"], links
