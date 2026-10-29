import base64
import io
import re
import zipfile
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from epub2web.cli import main
from epub2web.epub import Epub
from epub2web.generic import (
    BACK_LABELS,
    FRONT_LABELS,
    GenericExtractor,
    label_matches,
    marker_kind,
    sanitize_svg,
)
from epub2web.links import check_site_links
from epub2web.render import SITE_MARKER, render_site
from epub2web.text import match_key
from epub2web.verify import verify_site
from PIL import Image

OPF = "OEBPS/content.opf"
CH1 = "OEBPS/ch1.xhtml"
CH2 = "OEBPS/ch2.xhtml"
COVER = "OEBPS/images/cover.png"


def _build(epub: Path, site: Path) -> int:
    return main([str(epub), "-o", str(site), "--force"])


def test_png_cover_keeps_its_real_extension(tiny_epub, tmp_path: Path):
    site = tmp_path / "site"
    assert _build(tiny_epub, site) == 0

    assert (site / "images" / "cover.png").read_bytes().startswith(b"\x89PNG")
    assert not (site / "images" / "cover.jpg").exists()
    assert "images/cover.png" in (site / "index.html").read_text(encoding="utf-8")


def test_failed_rebuild_preserves_the_previous_site(tiny_epub, epub_factory, tmp_path: Path):
    site = tmp_path / "site"
    assert _build(tiny_epub, site) == 0
    before = (site / "index.html").read_text(encoding="utf-8")

    bad = epub_factory(
        "bad.epub",
        replacements={CH1: [(b'src="images/cover.png"', b'src="images/missing.png"')]},
    )
    assert _build(bad, site) == 2
    assert (site / "index.html").read_text(encoding="utf-8") == before
    assert not list(tmp_path.glob(".site-build-*"))


def test_force_refuses_to_remove_the_input_directory(tiny_epub, tmp_path: Path):
    with pytest.raises(SystemExit) as exc:
        main([str(tiny_epub), "-o", str(tmp_path), "--force"])
    assert exc.value.code == 2
    assert tiny_epub.exists()


def test_missing_image_fails_with_an_actionable_error(epub_factory, tmp_path: Path, capsys):
    bad = epub_factory(
        "missing.epub",
        replacements={CH1: [(b'src="images/cover.png"', b'src="images/missing.png"')]},
    )
    site = tmp_path / "site"
    assert _build(bad, site) == 2
    error = capsys.readouterr().err
    assert "missing from the EPUB" in error
    assert not site.exists()


def test_remote_image_fails_instead_of_disappearing(epub_factory, tmp_path: Path, capsys):
    bad = epub_factory(
        "remote.epub",
        replacements={CH1: [(b'src="images/cover.png"', b'src="https://example.com/f.png"')]},
    )
    assert _build(bad, tmp_path / "site") == 2
    assert "remote image is not supported" in capsys.readouterr().err


def test_empty_spine_content_fails(tiny_epub, tmp_path: Path, capsys):
    target = tmp_path / "empty.epub"
    with zipfile.ZipFile(tiny_epub) as source, zipfile.ZipFile(target, "w") as dest:
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename in (CH1, CH2):
                data = re.sub(rb"<body>.*?</body>", b"<body></body>", data, flags=re.S)
            dest.writestr(item, data)

    assert _build(target, tmp_path / "site") == 2
    assert "no readable pages" in capsys.readouterr().err


def test_source_active_content_is_removed(epub_factory, tmp_path: Path):
    variant = epub_factory(
        "sanitized.epub",
        replacements={
            CH1: [
                (
                    b"</body>",
                    b'<p data-chrome="1" onclick="alert(1)">visible ghost text</p>'
                    b'<p><a href="javascript:alert(2)" onclick="alert(3)">safe link</a></p>'
                    b"</body>",
                )
            ]
        },
    )
    site = tmp_path / "site"
    assert _build(variant, site) == 0
    html = (site / "read" / "1" / "index.html").read_text(encoding="utf-8")
    assert "visible ghost text" in html
    assert "safe link" in html
    assert "javascript:" not in html

    soup = BeautifulSoup(html, "lxml")
    ghost = soup.find(string=lambda value: value and "visible ghost text" in value)
    assert ghost is not None
    assert not ghost.parent.has_attr("data-chrome")
    assert not ghost.parent.has_attr("onclick")
    link = soup.find("a", string=lambda value: value and "safe link" in value)
    assert link is not None
    assert not link.has_attr("href")
    assert not link.has_attr("onclick")


