"""Render a generic extracted book with the project's browser design."""

from __future__ import annotations

import html
import json
import os
import shutil
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATES = Path(__file__).resolve().parent / "templates"
DEFAULT_STATIC = Path(__file__).resolve().parent / "theme"
TODAY = date.today().isoformat()


def comma(value) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value)


def minutes(words: int) -> int:
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


def route_to_file(dist: Path, route: str) -> Path:
    if route == "/":
        return dist / "index.html"
    return dist / route.strip("/") / "index.html"


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
    ):
        self.content_dir = Path(content_dir)
        self.dist = Path(dist_dir)
        self.templates_dir = Path(templates_dir or DEFAULT_TEMPLATES)
        self.static_dir = Path(static_dir or DEFAULT_STATIC)
        self.site_url = site_url.rstrip("/")
        self.book = json.loads((self.content_dir / "book.json").read_text(encoding="utf-8"))
        self.env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.env.filters["comma"] = comma

    def run(self) -> dict:
        self._prepare()
        self._render()
        self._assets()
        self._sitemap()
        return self.book

    # -- preparation ------------------------------------------------------
    def _prepare(self) -> None:
        meta = self.book.setdefault("meta", {})
        title = meta.get("title") or "Untitled"
        meta.setdefault("short_title", title.split(":")[0].strip() or title)
        meta.setdefault("subtitle", "")
        meta.setdefault("author", "")
        meta.setdefault("publisher", "")
        meta.setdefault("year", (meta.get("date") or "")[:4])
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

        self.pages = self.book.get("pages", [])
        self.page_by_id = {p["id"]: p for p in self.pages}
        self.page_by_route = {p["route"]: p for p in self.pages}
        self.reading_order = self.book.get("reading_order") or [p["id"] for p in self.pages]
        for page in self.pages:
            page.setdefault("reading_minutes", minutes(page.get("words", 0)))
            page.setdefault("display_title", page.get("title", ""))
            page.setdefault("short_title", page.get("title", ""))
            if page.get("type") == "chapter" and page.get("number") and ":" not in page["display_title"]:
                page["display_title"] = f"Chapter {page['number']}: {page['title']}"
            page.setdefault("sections", [])

        self.toc = self.book.get("toc", [])
        self.stats = self.book.get("stats", {})
        self._build_navigation()
        self._build_home()

    def _page_for_href(self, href: str) -> dict | None:
        route = href.split("#", 1)[0]
        return self.page_by_route.get(route)

    def _build_navigation(self) -> None:
        before, chapters, after = [], [], []
        chapter_entries = [e for e in self.toc if e.get("kind") in ("chapter", "part")]
        if chapter_entries:
            first = self.toc.index(chapter_entries[0])
            last = len(self.toc) - 1 - list(reversed(self.toc)).index(chapter_entries[-1])
        else:
            first, last = len(self.toc), len(self.toc)
        before_entries = self.toc[:first]
        after_entries = self.toc[last + 1:]

        for entry in before_entries:
            page = self._page_for_href(entry.get("href", ""))
            before.append({
                "id": page["id"] if page else entry.get("href", "").strip("/"),
                "label": short_label(entry.get("label", "")),
                "href": entry.get("href", ""),
            })

        for entry in chapter_entries:
            page = self._page_for_href(entry.get("href", ""))
            chapters.append({
                "id": page["id"] if page else entry.get("href", "").strip("/"),
                "number": entry.get("number") or (page.get("number", "") if page else ""),
                "label": entry.get("label", ""),
                "href": entry.get("href", ""),
                "sections": [
                    {"label": s.get("label", ""), "href": s.get("href", "")}
                    for s in self.toc
                    if s.get("kind") == "section" and s.get("href", "").split("#")[0] == entry.get("href", "").split("#")[0]
                ],
            })

        for entry in after_entries:
            if entry.get("kind") == "section":
                continue
            page = self._page_for_href(entry.get("href", ""))
            after.append({
                "id": page["id"] if page else entry.get("href", "").strip("/"),
                "label": short_label(entry.get("label", "")),
                "href": entry.get("href", ""),
            })
        self.sidebar = {"before": before, "chapters": chapters, "after": after}

        # Contents page blocks.
        blocks = []
        current = None
        for entry in self.toc:
            if entry.get("kind") == "chapter":
                page = self._page_for_href(entry.get("href", ""))
                current = {
                    "kind": "chapter",
                    "number": entry.get("number") or (page.get("number", "") if page else ""),
                    "label": entry.get("label", ""),
                    "href": entry.get("href", ""),
                    "sections": [],
                    "reading_minutes": page.get("reading_minutes", 0) if page else 0,
                    "generated": entry.get("generated", False),
                }
                blocks.append(current)
            elif entry.get("kind") == "section" and current is not None:
                current["sections"].append({"label": entry.get("label", ""), "href": entry.get("href", "")})
            else:
                blocks.append({
                    "kind": "entry",
                    "label": entry.get("label", ""),
                    "href": entry.get("href", ""),
                    "generated": entry.get("generated", False),
                })
                current = None
        self.toc_blocks = blocks

        self.footer_links = [{"label": "Contents", "href": "/contents/"}]
        for redir in self.pages:
            if redir.get("type") == "frontmatter":
                self.footer_links.append({"label": "Front matter", "href": redir["route"]})
                break
        for wanted in ("notes", "references", "index"):
            for page in self.pages:
                if wanted in page.get("title", "").lower():
                    self.footer_links.append({"label": short_label(page["title"]), "href": page["route"]})
                    break
        seen = set()
        self.footer_links = [l for l in self.footer_links if not (l["href"] in seen or seen.add(l["href"]))]

    def _build_home(self) -> None:
        chapters = [p for p in self.pages if p.get("type") == "chapter"]
        if not chapters:
            chapters = [p for p in self.pages if p.get("type") not in ("frontmatter", "backmatter")]
        for i, page in enumerate(chapters):
            number = page.get("number") or ""
            if number.isdigit():
                display = f"{int(number):02d}"
            elif number:
                display = number
            else:
                display = f"{i + 1:02d}"
            page["display_number"] = display
            page["section_count"] = len(page.get("sections", []))
        self.home_chapters = chapters
        self.home_extras = [
            {"label": short_label(p["title"]), "href": p["route"]}
            for p in self.pages if p.get("type") == "backmatter"
        ]
        self.start_href = next((p["route"] for p in self.pages if p.get("id") == "preface"), "")
        if not self.start_href:
            self.start_href = self.home_chapters[0]["route"] if self.home_chapters else (
                self.pages[0]["route"] if self.pages else "/contents/"
            )
        self.home_heading = "The chapters" if self.home_chapters else "Contents"

        stats = self.stats
        figure_count = stats.get("figures", 0)
        note_count = stats.get("notes", 0)
        chapter_words = stats.get("words") or stats.get("chapter_words", 0)
        chapter_count = stats.get("chapters") or len(self.home_chapters)
        parts = []
        if chapter_count:
            parts.append(f"{chapter_count} chapters")
        if figure_count:
            parts.append(f"{figure_count} figures")
        if note_count:
            parts.append(f"{note_count} notes")
        if chapter_words:
            parts.append(f"{comma(chapter_words)} words")
        if parts:
            self.hero_intro = "The complete text, set for the browser. " + ", ".join(parts) + " — with nothing abridged."
        else:
            self.hero_intro = "The complete text, set for the browser, with nothing abridged."
        self.stats_items = []
        for label, value in (("Chapters", chapter_count), ("Words", chapter_words),
                             ("Figures", figure_count), ("Notes", note_count)):
            if value:
                self.stats_items.append({"label": label, "value": comma(value)})
        self.contents_intro = "Every chapter and section, plus the front and back matter. Every section is linked."
        self.contents_quick = [{"label": "Start reading", "href": self.start_href}]
        for page in self.pages:
            low = page.get("title", "").lower()
            if any(k in low for k in ("notes", "references", "index")):
                self.contents_quick.append({"label": short_label(page["title"]), "href": page["route"]})

    # -- rendering --------------------------------------------------------
    def _render(self) -> None:
        if self.dist.exists():
            shutil.rmtree(self.dist)
        self.dist.mkdir(parents=True)

        meta = self.book["meta"]
        book_title = meta["short_title"]
        cover = meta.get("cover", "")
        cover_webp = meta.get("cover_webp", "")
        book_json_ld = {
            "@context": "https://schema.org",
            "@type": "Book",
            "name": meta["title"],
            "author": {"@type": "Person", "name": meta["author"]} if meta.get("author") else None,
            "publisher": {"@type": "Organization", "name": meta["publisher"]} if meta.get("publisher") else None,
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
        book_json_ld = json.dumps(book_json_ld, ensure_ascii=False)

        # Home
        home_page = {
            "id": "home", "type": "home", "route": "/",
            "title": book_title, "display_title": book_title,
            "short_title": book_title, "reading_minutes": 0,
        }
        home_ctx = dict(
            page=home_page, book=self.book, site_url=self.site_url,
            meta_description=meta.get("description") or f"{meta['title']} by {meta.get('author', '')}.",
            stats=self.stats, home_chapters=self.home_chapters, home_extras=self.home_extras,
            hero_intro=self.hero_intro, stats_items=self.stats_items, start_href=self.start_href,
            home_heading=self.home_heading, book_json_ld=book_json_ld,
            sidebar=self.sidebar, footer_links=self.footer_links, prev=None, next=None,
            fragment="", toc_blocks=[], is_reading=False, show_sidebar=False, wide=False,
            pagefind_ignore=True, cover_width=meta.get("cover_width", 438),
            cover_height=meta.get("cover_height", 662), search_label="Static full-text",
            contents_intro=self.contents_intro, contents_quick=self.contents_quick,
        )
        write_route(self.dist, "/", self.env.get_template("home.html").render(**home_ctx))

        # Contents
        contents_page = {
            "id": "contents", "type": "contents", "route": "/contents/",
            "title": "Contents", "display_title": "Contents",
            "short_title": "Contents", "reading_minutes": 0,
        }
        contents_ctx = dict(
            page=contents_page, book=self.book, site_url=self.site_url,
            meta_description=f"Contents of {meta['title']} by {meta.get('author', '')}.",
            stats=self.stats, home_chapters=self.home_chapters, home_extras=self.home_extras,
            hero_intro=self.hero_intro, stats_items=self.stats_items, start_href=self.start_href,
            home_heading=self.home_heading, book_json_ld=book_json_ld,
            sidebar=self.sidebar, footer_links=self.footer_links, prev=None, next=None,
            fragment="", toc_blocks=self.toc_blocks, is_reading=False, show_sidebar=False,
            wide=True, pagefind_ignore=False, contents_intro=self.contents_intro,
            contents_quick=self.contents_quick, search_label="Static full-text",
        )
        write_route(self.dist, "/contents/", self.env.get_template("contents.html").render(**contents_ctx))

        # Reading pages
        for index, page in enumerate(self.pages):
            fragment_path = self.content_dir / "pages" / f"{page['id']}.html"
            if not fragment_path.exists():
                continue
            fragment = fragment_path.read_text(encoding="utf-8")
            fragment = fragment.replace('<span class="readtime">Calculating…</span>',
                                        f'{page["reading_minutes"]} min read')
            pos = self.reading_order.index(page["id"]) if page["id"] in self.reading_order else -1
            prev_page = self.page_by_id[self.reading_order[pos - 1]] if pos > 0 else None
            next_page = self.page_by_id[self.reading_order[pos + 1]] if 0 <= pos < len(self.reading_order) - 1 else None
            wide = page.get("title", "").lower().strip() == "index" or page.get("type") == "index"
            show_sidebar = not wide
            desc = (f"{page.get('title', '')} from {meta['title']}"
                    + (f" by {meta['author']}" if meta.get("author") else "") + ".")
            ctx = dict(
                page=page, book=self.book, site_url=self.site_url, meta_description=desc,
                stats=self.stats, home_chapters=self.home_chapters, home_extras=self.home_extras,
                hero_intro=self.hero_intro, stats_items=self.stats_items, start_href=self.start_href,
                home_heading=self.home_heading, book_json_ld=book_json_ld,
                sidebar=self.sidebar, footer_links=self.footer_links, prev=prev_page, next=next_page,
                fragment=fragment, toc_blocks=self.toc_blocks, is_reading=True,
                show_sidebar=show_sidebar, wide=wide, pagefind_ignore=False,
                contents_intro=self.contents_intro, contents_quick=self.contents_quick,
                search_label="Static full-text", cover_width=meta.get("cover_width", 438),
                cover_height=meta.get("cover_height", 662),
            )
            write_route(self.dist, page["route"], self.env.get_template("page.html").render(**ctx))

        # 404
        p404 = {"id": "404", "type": "404", "route": "/404", "title": "Page not found",
                "display_title": "Page not found", "short_title": "Page not found", "reading_minutes": 0}
        ctx = dict(
            page=p404, book=self.book, site_url=self.site_url, meta_description="Page not found.",
            stats=self.stats, home_chapters=self.home_chapters, home_extras=self.home_extras,
            hero_intro=self.hero_intro, stats_items=self.stats_items, start_href=self.start_href,
            home_heading=self.home_heading, book_json_ld=book_json_ld, sidebar=self.sidebar,
            footer_links=self.footer_links, prev=None, next=None, fragment="", toc_blocks=[],
            is_reading=False, show_sidebar=False, wide=False, pagefind_ignore=True,
            contents_intro=self.contents_intro, contents_quick=self.contents_quick,
            search_label="Static full-text", cover_width=meta.get("cover_width", 438),
            cover_height=meta.get("cover_height", 662),
        )
        (self.dist / "404.html").write_text(self.env.get_template("404.html").render(**ctx), encoding="utf-8")

    # -- assets -----------------------------------------------------------
    def _assets(self) -> None:
        assets = self.static_dir / "assets"
        if assets.exists():
            shutil.copytree(assets, self.dist / "assets", dirs_exist_ok=True)
        favicon = self.static_dir / "favicon.svg"
        if favicon.exists():
            shutil.copyfile(favicon, self.dist / "favicon.svg")
        images = self.content_dir.parent / "images"
        if images.exists():
            shutil.copytree(images, self.dist / "images", dirs_exist_ok=True)
        notes = self.content_dir / "notes-popover.json"
        if notes.exists():
            shutil.copyfile(notes, self.dist / "notes.json")

    def _sitemap(self) -> None:
        routes = ["/", "/contents/"] + [p["route"] for p in self.pages]
        urls = "\n".join(
            f"  <url><loc>{html.escape(self.site_url + r)}</loc><lastmod>{TODAY}</lastmod></url>"
            for r in routes
        )
        (self.dist / "sitemap.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{urls}\n</urlset>\n", encoding="utf-8"
        )
        (self.dist / "robots.txt").write_text(
            f"User-agent: *\nAllow: /\nSitemap: {self.site_url}/sitemap.xml\n", encoding="utf-8"
        )


def render_site(content_dir, dist_dir, templates_dir=None, static_dir=None, site_url=None) -> dict:
    renderer = SiteRenderer(
        content_dir=content_dir,
        dist_dir=dist_dir,
        templates_dir=templates_dir,
        static_dir=static_dir,
        site_url=site_url or os.environ.get("SITE_URL", "http://localhost:4321"),
    )
    return renderer.run()
