"""Shared text normalization and extraction helpers."""

from __future__ import annotations

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


def tokens(text: str) -> list[str]:
    return normalize_text(text).split()


def slugify(text: str, fallback: str = "section") -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Za-z0-9\s-]", "", text).strip().lower()
    text = re.sub(r"[\s_]+", "-", text)
    return text[:70].strip("-") or fallback


def inner(el: Tag) -> str:
    return "".join(str(c) for c in el.contents)


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
