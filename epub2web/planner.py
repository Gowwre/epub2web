"""Plan reading pages from cleaned spine documents and EPUB TOC targets."""

from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup, Tag

from .dom import (
    class_names,
    direct_page_blocks,
    first_heading_in_blocks,
    has_visible_content,
    heading_text,
    split_block_at,
)
from .epub import Epub, ManifestItem, TocEntry
from .labels import (
    BACK_LABELS,
    FRONT_LABELS,
    label_matches,
    marker_kind,
    number_short,
    parse_label,
)
from .models import PagePart, PagePlan, SplitSegment
from .text import match_key, normalize_text, text_of


class PagePlanner:
    """Build reading pages without depending on rendering or output paths."""

    def __init__(
        self,
        book: Epub,
        items: list[ManifestItem],
        cleaned: dict[str, BeautifulSoup],
        cover_info: dict | None,
    ):
        self.book = book
        self.items = items
        self.cleaned = cleaned
        self.cover_info = cover_info

    def plan(self) -> list[PagePlan]:
        """Turn spine documents into reading pages at their TOC boundaries.

        Content before the first TOC anchor continues the previous page. That
        keeps chapters that span more than one EPUB file together.
        """
        pages: list[PagePlan] = []
        previous_page: PagePlan | None = None
        for item in self.items:
            soup = self.cleaned.get(item.path)
            if soup is None or soup.body is None:
                continue
            text = soup.body.get_text(" ", strip=True)
            imgs = soup.body.find_all("img")
            if not text and not imgs:
                continue
            # Skip a cover wrapper that contains only the cover image.
            if self.cover_info and len(imgs) == 1 and not text:
                src = imgs[0].get("src", "")
                path, _ = self.book._resolve(item.path, src)
                if self.book.cover_item and path == self.book.cover_item.path:
                    continue

            blocks = direct_page_blocks(soup.body)
            if not blocks:
                continue
            entries = self._split_entries(item.path)
            segments = self._split_segments(item, soup, entries) if entries else None
            if segments is None:
                page = self._new_page(
                    item.path,
                    self._fallback_label(item, soup, blocks),
                    blocks,
                    toc_entry=self._first_nav_entry(item.path),
                )
                pages.append(page)
                previous_page = page
                continue

            pending_lead: list[Tag] = []
            for segment in segments:
                segment_blocks = segment.blocks
                entry = segment.entry
                if entry is None:
                    if previous_page is not None:
                        previous_page.add_part(PagePart(item.path, segment_blocks))
                    else:
                        pending_lead.extend(segment_blocks)
                    continue
                if pending_lead:
                    segment_blocks = [*pending_lead, *segment_blocks]
                    pending_lead = []
                page = self._new_page(item.path, entry.label, segment_blocks, toc_entry=entry)
                pages.append(page)
                previous_page = page
            if pending_lead:
                if previous_page is not None:
                    previous_page.add_part(PagePart(item.path, pending_lead))
                else:
                    fallback = (
                        entries[0].label if entries else self._fallback_label(item, soup, blocks)
                    )
                    page = self._new_page(
                        item.path,
                        fallback,
                        pending_lead,
                        toc_entry=entries[0] if entries else self._first_nav_entry(item.path),
                    )
                    pages.append(page)
                    previous_page = page

        for page in pages:
            page_blocks = page.text_blocks()
            page.source_text = normalize_text(" ".join(text_of(block) for block in page_blocks))
            heading = first_heading_in_blocks(page_blocks)
            page.heading = heading_text(heading) if heading else ""
            heading_class = class_names(heading) if heading else ""
            page.marker_kind = marker_kind(page.label, page.heading, heading_class)
            page.marker = bool(page.marker_kind)
            page.words = len(page.source_text.split())

        chapter_start = next((i for i, page in enumerate(pages) if page.marker), None)
        if chapter_start is None:
            book_title = match_key(self.book.metadata.get("title", ""))
            for i, page in enumerate(pages):
                if label_matches(page.label, FRONT_LABELS):
                    continue
                if book_title and match_key(page.label) == book_title:
                    continue
                chapter_start = i
                break
        if chapter_start is None:
            chapter_start = 0

        chapter_markers = [i for i, page in enumerate(pages) if page.marker_kind == "chapter"]
        last_chapter = max(chapter_markers, default=-1)
        back_start = len(pages)
        search_from = max(chapter_start, last_chapter + 1)
        for i, page in enumerate(pages):
            if i >= search_from and label_matches(page.label, BACK_LABELS):
                back_start = i
                break
        if chapter_markers and back_start == len(pages):
            back_start = last_chapter + 1

        for i, page in enumerate(pages):
            page.id = f"page-{i + 1}"
            page.route = f"/read/{i + 1}/"
            kind = page.marker_kind
            if i < chapter_start:
                page.type = "frontmatter"
            elif i >= back_start:
                page.type = "backmatter"
            elif kind == "part":
                page.type = "part"
            elif kind == "chapter":
                page.type = "chapter"
            elif page.words < 50 and page.label.isupper():
                # Short all-caps divider pages are part headings.
                page.type = "part"
            else:
                page.type = "chapter"
        return pages

    def _split_entries(self, path: str) -> list[TocEntry]:
        """Top-level TOC entries that start a new page inside one spine file."""
        result = []
        seen: set[str] = set()
        for entry in self.book.toc:
            if entry.path != path or not entry.fragment or entry.fragment in seen:
                continue
            seen.add(entry.fragment)
            result.append(entry)
        return result

    def _split_segments(
        self,
        item: ManifestItem,
        soup: BeautifulSoup,
        entries: list[TocEntry],
    ) -> list[SplitSegment] | None:
        """Cut a spine document into segments at its TOC anchor points.

        A segment keeps the DOM blocks it owns. The leading segment (content
        before the first anchor) is returned with ``entry=None`` so the caller
        can append it to the previous reading page. The split is refused if it
        would not account for all of the document's text.
        """
        body = soup.body
        blocks = direct_page_blocks(body)
        if not blocks:
            return None
        entry_by_id = {entry.fragment: entry for entry in entries}
        segments: list[SplitSegment] = []
        current_entry: TocEntry | None = None
        current_blocks: list[Tag] = []

        for block in blocks:
            matched_entry = None
            matched_anchor = None
            for tag in [block, *block.find_all(id=True)]:
                anchor_id = tag.get("id")
                if anchor_id in entry_by_id:
                    matched_entry = entry_by_id[anchor_id]
                    matched_anchor = soup.find(id=anchor_id)
                    break
            if matched_entry is None or matched_anchor is None:
                current_blocks.append(block)
                continue

            halves = split_block_at(block, matched_anchor)
            if (
                halves is not None
                and has_visible_content(halves[0])
                and has_visible_content(halves[1])
            ):
                before, after = halves
                current_blocks.append(before)
                if current_blocks:
                    segments.append(SplitSegment(current_entry, current_blocks))
                current_blocks = [after]
                current_entry = matched_entry
            else:
                if current_blocks:
                    segments.append(SplitSegment(current_entry, current_blocks))
                current_blocks = [block]
                current_entry = matched_entry

        if current_blocks:
            segments.append(SplitSegment(current_entry, current_blocks))

        if not any(segment.entry is not None for segment in segments):
            return None
        full_text = normalize_text(text_of(body))
        segment_text = normalize_text(
            " ".join(text_of(block) for segment in segments for block in segment.blocks)
        )
        if full_text != segment_text:
            return None
        return segments

    def _fallback_label(
        self,
        item: ManifestItem,
        soup: BeautifulSoup,
        blocks: list[Tag],
    ) -> str:
        entry = self._first_nav_entry(item.path)
        if entry is not None:
            return entry.label
        heading = first_heading_in_blocks(blocks)
        return (
            (heading_text(heading) if heading else "")
            or self.book._text(soup.find("title"))
            or Path(item.path).stem
        )

    def _first_nav_entry(self, path: str) -> TocEntry | None:
        return next(
            (entry for entry in self.book.toc_flat() if entry.path == path),
            None,
        )

    def _new_page(
        self,
        path: str,
        label: str,
        blocks: list[Tag],
        toc_entry: TocEntry | None = None,
    ) -> PagePlan:
        display, number_label, title = parse_label(label)
        return PagePlan(
            label=label,
            display_title=display,
            title=title,
            number_label=number_label,
            number_short=number_short(number_label),
            source_files=[path],
            parts=[PagePart(path, blocks)],
            toc_entry=toc_entry,
            toc_fragment=toc_entry.fragment if toc_entry else "",
        )
