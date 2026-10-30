from bs4 import BeautifulSoup
from epub2web.converter import PageConverter
from epub2web.dom import direct_page_blocks
from epub2web.epub import Epub
from epub2web.models import PagePart, PagePlan


class StubBook:
    """Only the path resolver is needed for converter-only tests."""

    _resolve = staticmethod(Epub._resolve)


def make_page(body: str, *, page_type: str = "chapter") -> PagePlan:
    path = "OEBPS/ch1.xhtml"
    blocks = direct_page_blocks(BeautifulSoup(body, "lxml").body)
    page = PagePlan(
        label="Chapter One",
        display_title="Chapter One",
        title="Chapter One",
        number_label="Chapter One",
        number_short="1",
        source_files=[path],
        parts=[PagePart(path, blocks)],
    )
    page.id = "page-1"
    page.route = "/read/1/"
    page.type = page_type
    return page


def make_converter() -> PageConverter:
    return PageConverter(
        book=StubBook(),
        images={
            "OEBPS/pic.png": {
                "name": "pic.png",
                "webp": "pic.webp",
                "width": 40,
                "height": 60,
            }
        },
        route_by_path={"OEBPS/ch1.xhtml": "/read/1/"},
        route_by_target={},
    )


def test_converter_handles_common_block_types():
    body = """
    <body>
      <h1 id="ch1">Chapter One</h1>
      <p>Hello <em>world</em>.</p>
      <h2 id="section-one">A Section</h2>
      <p class="image"><img src="pic.png" alt="A picture"></p>
      <p class="caption">A caption.</p>
      <ul><li>One</li><li>Two</li></ul>
      <p class="quote">A quoted line.</p>
      <table><tr><td>Cell</td></tr></table>
      <p class="index">Alpha entry</p>
      <p><a id="empty-anchor"></a></p>
    </body>
    """
    fragment, sections = make_converter().convert(make_page(body))

    assert 'id="ch1"' in fragment
    assert "Chapter One" in fragment
    assert "Hello <em>world</em>." in fragment
    assert 'id="section-one"' in fragment
    assert sections == [{"level": 2, "id": "section-one", "title": "A Section"}]
    assert '<figure class="figure"' in fragment
    assert 'src="/images/pic.png"' in fragment
    assert 'srcset="/images/pic.webp"' in fragment
    assert "A caption." in fragment
    assert '<ul class="book-list">' in fragment
    assert '<blockquote class="book-quote quote-epigraph">' in fragment
    assert '<div class="table-wrap">' in fragment
    assert 'class="index-anchor"' in fragment
    assert 'id="index-a"' in fragment
    assert 'class="index-nav"' in fragment
    assert 'id="empty-anchor"' in fragment


def test_converter_merges_quote_and_bullet_groups():
    body = """
    <body>
      <h1 id="ch1">Chapter One</h1>
      <p class="quote">First quoted line.</p>
      <p class="epigraph">Second quoted line.</p>
      <p class="bullet">• First bullet</p>
      <p class="bullet">• Second bullet</p>
    </body>
    """
    fragment, _ = make_converter().convert(make_page(body))

    assert fragment.count('<blockquote class="book-quote quote-epigraph">') == 1
    assert "First quoted line." in fragment
    assert "Second quoted line." in fragment
    assert fragment.count('<ul class="book-list">') == 1
    assert "First bullet" in fragment
    assert "Second bullet" in fragment
