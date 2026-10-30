"""Typed models shared by extraction, navigation, and rendering.

The extractor works with :class:`PagePlan` objects. They include source DOM
blocks and TOC metadata that never belongs in ``book.json``. The renderer and
verification gates consume the stable dictionary form produced by
:meth:`PagePlan.to_dict`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypedDict

from bs4 import Tag

from .epub import TocEntry


class PageSection(TypedDict):
    level: int
    id: str
    title: str


class PageData(TypedDict, total=False):
    """Stable page shape written to ``book.json`` and read by the renderer."""

    id: str
    type: str
    route: str
    title: str
    display_title: str
    short_title: str
    number: str
    source_files: list[str]
    sections: list[PageSection]
    in_toc: bool
    words: int
    characters: int
    reading_units: float
    figure_count: int
    images: int

    # Added by the renderer for reading progress and navigation.
    reading_minutes: int
    key: str
    chapter_key: str
    chapter_index: int
    chapter_total: int
    progress_start: float
    progress_end: float
    continue_label: str


@dataclass
class PagePart:
    """A contiguous run of source blocks that belongs to one reading page."""

    path: str
    blocks: list[Tag]


@dataclass
class SplitSegment:
    """A document slice starting at a TOC entry, or a leading continuation."""

    entry: TocEntry | None
    blocks: list[Tag]


@dataclass
class PagePlan:
    """An internal reading page before it is serialized to ``book.json``."""

    label: str
    display_title: str
    title: str
    number_label: str
    number_short: str
    source_files: list[str]
    parts: list[PagePart]
    id: str = ""
    route: str = ""
    type: str = "chapter"
    heading: str = ""
    marker: bool = False
    marker_kind: str = ""
    toc_entry: TocEntry | None = None
    toc_fragment: str = ""
    source_text: str = ""
    sections: list[PageSection] = field(default_factory=list)
    words: int = 0
    characters: int = 0
    reading_units: float = 0.0
    figure_count: int = 0
    images: int = 0
    in_toc: bool = True

    def add_part(self, part: PagePart) -> None:
        self.parts.append(part)
        if part.path not in self.source_files:
            self.source_files.append(part.path)

    def text_blocks(self) -> list[Tag]:
        return [block for part in self.parts for block in part.blocks]

    def to_dict(self) -> PageData:
        return {
            "id": self.id,
            "type": self.type,
            "route": self.route,
            "title": self.title,
            "display_title": self.display_title,
            "short_title": self.title,
            "number": self.number_short,
            "source_files": self.source_files,
            "sections": self.sections,
            "in_toc": self.in_toc,
            "words": self.words,
            "characters": self.characters,
            "reading_units": self.reading_units,
            "figure_count": self.figure_count,
            "images": self.images,
        }
