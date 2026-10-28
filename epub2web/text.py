"""Shared text normalization and extraction helpers."""

from __future__ import annotations

import html
import re
import unicodedata

from bs4 import Comment, Doctype, NavigableString, ProcessingInstruction, Tag

BLOCK_TAGS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "caption",
    "dd",
    "div",
    "dl",
    "dt",
    "fieldset",
    "figcaption",
    "figure",
    "footer",
    "form",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "hr",
    "li",
    "main",
    "nav",
    "ol",
    "p",
    "pre",
    "section",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
    "ul",
}


def text_of(root: Tag) -> str:
    parts: list[str] = []

    def walk(node):
        if isinstance(node, (Comment, Doctype, ProcessingInstruction)):
            return
        if isinstance(node, NavigableString):
            parts.append(str(node))
            return
        if not isinstance(node, Tag):
            return
        if node.name in ("script", "style"):
            return
        if node.has_attr("data-chrome") or node.has_attr("data-generated"):
            return
        if node.name == "br":
            parts.append("\n")
            return
        block = node.name in BLOCK_TAGS
        if block:
            parts.append("\n")
        for child in node.children:
            walk(child)
        if block:
            parts.append("\n")

    walk(root)
    return "".join(parts)


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\u00ad", "").replace("\u200b", "").replace("\ufeff", "")
    text = text.replace("\u00a0", " ")
    lines = []
    for line in text.splitlines():
        line = line.strip()
        line = re.sub(r"^[•·]\s*", "", line)
        line = re.sub(r"^\d+\.\s+", "", line)
        if line:
            lines.append(line)
    return re.sub(r"\s+", " ", " ".join(lines)).strip()


_MATCH_TRANSLATION = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
    }
)


def match_key(text: str) -> str:
    """Normalize punctuation for title/label comparisons, never for display."""
    return normalize_text(text).lower().translate(_MATCH_TRANSLATION)


def tokens(text: str) -> list[str]:
    return normalize_text(text).split()


TITLE_SEPARATOR_RE = re.compile(r"\s*[:\u2013\u2014]\s*")
YEAR_RE = re.compile(r"(?<!\d)(\d{4})(?!\d)")


def split_title(title: str) -> tuple[str, str]:
    """Split a display title into (short title, subtitle)."""
    title = (title or "").strip()
    parts = TITLE_SEPARATOR_RE.split(title, maxsplit=1)
    short = parts[0].strip() or title
    subtitle = parts[1].strip() if len(parts) > 1 else ""
    return short, subtitle


def year_from_date(value: str) -> str:
    match = YEAR_RE.search(value or "")
    return match.group(1) if match else ""


def slugify(text: str, fallback: str = "section") -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Za-z0-9\s-]", "", text).strip().lower()
    text = re.sub(r"[\s_]+", "-", text)
    return text[:70].strip("-") or fallback


def inner(el: Tag) -> str:
    """Serialize inline contents, escaping source text that looks like markup.

    BeautifulSoup keeps text such as ``&lt;insert your name&gt;`` as a text
    node. Concatenating ``str(node)`` would put the literal ``<insert ...>``
    into the generated page, where the browser parses it as a real element and
    drops the visible words. Escape text nodes while leaving inline tags as
    HTML.
    """
    parts: list[str] = []
    for child in el.contents:
        if isinstance(child, (Comment, Doctype, ProcessingInstruction)):
            continue
        if isinstance(child, Tag):
            parts.append(str(child))
        else:
            parts.append(html.escape(str(child), quote=False))
    return "".join(parts)


def first_text_node(el: Tag):
    for s in el.find_all(string=True):
        if isinstance(s, NavigableString) and s.strip():
            return s
    return None


def strip_leading(el: Tag, pattern: str):
    s = first_text_node(el)
    if s is None:
        return None
    m = re.match(pattern, str(s))
    if m:
        s.replace_with(str(s)[m.end() :])
    return m
