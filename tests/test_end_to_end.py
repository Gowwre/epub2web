import json
import shutil
import uuid
from pathlib import Path

from bs4 import BeautifulSoup
from epub2web.annotations import make_document, write_document
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
    assert (site / "assets" / "annotations.js").is_file()

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


def test_content_id_survives_metadata_changes_and_tracks_text(
    tiny_epub, epub_factory, tmp_path: Path
):
    def extract(epub: Path, name: str) -> dict:
        return GenericExtractor(
            epub,
            tmp_path / f"{name}-content",
            tmp_path / f"{name}-images",
        ).run()

    original = extract(tiny_epub, "original")
    content_id = original["meta"]["content_id"]
    assert len(content_id) == 64
    assert all(character in "0123456789abcdef" for character in content_id)

    metadata_variant = epub_factory(
        "metadata-variant.epub",
        replacements={
            "OEBPS/content.opf": [
                (b"<dc:title>A Tiny Book</dc:title>", b"<dc:title>A Revised Title</dc:title>")
            ]
        },
    )
    metadata_book = extract(metadata_variant, "metadata-variant")
    assert metadata_book["meta"]["content_id"] == content_id
    assert metadata_book["meta"]["reading_id"] != original["meta"]["reading_id"]

    text_variant = epub_factory(
        "text-variant.epub",
        replacements={"OEBPS/ch1.xhtml": [(b"Hello", b"Goodbye")]},
    )
    text_book = extract(text_variant, "text-variant")
    assert text_book["meta"]["content_id"] != content_id


def test_generated_site_never_contains_annotation_stores(tiny_epub, tmp_path: Path):
    content = tmp_path / "content"
    images = tmp_path / "images"
    site = tmp_path / "site"

    book = GenericExtractor(tiny_epub, content, images).run()
    marker = "PRIVATE-ANNOTATION-MARKER"
    document = make_document(
        book["meta"],
        [
            {
                "id": str(uuid.uuid4()),
                "type": "highlight",
                "created": "2026-11-04T10:00:00.000Z",
                "updated": "2026-11-04T10:00:00.000Z",
                "note": marker,
                "quote": "Hello world.",
            }
        ],
    )
    write_document(content / "annotations.json", document)

    render_site(content, site, site_url="http://localhost:8000")

    assert not (site / "annotations.json").exists()
    assert not (site / "annotations").exists()
    rendered = "\n".join(
        path.read_text(encoding="utf-8", errors="replace") for path in site.rglob("*.html")
    )
    assert marker not in rendered
    assert "epub2web.annotations" not in rendered


def test_reader_advertises_keyboard_shortcuts(tiny_epub, tmp_path: Path):
    content = tmp_path / "content"
    images = tmp_path / "images"
    site = tmp_path / "site"

    GenericExtractor(tiny_epub, content, images).run()
    render_site(content, site, site_url="http://localhost:8000")

    home = BeautifulSoup((site / "index.html").read_text(encoding="utf-8"), "lxml")
    help_button = home.find("button", class_="shortcuts-btn")
    assert help_button is not None
    assert help_button["aria-keyshortcuts"] == "?"
    search_button = home.find("button", class_="search-btn")
    assert search_button["aria-keyshortcuts"] == "/"
    assert search_button.find("kbd").get_text(strip=True) == "/"
    assert home.find("button", class_="footer-shortcuts") is not None
    assert home.find("button", class_="menu-shortcuts") is not None
    shortcuts = home.find("dialog", id="epub2web-shortcuts-dialog")
    assert shortcuts is not None
    assert shortcuts.find(id="shortcuts-anywhere") is not None
    assert shortcuts.find(id="shortcuts-reading") is None
    assert "Search the book" in shortcuts.get_text(" ", strip=True)

    page = BeautifulSoup((site / "read" / "1" / "index.html").read_text(encoding="utf-8"), "lxml")
    shortcuts = page.find("dialog", id="epub2web-shortcuts-dialog")
    assert shortcuts.find(id="shortcuts-reading") is not None
    assert shortcuts.find(id="shortcuts-notes") is not None
    toolbar = page.find(id="epub2web-annotation-toolbar")
    assert toolbar.find(attrs={"data-annotation-highlight": True})["aria-keyshortcuts"] == "H"
    assert toolbar.find("kbd", class_="annotation-key").get_text(strip=True) == "H"
    note_dialog = page.find(id="epub2web-note-dialog")
    assert "Ctrl" in note_dialog.find("p", class_="note-hint").get_text(" ", strip=True)
    reader_dialog = page.find(id="epub2web-reader-dialog")
    assert reader_dialog.find("button", class_="reader-shortcuts") is not None
    panel = page.find(id="epub2web-annotations-dialog")
    assert "all shortcuts" in panel.find("p", class_="annotations-shortcuts").get_text(
        " ", strip=True
    )


def test_reader_explains_annotation_storage_before_requesting_persistence(
    tiny_epub, tmp_path: Path
):
    content = tmp_path / "content"
    images = tmp_path / "images"
    site = tmp_path / "site"

    GenericExtractor(tiny_epub, content, images).run()
    render_site(content, site, site_url="http://localhost:8000")
    page = BeautifulSoup((site / "read" / "1" / "index.html").read_text(encoding="utf-8"), "lxml")

    panel = page.find(id="epub2web-annotations-dialog")
    privacy = panel.find(class_="annotations-privacy").get_text(" ", strip=True)
    assert "stay in this browser" in privacy
    assert "never uploaded" in privacy
    assert panel.find(attrs={"data-storage-open": True}) is not None

    storage = page.find(id="epub2web-storage-dialog")
    assert storage is not None
    text = storage.get_text(" ", strip=True)
    assert "never uploaded" in text
    assert "may ask for permission" in text
    assert "Export a backup" in text
    assert storage.find(attrs={"data-storage-request": True}) is not None

    script = (site / "assets" / "annotations.js").read_text(encoding="utf-8")
    assert script.count("navigator.storage.persist()") == 1


