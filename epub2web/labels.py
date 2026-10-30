"""Book-structure labels and chapter title parsing.

These helpers are deliberately independent of EPUB parsing and rendering.
They classify author-provided labels such as "Chapter One", "Prologue", or
"Part II" so page planning and link generation share the same rules.
"""

from __future__ import annotations

import re

from .text import match_key

FRONT_LABELS = {
    "title page",
    "title",
    "copyright",
    "dedication",
    "contents",
    "table of contents",
    "half title",
    "also by",
    "frontispiece",
    "preface",
    "foreword",
    "introduction",
    "prologue",
    "translator's note",
    "editor's note",
    "author's note",
    "cover",
}
BACK_LABELS = {
    "notes",
    "note",
    "endnotes",
    "references",
    "bibliography",
    "index",
    "appendix",
    "acknowledgments",
    "acknowledgements",
    "afterword",
    "glossary",
    "colophon",
    "license",
    "copyright",
    "copyright page",
    "postscript",
    "epilogue",
    "about the author",
    "about the publisher",
    "further reading",
    "permissions",
    "credits",
    "sources",
    "chronology",
}
CHAPTER_RE = re.compile(
    r"^(chapter|part|book)\s+([0-9]+|[IVXLCDM]+|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)"
    r"([.:]?)\s*(.*)$",
    re.I,
)
NUMBER_RE = re.compile(r"^(\d+)([.:)]?)\s+(.*)$")
ROMAN_PART_RE = re.compile(r"^([IVXLCDM]+)\s*[:.\u2014\u2013-]\s*(\S.*)$", re.I)


def label_matches(label: str, labels: set[str]) -> bool:
    key = match_key(label)
    for raw in labels:
        candidate = match_key(raw)
        if key == candidate or key.startswith(candidate + " ") or key.startswith(candidate + ":"):
            return True
    return False


def marker_kind(label: str, heading: str, heading_class: str = "") -> str:
    for text in (label, heading):
        if CHAPTER_RE.match(text):
            return "part" if text.lower().startswith(("part ", "book ")) else "chapter"
    if "chaptertitle" in heading_class:
        return "chapter"
    for text in (label, heading):
        if ROMAN_PART_RE.match(text):
            return "part"
    return ""


def parse_label(label: str) -> tuple[str, str, str]:
    """Return (display_title, number_label, short_title)."""
    label = re.sub(r"\s+", " ", label).strip()
    m = CHAPTER_RE.match(label)
    if m:
        number_label = f"{m.group(1)} {m.group(2)}{m.group(3)}"
        title = m.group(4).strip() or label
        return label, number_label, title
    m = NUMBER_RE.match(label)
    if m:
        number_label = f"{m.group(1)}{m.group(2)}"
        return label, number_label, m.group(3).strip()
    return label, "", label


def number_short(number_label: str) -> str:
    value = number_label.upper()
    for prefix in ("CHAPTER", "PART", "BOOK"):
        if value.startswith(prefix + " "):
            value = value[len(prefix) + 1 :].strip()
            break
    m = re.match(r"([0-9]+|[IVXLCDM]+)", value)
    return m.group(1) if m else ""
