from epub2web.text import normalize_text, slugify, tokens


def test_normalize_whitespace_and_list_markers():
    assert normalize_text("  •  Hello\n\n  1. world  ") == "Hello world"
    assert tokens("Hello, world!") == ["Hello,", "world!"]


def test_slugify():
    assert slugify("A Section: The Beginning!") == "a-section-the-beginning"