def test_reader_offers_markdown_export_and_copy_all(tiny_epub, tmp_path: Path):
    content = tmp_path / "content"
    images = tmp_path / "images"
    site = tmp_path / "site"

    GenericExtractor(tiny_epub, content, images).run()
    render_site(content, site, site_url="http://localhost:8000")
    page = BeautifulSoup((site / "read" / "1" / "index.html").read_text(encoding="utf-8"), "lxml")
    panel = page.find(id="epub2web-annotations-dialog")

    copy_all = panel.find(attrs={"data-annotations-copy": True})
    assert copy_all is not None
    assert copy_all.get_text(strip=True) == "Copy all"
    export = panel.find("details", class_="annotations-export")
    assert export is not None
    assert export.find("summary").get_text(strip=True) == "Export"
    markdown = export.find(attrs={"data-annotations-export-markdown": True})
    assert markdown is not None
    assert markdown.get_text(strip=True) == "Markdown (.md)"
    backup = export.find(attrs={"data-annotations-export": True})
    assert backup is not None
    assert backup.get_text(strip=True) == "JSON backup (.json)"

    script = (site / "assets" / "annotations.js").read_text(encoding="utf-8")
    assert "function markdownForAnnotations" in script
    assert "text/markdown;charset=utf-8" in script


def test_reader_has_local_annotation_search(tiny_epub, tmp_path: Path):
    content = tmp_path / "content"
    images = tmp_path / "images"
    site = tmp_path / "site"

    GenericExtractor(tiny_epub, content, images).run()
    render_site(content, site, site_url="http://localhost:8000")
    page = BeautifulSoup((site / "read" / "1" / "index.html").read_text(encoding="utf-8"), "lxml")
    panel = page.find(id="epub2web-annotations-dialog")

    search = panel.find("input", attrs={"data-annotations-search": True})
    assert search is not None
    assert search["type"] == "search"
    assert search["aria-controls"] == "epub2web-annotations-list"
    assert panel.find(id="epub2web-annotations-list") is not None
    status = panel.find(attrs={"data-annotations-search-status": True})
    assert status is not None
    assert status.has_attr("hidden")

    script = (site / "assets" / "annotations.js").read_text(encoding="utf-8")
    assert "function annotationMatchesQuery" in script
    assert "function normalizeSearch" in script


def test_rendered_pages_expose_reading_progress(tiny_epub, tmp_path: Path):
    content = tmp_path / "content"
    images = tmp_path / "images"
    site = tmp_path / "site"

    book = GenericExtractor(tiny_epub, content, images).run()
    reading_id = book["meta"]["reading_id"]
    render_site(content, site, site_url="http://localhost:8000")

    home = BeautifulSoup((site / "index.html").read_text(encoding="utf-8"), "lxml")
    assert home.html["data-reading-id"] == reading_id
    assert home.html["data-content-id"] == book["meta"]["content_id"]
    start = next(
        (
            link
            for link in home.find_all(attrs={"data-reading-start": True})
            if link.find(attrs={"data-reading-label": True}) is not None
        ),
        None,
    )
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
    assert home.find(attrs={"data-annotations-open": True}) is None
    assert home.find(id="epub2web-annotation-toolbar") is None

    page1 = BeautifulSoup((site / "read" / "1" / "index.html").read_text(encoding="utf-8"), "lxml")
    page2 = BeautifulSoup((site / "read" / "2" / "index.html").read_text(encoding="utf-8"), "lxml")

    page_keys = {entry["key"] for entry in reading_map}
    meta_script = page1.find("script", id="epub2web-book-meta")
    assert meta_script is not None
    assert json.loads(meta_script.get_text())["content_id"] == book["meta"]["content_id"]
    page_map_script = page1.find("script", id="epub2web-reading-map")
    assert page_map_script is not None
    assert {entry["key"] for entry in json.loads(page_map_script.get_text())} == page_keys
    assert page1.find(attrs={"data-annotations-open": True}) is not None
    assert page1.find(id="epub2web-annotation-toolbar") is not None
    assert page1.find(id="epub2web-highlight-card") is not None
    assert page1.find(id="epub2web-note-dialog") is not None
    assert page1.find(id="epub2web-annotations-dialog") is not None
    for page, chapter in ((page1, 1), (page2, 2)):
        assert page.html["data-reading-id"] == reading_id
        assert page.html["data-content-id"] == book["meta"]["content_id"]
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
    header_read = home.find("a", class_="header-read-link")
    assert header_read is not None
    assert header_read.get_text(strip=True) == "Read"
    assert header_read.has_attr("data-reading-start")
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
    assert {input["value"] for input in reader.select('input[name="reader-paragraphs"]')} == {
        "spaced",
        "indented",
    }
    assert {input["value"] for input in reader.select('input[name="reader-width"]')} == {
        "narrow",
        "standard",
        "wide",
    }
    assert {input["value"] for input in reader.select('input[name="reader-theme"]')} == {
        "auto",
        "light",
        "dark",
    }

    page = BeautifulSoup((site / "read" / "1" / "index.html").read_text(encoding="utf-8"), "lxml")
    assert page.find("a", class_="header-read-link") is None
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

    lightbox = page.find("dialog", id="epub2web-lightbox")
    assert lightbox is not None
    assert lightbox.find(attrs={"data-lightbox-prev": True}) is not None
    assert lightbox.find(attrs={"data-lightbox-next": True}) is not None
    assert lightbox.find(attrs={"data-lightbox-status": True}) is not None
    assert page.find("a", class_="lightbox-link") is not None


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
