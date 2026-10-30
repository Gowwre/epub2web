"""Build the website navigation model from the EPUB table of contents.

The EPUB TOC describes destinations as ``document#fragment``. The site also
needs page routes, chapter numbers, and display-only sections. Keeping those
two models separate makes the conversion easier to reason about:

* :class:`~epub2web.epub.TocEntry` is the source navigation tree.
* :class:`SiteTocItem` is the tree rendered in the contents page and sidebar.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .epub import TocEntry


@dataclass
class SiteTocItem:
    """One entry in the generated table of contents."""

    kind: str
    label: str
    href: str
    page_id: str
    number: str = ""
    generated: bool = False
    children: list[SiteTocItem] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "number": self.number,
            "label": self.label,
            "href": self.href,
            "page_id": self.page_id,
            "generated": self.generated,
            "children": [child.as_dict() for child in self.children],
        }


@dataclass
class SiteToc:
    """The generated navigation tree plus the flat data used by templates."""

    tree: list[SiteTocItem]
    flat: list[dict]
    chapter_count: int
    page_ids: set[str]


class SiteTocBuilder:
    """Project the EPUB TOC onto the reading pages produced by extraction.

    The builder is intentionally read-only: it consumes page plans and route
    maps, then returns a separate presentation tree. Pages that the EPUB TOC
    does not reference are left out of the navigation, but remain in the
    reading order.
    """

    def __init__(
        self,
        toc_entries: list[TocEntry],
        pages: list[dict],
        route_by_path: dict[str, str],
        route_by_target: dict[tuple[str, str], str],
    ):
        self.toc_entries = toc_entries
        self.pages = pages
        self.route_by_path = route_by_path
        self.route_by_target = route_by_target
        self.page_by_route = {page["route"]: page for page in pages}
        self.page_by_id = {page["id"]: page for page in pages}
        self._claimed_pages: set[str] = set()

    def build(self) -> SiteToc:
        tree = self._from_epub_toc() if self.toc_entries else []
        if not self._has_chapter(tree):
            tree = self._from_pages()
        self._add_heading_sections(tree)
        self._assign_chapter_numbers(tree)

        flat = self._flatten(tree)
        chapter_items = [item for item in flat if item["kind"] == "chapter"]
        if not chapter_items:
            chapter_items = [item for item in flat if item["kind"] == "part"]
        return SiteToc(
            tree=tree,
            flat=flat,
            chapter_count=len(chapter_items),
            page_ids=self._referenced_page_ids(tree),
        )

    # -- source TOC -------------------------------------------------------
    def _from_epub_toc(self) -> list[SiteTocItem]:
        self._claimed_pages = set()
        return self._build_level(self.toc_entries)

    def _build_level(self, entries: list[TocEntry]) -> list[SiteTocItem]:
        result: list[SiteTocItem] = []
        for entry in entries:
            page = self._page_for_entry(entry)
            if page is None:
                # A broken parent should not hide valid child destinations.
                result.extend(self._build_level(entry.children))
                continue

            if page["id"] not in self._claimed_pages and page.get("toc_entry") is entry:
                self._claimed_pages.add(page["id"])
                item = self._page_item(page)
            else:
                item = self._section_item(page, entry.label, entry.fragment)
            item.children = self._build_level(entry.children)
            result.append(item)
        return result

    def _page_for_entry(self, entry: TocEntry) -> dict | None:
        if entry.path and entry.fragment:
            route = self.route_by_target.get((entry.path, entry.fragment))
            return self.page_by_route.get(route) if route else None
        route = self.route_by_path.get(entry.path) if entry.path else None
        return self.page_by_route.get(route)

    # -- page fallback ----------------------------------------------------
    def _from_pages(self) -> list[SiteTocItem]:
        result: list[SiteTocItem] = []
        for page in self.pages:
            item = self._page_item(page)
            item.children = [
                self._section_item(page, section["title"], section["id"])
                for section in page["sections"]
            ]
            result.append(item)
        return result

    # -- item construction ------------------------------------------------
    def _page_item(self, page: dict) -> SiteTocItem:
        if page["type"] == "chapter":
            kind = "chapter"
            label = page["title"]
            number = page["number_short"]
        elif page["type"] == "part":
            kind = "part"
            label = page["display_title"]
            number = ""
        else:
            kind = "entry"
            label = page["display_title"]
            number = ""
        return SiteTocItem(
            kind=kind,
            label=label,
            href=page["route"],
            page_id=page["id"],
            number=number,
        )

    def _section_item(self, page: dict, label: str, fragment: str) -> SiteTocItem:
        href = f"{page['route']}#{fragment}" if fragment else page["route"]
        return SiteTocItem(
            kind="section",
            label=label,
            href=href,
            page_id=page["id"],
        )

    # -- post-processing --------------------------------------------------
    @staticmethod
    def _has_chapter(items: list[SiteTocItem]) -> bool:
        return any(
            item.kind in ("chapter", "part") or SiteTocBuilder._has_chapter(item.children)
            for item in items
        )

    def _add_heading_sections(self, items: list[SiteTocItem]) -> None:
        """Use heading-derived sections only when the EPUB TOC has none."""
        for item in items:
            if not item.children and item.kind in ("chapter", "part"):
                page = self.page_by_id.get(item.page_id)
                if page is not None:
                    item.children = [
                        self._section_item(page, section["title"], section["id"])
                        for section in page["sections"]
                    ]
            self._add_heading_sections(item.children)

    def _assign_chapter_numbers(self, items: list[SiteTocItem], start: int = 1) -> int:
        number = start
        for item in items:
            if item.kind == "chapter":
                if not item.number:
                    item.number = str(number)
                number += 1
            number = self._assign_chapter_numbers(item.children, number)
        return number

    def _flatten(self, items: list[SiteTocItem], depth: int = 0) -> list[dict]:
        result: list[dict] = []
        for item in items:
            data = item.as_dict()
            data.pop("children")
            data["depth"] = depth
            result.append(data)
            result.extend(self._flatten(item.children, depth + 1))
        return result

    @staticmethod
    def _referenced_page_ids(items: list[SiteTocItem]) -> set[str]:
        result: set[str] = set()
        for item in items:
            if item.page_id:
                result.add(item.page_id)
            result.update(SiteTocBuilder._referenced_page_ids(item.children))
        return result
