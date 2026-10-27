from bs4 import BeautifulSoup
from epub2web.text import inner, normalize_text, slugify, tokens


def test_normalize_whitespace_and_list_markers():
    assert normalize_text("  •  Hello\n\n  1. world  ") == "Hello world"
    assert tokens("Hello, world!") == ["Hello,", "world!"]


def test_slugify():
    assert slugify("A Section: The Beginning!") == "a-section-the-beginning"
    assert slugify("设计", fallback="") == ""
    assert slugify("", fallback="book") == "book"


def test_inner_escapes_text_that_looks_like_markup():
    soup = BeautifulSoup("<p>Use &lt;insert your name&gt; &amp; continue.</p>", "lxml")
    assert inner(soup.p) == "Use &lt;insert your name&gt; &amp; continue."


def test_inner_keeps_inline_markup():
    soup = BeautifulSoup("<p>Use <em>this</em> &lt;value&gt;.</p>", "lxml")
    assert inner(soup.p) == "Use <em>this</em> &lt;value&gt;."
