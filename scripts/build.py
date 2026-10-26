#!/usr/bin/env python3
"""Render the extracted book as a static website."""

from __future__ import annotations

import html
import json
import os
import shutil
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
DIST = ROOT / "dist"
STATIC = ROOT / "static"
PUBLIC = ROOT / "public"
SITE_URL = os.environ.get("SITE_URL", "http://localhost:4321").rstrip("/")
TODAY = date.today().isoformat()

env = Environment(
    loader=FileSystemLoader(ROOT / "templates"),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def comma(value) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value)


def minutes(words: int) -> int:
    return max(1, round(words / 230))


env.filters["comma"] = comma
env.filters["minutes"] = minutes


def route_file(route: str) -> Path:
    if route == "/":
        return DIST / "index.html"
    return DIST / route.strip("/") / "index.html"


def write_route(route: str, content: str) -> None:
    path = route_file(route)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> None:
    book = json.loads((CONTENT / "book.json").read_text(encoding="utf-8"))
    book["meta"]["short_title"] = "The Design of Everyday Things"
    book["meta"]["display_title"] = "The Design of Everyday Things"

    pages = {p["id"]: p for p in book["pages"]}
    page_by_id = pages
    reading_order = book["reading_order"]

    # Attach reading time and a browser title to every page.
    for page in book["pages"]:
        page["reading_minutes"] = minutes(page.get("words", 0))
        if page["type"] == "chapter":
            page["display_title"] = f"Chapter {page['number']}: {page['title']}"
        else:
            page["display_title"] = page["title"]

    # --- Sidebar ---------------------------------------------------------
    sidebar = {
        "before": [
            {"id": "front-matter", "label": "Front matter", "href": "/front-matter/"},
            {"id": "preface", "label": "Preface", "href": "/preface/"},
        ],
        "chapters": [],
        "after": [],
    }
    current_chapter = None
    for entry in book["toc"]:
        if entry["kind"] == "chapter":
            current_chapter = {
                "id": f"chapter-{entry['number']}",
                "number": entry["number"],
                "label": entry["label"],
                "href": entry["href"],
                "sections": [],
            }
            sidebar["chapters"].append(current_chapter)
        elif entry["kind"] == "section" and current_chapter is not None:
            current_chapter["sections"].append({
                "label": entry["label"],
                "href": entry["href"],
            })
        elif entry["kind"] == "entry":
            href = entry["href"]
            if href.startswith("/preface/"):
                continue
            if href.startswith("/acknowledgments/"):
                sidebar["after"].append({"id": "acknowledgments", "label": "Acknowledgments", "href": href})
            elif href.startswith("/notes/"):
                sidebar["after"].append({"id": "notes", "label": "Notes", "href": href})
            elif href.startswith("/references/"):
                sidebar["after"].append({"id": "references", "label": "References", "href": href})
            elif href.startswith("/index-of-terms/"):
                sidebar["after"].append({"id": "index", "label": "Index", "href": href})

    # --- Contents blocks -------------------------------------------------
    toc_blocks = []
    current_block = None
    for entry in book["toc"]:
        if entry["kind"] == "chapter":
            page = page_by_id.get(f"chapter-{entry['number']}", {})
            current_block = {
                "kind": "chapter",
                "number": entry["number"],
                "label": entry["label"],
                "href": entry["href"],
                "sections": [],
                "reading_minutes": page.get("reading_minutes", 0),
                "generated": entry.get("generated", False),
            }
            toc_blocks.append(current_block)
        elif entry["kind"] == "section" and current_block is not None:
            current_block["sections"].append({
                "label": entry["label"],
                "href": entry["href"],
            })
        else:
            toc_blocks.append({
                "kind": "entry",
                "label": entry["label"],
                "href": entry["href"],
                "generated": entry.get("generated", False),
            })
            current_block = None

    # --- Home ------------------------------------------------------------
    home_chapters = []
    for file, number, _title in [
        ("Chapter001.html", 1, ""), ("Chapter002.html", 2, ""), ("Chapter003.html", 3, ""),
        ("Chapter004.html", 4, ""), ("Chapter005.html", 5, ""), ("Chapter006.html", 6, ""),
        ("Chapter007.html", 7, ""),
    ]:
        page = page_by_id[f"chapter-{number}"]
        home_chapters.append({
            "number": number,
            "title": page["title"],
            "route": page["route"],
            "section_count": len(page.get("sections", [])),
            "reading_minutes": page["reading_minutes"],
        })

    book_json_ld = json.dumps({
        "@context": "https://schema.org",
        "@type": "Book",
        "name": book["meta"]["title"],
        "author": {"@type": "Person", "name": book["meta"]["author"]},
        "publisher": {"@type": "Organization", "name": "Basic Books"},
        "datePublished": "2013",
        "isbn": book["meta"]["isbn"],
        "inLanguage": "en",
        "numberOfPages": 366,
        "description": book["meta"].get("description", ""),
        "image": f"{SITE_URL}/images/cover.jpg",
        "url": f"{SITE_URL}/",
    }, ensure_ascii=False)

    # --- Render ----------------------------------------------------------
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)

    for page in book["pages"]:
        route = page["route"]
        page_id = page["id"]

        if page_id == "home":
            page["title"] = "The Design of Everyday Things"
            meta_description = (
                "The complete text of Don Norman's The Design of Everyday Things, "
                "revised and expanded edition, set for the browser."
            )
            template = env.get_template("home.html")
            ctx = dict(
                page=page, book=book, site_url=SITE_URL, meta_description=meta_description,
                stats=book["stats"], home_chapters=home_chapters, book_json_ld=book_json_ld,
                sidebar=sidebar, prev=None, next=None, fragment="", toc_blocks=[],
                is_reading=False, show_sidebar=False, wide=False, pagefind_ignore=True,
            )
            write_route(route, template.render(**ctx))
            continue

        if page_id == "contents":
            meta_description = (
                "Full contents of The Design of Everyday Things by Don Norman: "
                "chapters, sections, notes, references, and index."
            )
            template = env.get_template("contents.html")
            ctx = dict(
                page=page, book=book, site_url=SITE_URL, meta_description=meta_description,
                stats=book["stats"], home_chapters=home_chapters, book_json_ld=book_json_ld,
                sidebar=sidebar, prev=None, next=None, fragment="", toc_blocks=toc_blocks,
                is_reading=False, show_sidebar=False, wide=True, pagefind_ignore=False,
            )
            write_route(route, template.render(**ctx))
            continue

        # Reading pages.
        fragment = (CONTENT / "pages" / f"{page_id}.html").read_text(encoding="utf-8")
        read_label = f'{page["reading_minutes"]} min read'
        fragment = fragment.replace('<span class="readtime">Calculating…</span>', read_label)

        pos = reading_order.index(page_id)
        prev_page = page_by_id[reading_order[pos - 1]] if pos > 0 else None
        next_page = page_by_id[reading_order[pos + 1]] if pos + 1 < len(reading_order) else None

        show_sidebar = page_id != "index"
        wide = page_id == "index"

        if page["type"] == "chapter":
            meta_description = (
                f"Chapter {page['number']}: {page['title']} from Don Norman's "
                "The Design of Everyday Things. Read the complete text."
            )
        elif page_id == "notes":
            meta_description = (
                "General readings and notes for The Design of Everyday Things by Don Norman."
            )
        elif page_id == "references":
            meta_description = "The full reference list for The Design of Everyday Things by Don Norman."
        elif page_id == "index":
            meta_description = "The full index to The Design of Everyday Things by Don Norman."
        else:
            meta_description = (
                f"{page['title']} — the complete text of Don Norman's The Design of Everyday Things, "
                "set for the browser."
            )

        template = env.get_template("page.html")
        ctx = dict(
            page=page, book=book, site_url=SITE_URL, meta_description=meta_description,
            stats=book["stats"], home_chapters=home_chapters, book_json_ld=book_json_ld,
            sidebar=sidebar, prev=prev_page, next=next_page, fragment=fragment, toc_blocks=toc_blocks,
            is_reading=True, show_sidebar=show_sidebar, wide=wide, pagefind_ignore=False,
        )
        write_route(route, template.render(**ctx))

    # 404
    page_404 = {
        "id": "404", "type": "404", "route": "/404", "title": "Page not found",
        "short_title": "Page not found", "display_title": "Page not found",
        "reading_minutes": 0,
    }
    ctx = dict(
        page=page_404, book=book, site_url=SITE_URL,
        meta_description="Page not found.",
        stats=book["stats"], home_chapters=[], book_json_ld=book_json_ld,
        sidebar=sidebar, prev=None, next=None, fragment="", toc_blocks=[],
        is_reading=False, show_sidebar=False, wide=False, pagefind_ignore=True,
    )
    (DIST / "404.html").write_text(env.get_template("404.html").render(**ctx), encoding="utf-8")

    # --- Assets ----------------------------------------------------------
    shutil.copytree(STATIC / "assets", DIST / "assets", dirs_exist_ok=True)
    shutil.copytree(PUBLIC / "images", DIST / "images", dirs_exist_ok=True)
    shutil.copyfile(STATIC / "favicon.svg", DIST / "favicon.svg")
    (DIST / "notes.json").write_text(
        (CONTENT / "notes-popover.json").read_text(encoding="utf-8"), encoding="utf-8"
    )

    # --- Sitemap / robots ------------------------------------------------
    routes = ["/", "/contents/", "/front-matter/", "/preface/",
              *[f"/chapters/{n}/" for n in range(1, 8)],
              "/acknowledgments/", "/notes/", "/references/", "/index-of-terms/"]
    urls = "\n".join(
        f"  <url><loc>{html.escape(SITE_URL + r)}</loc><lastmod>{TODAY}</lastmod></url>"
        for r in routes
    )
    (DIST / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n</urlset>\n",
        encoding="utf-8",
    )
    (DIST / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8"
    )

    print(f"Built {len(book['pages'])} pages + 404 in {DIST}")
    print(f"  reading time (chapters): {sum(p['reading_minutes'] for p in home_chapters)} min")
    print(f"  site url: {SITE_URL}")


if __name__ == "__main__":
    main()
