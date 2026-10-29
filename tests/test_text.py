from bs4 import BeautifulSoup
from epub2web.text import (
    inner,
    normalize_text,
    reading_units,
    slugify,
    split_title,
    tokens,
    year_from_date,
)


def test_normalize_whitespace_and_list_markers():
    assert normalize_text("  •  Hello\n\n  1. world  ") == "Hello world"
    assert tokens("Hello, world!") == ["Hello,", "world!"]


def test_slugify():
    assert slugify("A Section: The Beginning!") == "a-section-the-beginning"
    assert slugify("设计", fallback="") == ""
    assert slugify("", fallback="book") == "book"


def test_reading_units_for_unspaced_scripts():
    assert reading_units("Hello world") == 2
    assert reading_units("你好世界") == 2
    assert reading_units("สวัสดี") == 3
    assert reading_units("Hello 世界") == 2


def test_inner_escapes_text_that_looks_like_markup():
    soup = BeautifulSoup("<p>Use &lt;insert your name&gt; &amp; continue.</p>", "lxml")
    assert inner(soup.p) == "Use &lt;insert your name&gt; &amp; continue."


def test_inner_keeps_inline_markup():
    soup = BeautifulSoup("<p>Use <em>this</em> &lt;value&gt;.</p>", "lxml")
    assert inner(soup.p) == "Use <em>this</em> &lt;value&gt;."


def test_split_title_uses_colon_and_dashes():
    assert split_title("Book: A Novel") == ("Book", "A Novel")
    assert split_title("Book \u2014 A Novel") == ("Book", "A Novel")
    assert split_title("Book \u2013 A Novel") == ("Book", "A Novel")
    assert split_title("Untitled") == ("Untitled", "")


def test_year_from_date_handles_non_iso_dates():
    assert year_from_date("2013") == "2013"
    assert year_from_date("2013-05-01") == "2013"
    assert year_from_date("January 1, 2013") == "2013"
    assert year_from_date("") == ""