def test_article_wrappers_pre_and_definition_lists_are_kept(epub_factory, tmp_path: Path):
    variant = epub_factory(
        "structural.epub",
        replacements={
            CH1: [
                (b"<body>", b"<body><article>"),
                (
                    b"</body>",
                    b"</article><pre>line one\n  line two</pre>"
                    b"<dl><dt>Term</dt><dd>Definition</dd></dl></body>",
                ),
            ]
        },
    )
    site = tmp_path / "site"
    assert _build(variant, site) == 0
    html = (site / "read" / "1" / "index.html").read_text(encoding="utf-8")
    assert '<pre class="book-pre">' in html
    assert '<dl class="book-dl">' in html
    assert "line one" in html
    assert "Definition" in html


def test_section_title_paragraphs_become_the_page_header(epub_factory, tmp_path: Path):
    variant = epub_factory(
        "title-paragraph.epub",
        replacements={
            CH1: [
                (
                    b'<h1 id="ch1">Chapter One</h1>',
                    b'<p class="fmtitleq" id="ch1"><span>CHAPTER ONE</span></p>',
                )
            ]
        },
    )
    site = tmp_path / "site"
    assert _build(variant, site) == 0

    soup = BeautifulSoup((site / "read" / "1" / "index.html").read_text(encoding="utf-8"), "lxml")
    main = soup.find("main")
    assert main is not None
    assert main.get_text(" ", strip=True).count("CHAPTER ONE") == 1
    header = soup.find("header", class_="chapter-header")
    assert header is not None
    assert not header.has_attr("data-chrome")
    assert header.find("h1", class_="chapter-title").get_text(strip=True) == "CHAPTER ONE"
    assert soup.find("h2", class_="section-title", string="CHAPTER ONE") is None


def test_dropcap_image_keeps_its_ornamental_float(epub_factory, tmp_path: Path):
    variant = epub_factory(
        "dropcap.epub",
        replacements={
            CH1: [
                (
                    b"<p>Hello <em>world</em>.</p>",
                    b'<p><span class="dropcap"><img src="images/cover.png" alt=""/></span>'
                    b" Hello world.</p>",
                )
            ]
        },
    )
    site = tmp_path / "site"
    assert _build(variant, site) == 0

    html = (site / "read" / "1" / "index.html").read_text(encoding="utf-8")
    assert 'class="lede has-dropcap-image"' in html
    assert 'data-dropcap="true"' in html
    assert 'src="/images/cover.png"' in html


def test_index_and_reference_classes_survive(epub_factory, tmp_path: Path):
    variant = epub_factory(
        "reference-classes.epub",
        replacements={
            CH1: [
                (
                    b"<p>Hello <em>world</em>.</p>",
                    b'<p class="index">Alpha</p><p class="indexsub">Beta</p>'
                    b'<p class="hangs">Citation</p>',
                )
            ]
        },
    )
    site = tmp_path / "site"
    assert _build(variant, site) == 0

    html = (site / "read" / "1" / "index.html").read_text(encoding="utf-8")
    assert 'class="lede index-entry"' in html
    assert 'class="index-subentry"' in html
    assert 'class="hanging"' in html


def test_figure_caption_anchors_point_to_the_figure(epub_factory, tmp_path: Path):
    variant = epub_factory(
        "figure-anchor.epub",
        replacements={
            CH1: [
                (
                    b"<p>Hello <em>world</em>.</p>",
                    b'<p>Hello <a href="#fig-one">figure</a>.</p>',
                ),
                (
                    b"<figcaption>Figure one.</figcaption>",
                    b'<figcaption><span id="fig-one"></span>Figure one.</figcaption>',
                ),
            ]
        },
    )
    site = tmp_path / "site"
    assert _build(variant, site) == 0

    html = (site / "read" / "1" / "index.html").read_text(encoding="utf-8")
    assert html.count('id="fig-one"') == 1
    assert '<span id="fig-one"></span><figure' in html
    assert '<a href="#fig-one">figure</a>' in html

    soup = BeautifulSoup(html, "lxml")
    figure = soup.find("figure")
    assert figure is not None
    anchor = figure.find_previous_sibling("span")
    assert anchor is not None
    assert anchor.get("id") == "fig-one"
    caption = figure.find("figcaption")
    assert caption is not None
    assert caption.find("span", id="fig-one") is None


