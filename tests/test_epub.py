from epub2web.epub import Epub


def test_reader(tiny_epub):
    with Epub(tiny_epub) as book:
        assert book.metadata["title"] == "A Tiny Book"
        assert book.metadata["creator"] == "Test Author"
        assert len(book.html_spine()) == 2
        assert book.cover_item is not None
        assert [entry.label for entry in book.toc_flat()] == ["Chapter One", "Chapter Two"]


def test_resolve_decodes_percent_encoded_fragments():
    assert Epub._resolve("OEBPS/content.opf", "ch1.xhtml#A%20Section") == (
        "OEBPS/ch1.xhtml",
        "A Section",
    )
