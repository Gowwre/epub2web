"""Render a generic extracted book with the project's browser design."""

from __future__ import annotations

import hashlib
import html
import json
import logging
import re
import shutil
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, Comment, Tag
from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import __version__
from .fonts import (
    detect_scripts,
    is_rtl_language,
    load_font_manifest,
    render_font_css,
    select_font_faces,
    uses_character_metrics,
)
from .paths import normalize_base_path, route_to_file
from .progress import ProgressCallback, report
from .text import normalize_text, slugify, split_title, text_of, year_from_date

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATES = Path(__file__).resolve().parent / "templates"
DEFAULT_STATIC = Path(__file__).resolve().parent / "theme"
SITE_MARKER = ".epub2web"


def comma(value) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value)


def minutes(words: float) -> int:
    return max(1, round(words / 230))


def short_label(title: str) -> str:
    low = title.lower().strip()
    if low == "index":
        return "Index"
    if "acknowledg" in low:
        return "Acknowledgments"
    if "notes" in low:
        return "Notes"
    if "reference" in low or "bibliograph" in low:
        return "References"
    if "preface" in low:
        return "Preface"
    if low in ("contents", "table of contents"):
        return "Contents"
    return title


def write_route(dist: Path, route: str, content: str) -> None:
    path = route_to_file(dist, route)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class SiteRenderer:
    def __init__(
        self,
        content_dir: str | Path,
        dist_dir: str | Path,
        templates_dir: str | Path | None = None,
        static_dir: str | Path | None = None,
        site_url: str = "http://localhost:4321",
        base_path: str = "",
        progress: ProgressCallback | None = None,
        overwrite: bool = False,
    ):
        self.content_dir = Path(content_dir)
        self.dist = Path(dist_dir)
        self.overwrite = overwrite
        self.templates_dir = Path(templates_dir or DEFAULT_TEMPLATES)
        self.static_dir = Path(static_dir or DEFAULT_STATIC)
        self.base_path = normalize_base_path(base_path)
        self.site_url = site_url.rstrip("/")
        self.progress = progress
        self.font_faces: list[dict] = []
        self.cjk_regions: list[str] = []
        self.text_direction = "ltr"
        if self.base_path:
            site_path = urlsplit(self.site_url).path.rstrip("/")
            if not (site_path == self.base_path or site_path.endswith(self.base_path)):
                self.site_url += self.base_path
        resolved_dist = self.dist.resolve()
        if self.content_dir.resolve() == resolved_dist or (
            self.content_dir.resolve().is_relative_to(resolved_dist)
        ):
            raise ValueError("the output directory must not contain the content directory")
        if resolved_dist in (
            Path.home().resolve(),
            Path.cwd().resolve(),
            Path(resolved_dist.anchor),
        ):
            raise ValueError(f"refusing to render into protected directory: {resolved_dist}")
        if resolved_dist.exists() and not resolved_dist.is_dir():
            raise ValueError(f"output path exists and is not a directory: {resolved_dist}")
        if (
            resolved_dist.exists()
            and any(resolved_dist.iterdir())
            and not (self.overwrite or (resolved_dist / SITE_MARKER).is_file())
        ):
            raise ValueError(
                f"refusing to replace non-epub2web directory: {resolved_dist} "
                "(pass overwrite=True to allow it)"
            )
        self.book = json.loads((self.content_dir / "book.json").read_text(encoding="utf-8"))
        self.env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.env.filters["comma"] = comma
        self.env.globals["base_path"] = self.base_path

    def _report(self, phase: str, label: str, current: int, total: int) -> None:
        report(self.progress, phase, label, current, total)

    def run(self) -> dict:
        self._prepare()
        logger.info(
            "rendering site",
            extra={
                "output": str(self.dist),
                "pages": len(self.pages),
                "base_path": self.base_path,
            },
        )
        self._report("render-pages", "Building pages", 0, len(self.pages))
        self._render()
        self._report("render-pages", "Building pages", len(self.pages), len(self.pages))
        self._report("render-assets", "Finishing site", 0, 1)
        self._apply_base_path()
        self._write_search_index()
        self._select_fonts()
        self._assets()
        self._sitemap()
        self._report("render-assets", "Finishing site", 1, 1)
        logger.info(
            "site rendered",
            extra={
                "output": str(self.dist),
                "search_entries": self.search_entries,
            },
        )
        return self.book

    # -- preparation ------------------------------------------------------
    def _prepare(self) -> None:
        meta = self.book.setdefault("meta", {})
        title = meta.get("title") or "Untitled"
        meta.setdefault("short_title", split_title(title)[0])
        meta.setdefault("subtitle", "")
        meta.setdefault("author", "")
        meta.setdefault("publisher", "")
        meta.setdefault("year", year_from_date(meta.get("date") or ""))
        meta.setdefault("date", "")
        meta.setdefault("isbn", "")
        meta.setdefault("language", "en")
        meta.setdefault("description", "")
        meta.setdefault("rights", "")
        meta.setdefault("cover", "")
        meta.setdefault("cover_webp", "")
        meta.setdefault("edition", "")
        meta.setdefault("source", "EPUB")
        meta.setdefault("title_lines", [])
        meta.setdefault("reading_id", "")
        self.text_direction = "rtl" if is_rtl_language(meta.get("language", "")) else "ltr"

        self.pages = self.book.get("pages", [])
        self.page_by_id = {p["id"]: p for p in self.pages}
        self.page_by_route = {p["route"]: p for p in self.pages}
        self.reading_order = self.book.get("reading_order") or [p["id"] for p in self.pages]
        for page in self.pages:
            length = page.get("reading_units", page.get("words", 0))
            page.setdefault("reading_minutes", minutes(length))
            page.setdefault("display_title", page.get("title", ""))
            page.setdefault("short_title", page.get("title", ""))
            if (
                page.get("type") == "chapter"
                and page.get("number")
                and ":" not in page["display_title"]
            ):
                page["display_title"] = f"Chapter {page['number']}: {page['title']}"
            page.setdefault("sections", [])

        self._prepare_progress()

        self.toc = self.book.get("toc", [])
        self.toc_tree = self.book.get("toc_tree") or self._tree_from_flat_toc()
        self._decorate_toc_tree(self.toc_tree)
        self.stats = self.book.get("stats", {})
        self._build_navigation()
        self._build_home()

    def _fallback_reading_id(self) -> str:
        """Derive a stable id for content directories without a source hash."""
        payload = json.dumps(
            [
                {
                    "id": page.get("id", ""),
                    "route": page.get("route", ""),
                    "sources": page.get("source_files", []),
                    "title": page.get("title", ""),
                }
                for page in self.pages
            ],
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _chapter_key(page: dict) -> str:
        kind = page.get("type") or "page"
        number = str(page.get("number") or "").strip()
        if kind in ("chapter", "part") and number:
            slug = slugify(number, fallback="")
            if slug:
                return f"{kind}-{slug}"
        title = page.get("title") or page.get("display_title") or page.get("id") or "page"
        return f"{kind}-{slugify(title)}"

    @staticmethod
    def _continue_label(page: dict) -> str:
        if page.get("type") == "chapter":
            number = str(page.get("number") or "").strip()
            if number.isdigit():
                number = str(int(number))
            if not number:
                number = str(page.get("chapter_index") or "")
            if number:
                return f"Chapter {number}"
        return short_label(page.get("title", "")) or page.get("display_title", "")

    @staticmethod
    def _reading_weight(page: dict) -> int:
        value = page.get("reading_units", page.get("words", 0)) or 0
        try:
            return max(1, round(float(value)))
        except (TypeError, ValueError):
            return 1

    def _prepare_progress(self) -> None:
        """Add stable page keys, chapter positions, and whole-book offsets."""
        meta = self.book["meta"]
        reading_id = str(meta.get("reading_id") or "").strip()
        if not reading_id:
            reading_id = self._fallback_reading_id()
        meta["reading_id"] = reading_id

        chapter_total = sum(1 for page in self.pages if page.get("type") == "chapter")
        chapter_index = 0
        total_weight = sum(self._reading_weight(page) for page in self.pages) or 1
        cumulative = 0
        for page in self.pages:
            sources = page.get("source_files") or [page.get("id", "")]
            payload = json.dumps(sources, ensure_ascii=False)
            page["key"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
            page["chapter_key"] = self._chapter_key(page)
            if page.get("type") == "chapter":
                chapter_index += 1
                page["chapter_index"] = chapter_index
            else:
                page["chapter_index"] = 0
            page["chapter_total"] = chapter_total
            page["progress_start"] = round(cumulative / total_weight, 6)
            cumulative += self._reading_weight(page)
            page["progress_end"] = round(cumulative / total_weight, 6)
            page["continue_label"] = self._continue_label(page)

        self.reading_map = [
            {
                "key": page["key"],
                "chapterKey": page["chapter_key"],
                "route": page["route"],
                "label": page["continue_label"],
            }
            for page in self.pages
        ]

    def _page_for_href(self, href: str) -> dict | None:
        route = href.split("#", 1)[0]
        return self.page_by_route.get(route)

    def _tree_from_flat_toc(self) -> list[dict]:
        """Rebuild a display tree from a flat TOC written by older versions."""
        tree: list[dict] = []
        for entry in self.toc:
            item = dict(entry)
            item["children"] = []
            page = self._page_for_href(item.get("href", ""))
            item["page_id"] = page["id"] if page else item.get("page_id", "")
            if item.get("kind") == "section" and tree:
                tree[-1]["children"].append(item)
            else:
                tree.append(item)
        return tree

    def _decorate_toc_tree(self, items: list[dict]) -> None:
        for item in items:
            page = self.page_by_id.get(item.get("page_id", ""))
            item["id"] = item.get("page_id", "")
            item["children"] = item.get("children") or []
            item["reading_minutes"] = page.get("reading_minutes", 0) if page else 0
            self._decorate_toc_tree(item["children"])

    def _build_navigation(self) -> None:
        before, chapters, after = [], [], []
        for item in self.toc_tree:
            page = self.page_by_id.get(item.get("page_id", ""))
            kind = item.get("kind")
            if kind in ("part", "chapter"):
                chapters.append(item)
            elif page is not None and page.get("type") == "frontmatter":
                before.append(
                    {
                        **item,
                        "label": short_label(item.get("label", "")),
                    }
                )
            elif (page is not None and page.get("type") == "backmatter") or kind == "entry":
                after.append(
                    {
                        **item,
                        "label": short_label(item.get("label", "")),
                    }
                )
            else:
                chapters.append(item)
        self.sidebar = {"before": before, "chapters": chapters, "after": after}
        self.toc_blocks = self.toc_tree

        links = [{"label": "Contents", "href": "/contents/"}]
        for page in self.pages:
            if page.get("type") == "frontmatter":
                links.append({"label": "Front matter", "href": page["route"]})
                break
        for wanted in ("notes", "references", "index"):
            for page in self.pages:
                if wanted in page.get("title", "").lower():
                    links.append({"label": short_label(page["title"]), "href": page["route"]})
                    break
        seen: set[str] = set()
        self.footer_links = []
        for link in links:
            if link["href"] in seen:
                continue
            seen.add(link["href"])
            self.footer_links.append(link)

    def _build_home(self) -> None:
        chapters: list[dict] = []

        def collect(items: list[dict]) -> None:
            for item in items:
                if item.get("kind") in ("chapter", "part"):
                    chapters.append(
                        {
                            "route": item.get("href", ""),
                            "title": item.get("label", ""),
                            "number": item.get("number", ""),
                            "reading_minutes": item.get("reading_minutes", 0),
                            "section_count": len(item.get("children", [])),
                        }
                    )
                collect(item.get("children", []))

        collect(self.toc_tree)
        if not chapters:
            pages = [p for p in self.pages if p.get("type") == "chapter" and p.get("in_toc", True)]
            if not pages:
                pages = [p for p in self.pages if p.get("type") == "chapter"]
            if not pages:
                pages = [
                    p for p in self.pages if p.get("type") not in ("frontmatter", "backmatter")
                ]
            chapters = [
                {
                    "route": page["route"],
                    "title": page["title"],
                    "number": page.get("number", ""),
                    "reading_minutes": page.get("reading_minutes", 0),
                    "section_count": len(page.get("sections", [])),
                }
                for page in pages
            ]
        for i, chapter in enumerate(chapters):
            number = str(chapter.get("number") or "")
            if number.isdigit():
                display = f"{int(number):02d}"
            elif number:
                display = number
            else:
                display = f"{i + 1:02d}"
            chapter["display_number"] = display
        self.home_chapters = chapters
        self.home_extras = [
            {"label": short_label(p["title"]), "href": p["route"]}
            for p in self.pages
            if p.get("type") == "backmatter" and p.get("in_toc", True)
        ]
        self.start_href = next(
            (
                p["route"]
                for p in self.pages
                if any(
                    word in p.get("title", "").lower()
                    for word in ("prologue", "preface", "foreword", "introduction")
                )
            ),
            "",
        )
        if not self.start_href:
            self.start_href = (
                self.home_chapters[0]["route"]
                if self.home_chapters
                else (self.pages[0]["route"] if self.pages else "/contents/")
            )
        self.home_heading = "The chapters" if self.home_chapters else "Contents"

        stats = self.stats
        figure_count = stats.get("figures", 0)
        character_metrics = uses_character_metrics(self.book["meta"].get("language", ""))
        if character_metrics:
            chapter_length = stats.get("chapter_characters") or stats.get("characters", 0)
            length_label = "characters"
        else:
            chapter_length = stats.get("chapter_words") or stats.get("words", 0)
            length_label = "words"
        chapter_count = stats.get("chapters") or len(self.home_chapters)
        parts = []
        if chapter_count:
            parts.append(f"{chapter_count} chapters")
        if figure_count:
            parts.append(f"{figure_count} figures")
        if chapter_length:
            parts.append(f"{comma(chapter_length)} {length_label}")
        if parts:
            self.hero_intro = (
                "The complete text, set for the browser. "
                + ", ".join(parts)
                + " — with nothing abridged."
            )
        else:
            self.hero_intro = "The complete text, set for the browser, with nothing abridged."
        self.stats_items = []
        for label, value in (
            ("Chapters", chapter_count),
            (length_label.title(), chapter_length),
            ("Figures", figure_count),
        ):
            if value:
                self.stats_items.append({"label": label, "value": comma(value)})
        self.contents_intro = (
            "Every chapter and section, plus the front and back matter. Every section is linked."
        )
        self.contents_quick = [{"label": "Start reading", "href": self.start_href}]
        for page in self.pages:
            low = page.get("title", "").lower()
            if any(k in low for k in ("notes", "references", "index")):
                self.contents_quick.append(
                    {"label": short_label(page["title"]), "href": page["route"]}
                )

    # -- rendering --------------------------------------------------------
    def _base_context(
        self,
        page: dict,
        meta_description: str,
        *,
        is_reading: bool = False,
        show_sidebar: bool = False,
        wide: bool = False,
        prev: dict | None = None,
        next: dict | None = None,
        legacy_anchors: set[str] | None = None,
    ) -> dict:
        return {
            "page": page,
            "book": self.book,
            "site_url": self.site_url,
            "text_direction": self.text_direction,
            "meta_description": meta_description,
            "sidebar": self.sidebar,
            "footer_links": self.footer_links,
            "prev": prev,
            "next": next,
            "is_reading": is_reading,
            "show_sidebar": show_sidebar,
            "wide": wide,
            "legacy_anchors": legacy_anchors if legacy_anchors is not None else {"top", "main"},
        }

    def _render(self) -> None:
        if self.dist.exists():
            shutil.rmtree(self.dist)
        self.dist.mkdir(parents=True)
        (self.dist / SITE_MARKER).write_text(f"epub2web {__version__}\n", encoding="utf-8")

        meta = self.book["meta"]
        book_title = meta["short_title"]
        cover = meta.get("cover", "")
        book_json_ld = {
            "@context": "https://schema.org",
            "@type": "Book",
            "name": meta["title"],
            "author": {"@type": "Person", "name": meta["author"]} if meta.get("author") else None,
            "publisher": {"@type": "Organization", "name": meta["publisher"]}
            if meta.get("publisher")
            else None,
            "datePublished": meta.get("year", ""),
            "inLanguage": meta.get("language", "en"),
            "description": meta.get("description", ""),
            "url": f"{self.site_url}/",
        }
        if meta.get("isbn"):
            book_json_ld["isbn"] = meta["isbn"]
        if cover:
            book_json_ld["image"] = f"{self.site_url}/images/{cover}"
        book_json_ld = {k: v for k, v in book_json_ld.items() if v not in (None, "")}
        book_json_ld = (
            json.dumps(book_json_ld, ensure_ascii=False)
            .replace("&", "\\u0026")
            .replace("<", "\\u003c")
            .replace(">", "\\u003e")
            .replace("\u2028", "\\u2028")
            .replace("\u2029", "\\u2029")
        )

        # Home
        home_page = {
            "id": "home",
            "type": "home",
            "route": "/",
            "title": book_title,
            "display_title": book_title,
            "short_title": book_title,
            "reading_minutes": 0,
        }
        home_description = meta.get("description") or (
            f"{meta['title']} by {meta['author']}." if meta.get("author") else f"{meta['title']}."
        )
        home_ctx = self._base_context(home_page, home_description)
        home_ctx.update(
            home_chapters=self.home_chapters,
            home_extras=self.home_extras,
            hero_intro=self.hero_intro,
            stats_items=self.stats_items,
            start_href=self.start_href,
            home_heading=self.home_heading,
            book_json_ld=book_json_ld,
            reading_map=self.reading_map,
            cover_width=meta.get("cover_width", 438),
            cover_height=meta.get("cover_height", 662),
            search_label="Built-in full-text index",
        )
        write_route(self.dist, "/", self.env.get_template("home.html").render(**home_ctx))

        # Contents
        contents_page = {
            "id": "contents",
            "type": "contents",
            "route": "/contents/",
            "title": "Contents",
            "display_title": "Contents",
            "short_title": "Contents",
            "reading_minutes": 0,
        }
        contents_description = (
            f"Contents of {meta['title']} by {meta['author']}."
            if meta.get("author")
            else f"Contents of {meta['title']}."
        )
        contents_ctx = self._base_context(contents_page, contents_description, wide=True)
        contents_ctx.update(
            toc_blocks=self.toc_blocks,
            contents_intro=self.contents_intro,
            contents_quick=self.contents_quick,
        )
        write_route(
            self.dist, "/contents/", self.env.get_template("contents.html").render(**contents_ctx)
        )

        # Reading pages
        total_pages = len(self.pages)
        for page_index, page in enumerate(self.pages, 1):
            fragment_path = self.content_dir / "pages" / f"{page['id']}.html"
            if not fragment_path.exists():
                self._report("render-pages", "Building pages", page_index, total_pages)
                continue
            fragment = fragment_path.read_text(encoding="utf-8")
            readtime = f"{page['reading_minutes']} min read"
            if page.get("chapter_index") and page.get("chapter_total"):
                readtime = (
                    f"Chapter {page['chapter_index']} of {page['chapter_total']} · {readtime}"
                )
            fragment = fragment.replace("<!--READTIME-->", readtime)
            pos = self.reading_order.index(page["id"]) if page["id"] in self.reading_order else -1
            prev_page = self.page_by_id.get(self.reading_order[pos - 1]) if pos > 0 else None
            next_page = (
                self.page_by_id.get(self.reading_order[pos + 1])
                if 0 <= pos < len(self.reading_order) - 1
                else None
            )
            wide = page.get("title", "").lower().strip() == "index" or page.get("type") == "index"
            show_sidebar = not wide
            desc = (
                f"{page.get('title', '')} from {meta['title']}"
                + (f" by {meta['author']}" if meta.get("author") else "")
                + "."
            )
            ctx = self._base_context(
                page,
                desc,
                is_reading=True,
                show_sidebar=show_sidebar,
                wide=wide,
                prev=prev_page,
                next=next_page,
            )
            ctx["fragment"] = fragment
            ctx["legacy_anchors"] = {
                name
                for name in ("top", "main")
                if re.search(rf'\bid=["\']{re.escape(name)}["\']', fragment) is None
            }
            write_route(self.dist, page["route"], self.env.get_template("page.html").render(**ctx))
            self._report("render-pages", "Building pages", page_index, total_pages)

        # 404
        p404 = {
            "id": "404",
            "type": "404",
            "route": "/404",
            "title": "Page not found",
            "display_title": "Page not found",
            "short_title": "Page not found",
            "reading_minutes": 0,
        }
        ctx = self._base_context(p404, "Page not found.")
        (self.dist / "404.html").write_text(
            self.env.get_template("404.html").render(**ctx), encoding="utf-8"
        )

    def _apply_base_path(self) -> None:
        """Prefix root-relative URLs when the site is hosted under a subpath."""
        if not self.base_path:
            return

        def prefix(value: str) -> str:
            if (
                not value.startswith("/")
                or value.startswith("//")
                or value == self.base_path
                or value.startswith(self.base_path + "/")
                or value.startswith(self.base_path + "?")
            ):
                return value
            return self.base_path + value

        for path in self.dist.rglob("*.html"):
            soup = BeautifulSoup(path.read_text(encoding="utf-8"), "lxml")
            for tag in soup.find_all(True):
                for attribute in ("href", "src", "poster"):
                    value = tag.get(attribute)
                    if isinstance(value, str):
                        tag[attribute] = prefix(value)
                srcset = tag.get("srcset")
                if isinstance(srcset, str):
                    items = []
                    for item in srcset.split(","):
                        bits = item.strip().split()
                        if bits:
                            bits[0] = prefix(bits[0])
                        items.append(" ".join(bits))
                    tag["srcset"] = ", ".join(items)
            path.write_text(str(soup), encoding="utf-8")

    def _write_search_index(self) -> None:
        """Build a dependency-free search index from the rendered sections."""
        entries: list[dict] = []

        def add_entry(title: str, chapter: str, href: str, parts: list[str]) -> None:
            text = normalize_text(" ".join(parts))
            if len(text) >= 20:
                entries.append(
                    {
                        "title": title,
                        "chapter": chapter,
                        "href": href,
                        "text": text,
                    }
                )

        for page in self.pages:
            path = self.content_dir / "pages" / f"{page['id']}.html"
            if not path.exists():
                continue
            soup = BeautifulSoup(path.read_text(encoding="utf-8"), "lxml")
            root = soup.body or soup
            page_title = page.get("title", "")
            current_title = page_title
            current_href = page["route"]
            buffer: list[str] = []

            for node in root.children:
                if not isinstance(node, Tag):
                    if not isinstance(node, Comment) and str(node).strip():
                        buffer.append(str(node))
                    continue
                if node.name in ("h1", "h2", "h3", "h4"):
                    add_entry(current_title, page_title, current_href, buffer)
                    buffer = []
                    current_title = node.get_text(" ", strip=True) or page_title
                    anchor = node.get("id") if node.name != "h1" else None
                    current_href = page["route"] + (f"#{anchor}" if anchor else "")
                else:
                    buffer.append(text_of(node))
            add_entry(current_title, page_title, current_href, buffer)

        (self.dist / "search-index.json").write_text(
            json.dumps(entries, ensure_ascii=False),
            encoding="utf-8",
        )
        self.search_entries = len(entries)

    # -- assets -----------------------------------------------------------
    def _select_fonts(self) -> None:
        """Choose and record the font subsets needed by this book."""
        meta = self.book["meta"]
        parts = [
            str(meta.get(key, ""))
            for key in ("title", "short_title", "subtitle", "author", "publisher", "description")
        ]
        parts.extend(str(entry.get("label", "")) for entry in self.toc)
        for page in self.pages:
            parts.extend(str(page.get(key, "")) for key in ("title", "display_title"))
            path = self.content_dir / "pages" / f"{page['id']}.html"
            if not path.exists():
                continue
            soup = BeautifulSoup(path.read_text(encoding="utf-8"), "lxml")
            parts.append(soup.get_text(" "))
        text = "\n".join(parts)
        scripts = detect_scripts(text)
        codepoints = {ord(character) for character in text if ord(character) >= 0x0300}
        manifest_path = self.static_dir / "assets" / "fonts" / "font-manifest.json"
        manifest = load_font_manifest(manifest_path) if manifest_path.is_file() else None
        self.font_faces, self.cjk_regions = select_font_faces(
            scripts, str(meta.get("language", "")), codepoints, manifest=manifest
        )
        logger.info(
            "fonts selected",
            extra={
                "scripts": sorted(scripts),
                "cjk_regions": self.cjk_regions,
                "fonts": len(self.font_faces),
            },
        )

    def _assets(self) -> None:
        assets = self.static_dir / "assets"
        if assets.exists():
            shutil.copytree(
                assets,
                self.dist / "assets",
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("fonts", "fonts.css"),
            )
        font_dir = self.dist / "assets" / "fonts"
        for face in self.font_faces:
            source = self.static_dir / "assets" / "fonts" / face["file"]
            if not source.is_file():
                source = DEFAULT_STATIC / "assets" / "fonts" / face["file"]
            if not source.is_file():
                raise ValueError(f"missing bundled font: {source}")
            destination = font_dir / face["file"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        (self.dist / "assets" / "fonts.css").write_text(
            render_font_css(self.font_faces), encoding="utf-8"
        )
        favicon = self.static_dir / "favicon.svg"
        if favicon.exists():
            shutil.copyfile(favicon, self.dist / "favicon.svg")
        images = self.content_dir.parent / "images"
        if images.exists():
            shutil.copytree(images, self.dist / "images", dirs_exist_ok=True)

    def _sitemap(self) -> None:
        routes = ["/", "/contents/"] + [p["route"] for p in self.pages]
        today = date.today().isoformat()
        urls = "\n".join(
            f"  <url><loc>{html.escape(self.site_url + r)}</loc><lastmod>{today}</lastmod></url>"
            for r in routes
        )
        (self.dist / "sitemap.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{urls}\n</urlset>\n",
            encoding="utf-8",
        )
        allow = self.base_path or "/"
        (self.dist / "robots.txt").write_text(
            f"User-agent: *\nAllow: {allow}\nSitemap: {self.site_url}/sitemap.xml\n",
            encoding="utf-8",
        )


def render_site(
    content_dir,
    dist_dir,
    templates_dir=None,
    static_dir=None,
    site_url=None,
    base_path="",
    progress: ProgressCallback | None = None,
    overwrite: bool = False,
) -> dict:
    renderer = SiteRenderer(
        content_dir=content_dir,
        dist_dir=dist_dir,
        templates_dir=templates_dir,
        static_dir=static_dir,
        site_url=site_url or "http://localhost:4321",
        base_path=base_path,
        progress=progress,
        overwrite=overwrite,
    )
    return renderer.run()