def test_heading_images_and_empty_links_do_not_duplicate(epub_factory, tmp_path: Path):
    variant = epub_factory(
        "heading.epub",
        replacements={
            CH1: [
                (
                    b'<h1 id="ch1">Chapter One</h1>',
                    b'<h1 id="ch1"><a id="chapter-anchor"></a>Chapter One'
                    b'<img src="images/cover.png" alt=""/></h1>',
                ),
                (
                    b"</body>",
                    b'<p><a href="missing.xhtml" id="dead-link"></a></p></body>',
                ),
            ]
        },
    )
    site = tmp_path / "site"
    assert _build(variant, site) == 0
    html = (site / "read" / "1" / "index.html").read_text(encoding="utf-8")
    assert html.count('id="chapter-anchor"') == 1
    assert html.count('id="dead-link"') == 1
    assert "missing.xhtml" not in html
    assert html.count('src="/images/cover.png"') == 2


def test_nested_nav_entries_are_not_duplicated(epub_factory):
    nav = b"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><title>Contents</title></head><body><nav epub:type="toc"><ol>
<li><a href="ch1.xhtml">Chapter One</a><ol>
<li><a href="ch1.xhtml#section-one">A Section</a></li></ol></li>
<li><a href="ch2.xhtml">Chapter Two</a></li>
</ol></nav></body></html>"""
    variant = epub_factory(
        "nav.epub",
        replacements={
            OPF: [
                (
                    b'<item id="ncx"',
                    b'<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" '
                    b'properties="nav"/>\n<item id="ncx"',
                ),
                (b'<itemref idref="ch1"/>', b'<itemref idref="nav"/>\n<itemref idref="ch1"/>'),
            ]
        },
        additions={"OEBPS/nav.xhtml": nav},
    )
    with Epub(variant) as book:
        assert [entry.label for entry in book.toc_flat()] == [
            "Chapter One",
            "A Section",
            "Chapter Two",
        ]


def test_body_level_toc_anchors_survive(epub_factory, tmp_path: Path):
    variant = epub_factory(
        "body-anchor.epub",
        replacements={
            CH1: [
                (
                    b"</body>",
                    b'<p><a href="ch2.xhtml#chapter-two-body">go to chapter two</a></p></body>',
                )
            ],
            CH2: [(b"<body>", b'<body id="chapter-two-body">')],
        },
    )
    site = tmp_path / "site"
    assert _build(variant, site) == 0
    assert 'id="chapter-two-body"' in (site / "read" / "2" / "index.html").read_text(
        encoding="utf-8"
    )


def test_part_and_backmatter_label_detection():
    assert match_key("Man\u2019s Search for Meaning") == match_key("Man's Search for Meaning")
    assert marker_kind("I: Experiences in a Concentration Camp", "I") == "part"
    assert marker_kind("Chapter One", "Chapter One") == "chapter"
    assert marker_kind("II: Logotherapy in a Nutshell", "II") == "part"
    assert label_matches("Preface to the 1992 Edition", FRONT_LABELS)
    assert label_matches("Postscript 1984", BACK_LABELS)
    assert label_matches("Copyright", BACK_LABELS)
    assert not label_matches("The Notebook", BACK_LABELS)


def test_base_path_does_not_rewrite_literal_text(epub_factory, tmp_path: Path):
    variant = epub_factory(
        "literal.epub",
        replacements={
            CH1: [(b"</body>", b'<p><code>href="/docs" src="/img.png"</code></p></body>')]
        },
    )
    site = tmp_path / "site"
    code = main(
        [
            str(variant),
            "-o",
            str(site),
            "--base-path",
            "/shelf",
            "--site-url",
            "https://example.com",
            "--force",
        ]
    )
    assert code == 0
    html = (site / "read" / "1" / "index.html").read_text(encoding="utf-8")
    assert 'href="/docs" src="/img.png"' in html
    assert "/shelf/docs" not in html
    assert 'href="/shelf/assets/styles.css"' in (site / "index.html").read_text(encoding="utf-8")


def test_json_ld_metadata_cannot_break_out_of_script(epub_factory, tmp_path: Path):
    injected = b"<dc:title>A &lt;/script&gt;&lt;script&gt;alert(1)&lt;/script&gt; Book</dc:title>"
    bad = epub_factory(
        "metadata.epub",
        replacements={OPF: [(b"<dc:title>A Tiny Book</dc:title>", injected)]},
    )
    site = tmp_path / "site"
    assert _build(bad, site) == 0
    html = (site / "index.html").read_text(encoding="utf-8")
    assert "</script><script>alert(1)</script>" not in html
    assert "\\u003c/script\\u003e" in html


def test_protocol_relative_links_are_external(epub_factory, tmp_path: Path):
    variant = epub_factory(
        "protocol.epub",
        replacements={CH1: [(b"</body>", b'<p><a href="//example.com/x">external</a></p></body>')]},
    )
    site = tmp_path / "site"
    assert _build(variant, site) == 0
    assert 'href="//example.com/x"' in (site / "read" / "1" / "index.html").read_text(
        encoding="utf-8"
    )


def test_data_uri_image_is_embedded(epub_factory, tmp_path: Path):
    buffer = io.BytesIO()
    Image.new("RGB", (10, 12), (20, 120, 200)).save(buffer, "PNG")
    uri = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
    variant = epub_factory(
        "data.epub",
        replacements={CH1: [(b'src="images/cover.png"', f'src="{uri}"'.encode("ascii"))]},
    )
    site = tmp_path / "site"
    assert _build(variant, site) == 0
    images = list((site / "images").glob("inline-*.png"))
    assert len(images) == 1
    assert images[0].read_bytes().startswith(b"\x89PNG")


def test_escaped_text_that_looks_like_markup_survives(epub_factory, tmp_path: Path):
    variant = epub_factory(
        "escaped.epub",
        replacements={
            CH1: [(b"</body>", b"<p>Use &lt;insert your name&gt; &amp; continue.</p></body>")]
        },
    )
    site = tmp_path / "site"
    assert _build(variant, site) == 0
    html = (site / "read" / "1" / "index.html").read_text(encoding="utf-8")
    assert "Use &lt;insert your name&gt; &amp; continue." in html
    assert "<insert" not in html


def test_malformed_external_href_with_leading_parenthesis_is_repaired(epub_factory, tmp_path: Path):
    variant = epub_factory(
        "external.epub",
        replacements={
            CH1: [
                (
                    b"</body>",
                    b'<p><a href="(https://example.com/wiki/Pipeline(computing)">pipeline</a></p></body>',
                )
            ]
        },
    )
    site = tmp_path / "site"
    assert _build(variant, site) == 0
    html = (site / "read" / "1" / "index.html").read_text(encoding="utf-8")
    assert 'href="https://example.com/wiki/Pipeline(computing)"' in html


def test_missing_footnote_targets_are_repaired(epub_factory, tmp_path: Path):
    variant = epub_factory(
        "notes.epub",
        replacements={
            CH1: [
                (
                    b"</body>",
                    b'<p>Text<a href="#fn1">1</a>.</p>'
                    b'<ol><li>Note<a href="#ffn1">back</a></li></ol></body>',
                )
            ]
        },
    )
    site = tmp_path / "site"
    assert _build(variant, site) == 0
    html = (site / "read" / "1" / "index.html").read_text(encoding="utf-8")
    assert 'id="fn1"' in html
    assert 'id="ffn1"' in html


def test_link_gate_checks_html_and_css_assets(tiny_epub, tmp_path: Path):
    content = tmp_path / "content"
    images = tmp_path / "images"
    site = tmp_path / "site"
    GenericExtractor(tiny_epub, content, images).run()
    render_site(content, site, site_url="http://localhost:8000")

    (site / "assets" / "fonts" / "literata-latin.woff2").unlink()
    result = check_site_links(site)
    assert not result["ok"]
    assert any(item["reason"] == "missing stylesheet asset" for item in result["broken"])


def test_verify_detects_a_dropped_image(tiny_epub, tmp_path: Path):
    content = tmp_path / "content"
    images = tmp_path / "images"
    site = tmp_path / "site"
    GenericExtractor(tiny_epub, content, images).run()
    render_site(content, site, site_url="http://localhost:8000")

    page_path = site / "read" / "1" / "index.html"
    soup = BeautifulSoup(page_path.read_text(encoding="utf-8"), "lxml")
    for image in soup.select("main article img"):
        image.decompose()
    page_path.write_text(str(soup), encoding="utf-8")

    report = verify_site(content, site, verbose=False)
    assert not report["pass"]
    assert any(row["status"] == "IMAGE MISMATCH" for row in report["pages"])


def test_link_gate_rejects_paths_outside_the_site(tiny_epub, tmp_path: Path):
    content = tmp_path / "content"
    images = tmp_path / "images"
    site = tmp_path / "site"
    GenericExtractor(tiny_epub, content, images).run()
    render_site(content, site, site_url="http://localhost:8000")

    (tmp_path / "secret.html").write_text("outside", encoding="utf-8")
    page_path = site / "read" / "1" / "index.html"
    page_html = page_path.read_text(encoding="utf-8")
    page_path.write_text(
        page_html.replace("</main>", '<a href="/../secret.html">escape</a></main>'),
        encoding="utf-8",
    )

    result = check_site_links(site)
    assert not result["ok"]
    assert any(item["href"] == "/../secret.html" for item in result["broken"])


def test_link_gate_requires_base_path_on_root_relative_links(tiny_epub, tmp_path: Path):
    content = tmp_path / "content"
    images = tmp_path / "images"
    site = tmp_path / "site"
    GenericExtractor(tiny_epub, content, images).run()
    render_site(content, site, site_url="https://example.com", base_path="shelf")

    page_path = site / "read" / "1" / "index.html"
    page_html = page_path.read_text(encoding="utf-8")
    page_path.write_text(
        page_html.replace("</main>", '<a href="/assets/styles.css">unprefixed</a></main>'),
        encoding="utf-8",
    )

    result = check_site_links(site, base_path="/shelf")
    assert not result["ok"]
    assert any(item["reason"] == "missing base path" for item in result["broken"])


def test_source_id_that_matches_template_id_builds(tiny_epub, tmp_path: Path):
    import zipfile

    target = tmp_path / "collision.epub"
    with zipfile.ZipFile(tiny_epub) as source, zipfile.ZipFile(target, "w") as dest:
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename == CH1:
                data = data.replace(
                    b'<h1 id="ch1">', b'<p id="main">collision text</p><h1 id="ch1">'
                )
            dest.writestr(item, data)

    site = tmp_path / "site"
    assert _build(target, site) == 0
    assert (site / "read" / "1" / "index.html").exists()


def test_legacy_top_link_still_resolves(epub_factory, tmp_path: Path):
    variant = epub_factory(
        "legacy-top.epub",
        replacements={CH1: [(b"</body>", b'<p><a href="#top">back to top</a></p></body>')]},
    )
    site = tmp_path / "site"
    assert _build(variant, site) == 0
    page = (site / "read" / "1" / "index.html").read_text(encoding="utf-8")
    assert 'id="top"' in page


def test_source_top_id_is_not_duplicated(epub_factory, tmp_path: Path):
    variant = epub_factory(
        "source-top.epub",
        replacements={
            CH1: [
                (
                    b"</body>",
                    b'<p id="top">source target</p><p><a href="#top">back</a></p></body>',
                )
            ]
        },
    )
    site = tmp_path / "site"
    assert _build(variant, site) == 0
    page = (site / "read" / "1" / "index.html").read_text(encoding="utf-8")
    assert page.count('id="top"') == 1


def test_readtime_placeholder_is_replaced(tiny_epub, tmp_path: Path):
    site = tmp_path / "site"
    assert _build(tiny_epub, site) == 0
    page = (site / "read" / "1" / "index.html").read_text(encoding="utf-8")
    assert "<!--READTIME-->" not in page
    assert "min read" in page


def test_generated_site_has_marker_without_note_assets(tiny_epub, tmp_path: Path):
    site = tmp_path / "site"
    assert _build(tiny_epub, site) == 0
    assert (site / SITE_MARKER).is_file()
    assert not (site / "notes.json").exists()
    assert 'name="generator" content="epub2web"' in (site / "index.html").read_text(
        encoding="utf-8"
    )


def test_render_refuses_to_clear_an_unrelated_directory(tiny_epub, tmp_path: Path):
    content = tmp_path / "content"
    images = tmp_path / "images"
    site = tmp_path / "site"
    GenericExtractor(tiny_epub, content, images).run()
    site.mkdir()
    keep = site / "keep.txt"
    keep.write_text("user data", encoding="utf-8")

    with pytest.raises(ValueError, match="refusing to replace"):
        render_site(content, site)

    assert keep.read_text(encoding="utf-8") == "user data"
    render_site(content, site, overwrite=True)
    assert not keep.exists()


def test_extractor_does_not_delete_unrelated_images(tiny_epub, tmp_path: Path):
    content = tmp_path / "content"
    images = tmp_path / "images"
    images.mkdir()
    keep = images / "keep.txt"
    keep.write_text("user data", encoding="utf-8")

    GenericExtractor(tiny_epub, content, images).run()
    assert keep.read_text(encoding="utf-8") == "user data"


def test_svg_sanitizer_removes_smil_and_unsafe_urls():
    payload = b"""<svg xmlns="http://www.w3.org/2000/svg">
      <defs><linearGradient id="g"/></defs>
      <a><animate attributeName="href" values="javascript:alert(1)"/><text>x</text></a>
      <set attributeName="href" to="javascript:alert(1)"/>
      <rect fill="url(#g)" filter="url(javascript:alert(1))" width="10" height="10"/>
    </svg>"""
    output = sanitize_svg(payload).decode("utf-8")

    assert "javascript:" not in output.lower()
    assert "<animate" not in output.lower()
    assert "<set" not in output.lower()
    assert 'fill="url(#g)"' in output
