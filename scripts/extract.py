"""Turn the EPUB into semantic HTML fragments and a source-text baseline.

Design rule: this script never rewrites prose. It only:
  * drops print-only artefacts (running heads, page anchors, spacer spans, drop caps),
  * maps the EPUB's class soup onto semantic HTML,
  * groups figures / captions / lists / quotes,
  * rewrites links to the new routes.

Every text block is also exported to content/source-text.json so verify.py can
prove that the built pages contain the same words in the same order.
"""

from __future__ import annotations

import html
import io
import json
import os
import re
import shutil
import sys
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, Tag
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from epub2web.text import (  # noqa: E402
    first_text_node,
    inner,
    normalize_text,
    slugify,
    strip_leading,
    text_of,
)

EPUB = (
    Path(os.environ["EPUB_PATH"])
    if os.environ.get("EPUB_PATH")
    else next(iter(sorted(ROOT.glob("*.epub"))), None)
)
CONTENT = Path(os.environ.get("CONTENT_DIR", ROOT / "content"))
PAGES = CONTENT / "pages"
PUBLIC_IMAGES = Path(os.environ.get("IMAGES_DIR", ROOT / "public" / "images"))

if EPUB is None:
    raise SystemExit("No .epub found in the project root.")

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

CHAPTERS = [
    ("Chapter001.html", 1, "The Psychopathology of Everyday Things"),
    ("Chapter002.html", 2, "The Psychology of Everyday Actions"),
    ("Chapter003.html", 3, "Knowledge in the Head and in the World"),
    ("Chapter004.html", 4, "Knowing What to Do: Constraints, Discoverability, and Feedback"),
    ("Chapter005.html", 5, "Human Error? No, Bad Design"),
    ("Chapter006.html", 6, "Design Thinking"),
    ("Chapter007.html", 7, "Design in the World of Business"),
]

ROUTES = {
    "Cover.html": "/",
    "Halftitle.html": "/front-matter/#halftitle",
    "Fm.html": "/front-matter/#also-by",
    "Title.html": "/front-matter/#title",
    "Copyright.html": "/front-matter/#copyright",
    "Dedication.html": "/front-matter/#dedication",
    "Contents.html": "/contents/",
    "Preface.html": "/preface/",
    "Acknowledgments.html": "/acknowledgments/",
    "Notes.html": "/notes/",
    "References.html": "/references/",
    "Index.html": "/index-of-terms/",
}
for _file, _num, _title in CHAPTERS:
    ROUTES[_file] = f"/chapters/{_num}/"

SPINE = [
    "Cover.html",
    "Halftitle.html",
    "Fm.html",
    "Title.html",
    "Copyright.html",
    "Dedication.html",
    "Contents.html",
    "Preface.html",
    *[c[0] for c in CHAPTERS],
    "Acknowledgments.html",
    "Notes.html",
    "References.html",
    "Index.html",
]

FRONT_MATTER_FILES = [
    "Halftitle.html",
    "Fm.html",
    "Title.html",
    "Copyright.html",
    "Dedication.html",
]


def rewrite_href(href: str) -> str:
    if not href:
        return href
    if href.startswith("//"):
        return href
    parts = urlsplit(href)
    if parts.scheme.lower() in ("http", "https", "mailto"):
        return href
    if parts.scheme:
        return href
    if not parts.path:
        frag = parts.fragment
        if frag.startswith("notes") and frag[5:].isdigit():
            frag = "n" + frag[5:]
        return f"#{frag}" if frag else href

    name = parts.path.rsplit("/", 1)[-1]
    base = ROUTES.get(name)
    if base is None:
        return href

    frag = parts.fragment
    if name == "Contents.html" and frag.startswith("r"):
        frag = ""
    elif name == "Notes.html" and frag.startswith("notes") and frag[5:].isdigit():
        frag = "n" + frag[5:]
    if frag:
        base = base.split("#", 1)[0]
        return f"{base}#{frag}"
    return base


# ---------------------------------------------------------------------------
# Cleaning
# ---------------------------------------------------------------------------


def parse_html(data: bytes) -> BeautifulSoup:
    return BeautifulSoup(data, "lxml")


def clean_soup(soup: BeautifulSoup, note_map: dict[str, dict] | None = None) -> BeautifulSoup:
    body = soup.body
    if body is None:
        return soup

    # Print-only elements. `.hide` is display:none in the EPUB; `.dropcap`
    # is a decorative ornament, not a letter. If a hidden element ever carries
    # real text, fail loudly rather than silently losing it.
    for el in body.select(".hide"):
        hidden = el.get_text(" ", strip=True)
        if hidden:
            raise ValueError(f"Refusing to drop hidden text: {hidden[:100]!r}")
        el.decompose()
    for el in body.select(".dropcap"):
        el.decompose()
    for el in body.find_all("hr"):
        el.decompose()
    for el in body.select("div.hr-top"):
        el.decompose()

    # Spacer spans carry layout whitespace. Turn them into a real space so
    # words like "FIGURE 1.1." and the caption do not run together.
    for el in body.find_all("span", class_=re.compile(r"^space")):
        el.replace_with(" ")

    # Page anchors become invisible targets so the printed index still links.
    for a in body.find_all("a", id=re.compile(r"^page_")):
        span = soup.new_tag("span")
        span["class"] = "page-anchor"
        span["id"] = a["id"]
        a.replace_with(span)

    # Figure / table anchors keep their original ids.
    for a in body.find_all("a", id=re.compile(r"^[FT]\d")):
        span = soup.new_tag("span")
        span["class"] = "anchor"
        span["id"] = a["id"]
        a.replace_with(span)

    # Endnote references: the EPUB has an empty anchor where a superscript
    # page number belongs. Recreate that marker; it is marked as generated so
    # the fidelity comparison ignores it.
    for a in body.find_all("a", id=re.compile(r"^notes\d+$")):
        nid = a["id"]
        n = nid[5:]
        note = (note_map or {}).get(nid)
        sup = soup.new_tag("sup")
        sup["class"] = "note-ref"
        sup["id"] = nid
        sup["data-note"] = f"n{n}"
        sup["data-pagefind-ignore"] = "true"
        link = soup.new_tag("a", href=f"/notes/#n{n}")
        link["data-generated"] = "true"
        link["aria-label"] = f"See note on page {note['page']}" if note else "See note"
        link.string = note["page"] if note else "†"
        sup.append(link)
        a.replace_with(sup)

    # Empty anchors with no function.
    for a in body.find_all("a"):
        if not a.get("href") and not a.get("id") and not a.get_text(strip=True):
            a.decompose()

    # Flatten layout divs.
    for div in body.find_all("div"):
        div.unwrap()

    # Unwrap the EPUB's span soup, preserving anchors with ids.
    while True:
        span = body.find("span", id=False)
        if span is None:
            break
        span.unwrap()

    # Rewrite internal links.
    for a in body.find_all("a", href=True):
        a["href"] = rewrite_href(a["href"])

    # Drop presentational attributes.
    for tag in body.find_all(True):
        if tag.name not in ("p", "table", "td", "th", "tr", "colgroup", "col", "sup", "span"):
            tag.attrs.pop("class", None)
        tag.attrs.pop("style", None)
    for tag in body.find_all(["p", "table", "td", "th", "tr", "colgroup", "col"]):
        for attr in ("width", "height", "align", "valign", "cellpadding", "cellspacing", "border"):
            tag.attrs.pop(attr, None)

    # Remove genuinely empty paragraphs, but keep anchors and media.
    for p in body.find_all("p"):
        if p.get_text(strip=True) or p.find(["img", "table"]) or p.find(id=True):
            continue
        p.decompose()

    return soup


# ---------------------------------------------------------------------------
# Text extraction / normalisation
# ---------------------------------------------------------------------------

SMALL_WORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "but",
    "by",
    "for",
    "from",
    "in",
    "into",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
    "vs",
}


def smart_title(text: str) -> str:
    """Title-case an ALL CAPS heading without capitalising small words."""
    words = text.lower().split()
    out = []
    capitalize_next = False
    for i, word in enumerate(words):
        if i and word in SMALL_WORDS and not capitalize_next:
            out.append(word)
        else:
            out.append(word[:1].upper() + word[1:])
        capitalize_next = word.endswith(":")
    return " ".join(out)


# ---------------------------------------------------------------------------
# Notes / TOC / index parsers
# ---------------------------------------------------------------------------


def parse_notes(soup: BeautifulSoup) -> dict:
    body = soup.body
    title = ""
    blocks: list[dict] = []
    notes: list[dict] = []
    current_group = ""

    for el in body.find_all(["p", "table"], recursive=False):
        classes = set(el.get("class", []))
        if "fmtitleq" in classes:
            title = el.get_text(" ", strip=True)
            continue
        if "subheading4" in classes:
            text = el.get_text(" ", strip=True)
            hid = f"notes-heading-{len(blocks) + 1}"
            blocks.append(
                {
                    "type": "heading",
                    "id": hid,
                    "html": inner(el).strip(),
                    "text": text,
                }
            )
            current_group = text
            continue
        if "notes" in classes:
            m = re.match(r"^\s*(\d+)\s*", el.get_text(""))
            page = m.group(1) if m else ""
            if m:
                s = first_text_node(el)
                if s is not None:
                    mm = re.match(r"^\s*\d+\s*", str(s))
                    if mm:
                        s.replace_with(str(s)[mm.end() :])
            backlink = el.find("a", href=re.compile(r"#notes(\d+)$"))
            n = None
            if backlink:
                mm = re.search(r"#notes(\d+)$", backlink["href"])
                if mm:
                    n = int(mm.group(1))
            if n is None:
                n = len(notes) + 1
            note_html = inner(el).strip()
            note = {
                "n": n,
                "id": f"n{n}",
                "anchor": f"notes{n}",
                "page": page,
                "group": current_group,
                "html": note_html,
                "text": normalize_text(text_of(el)),
            }
            notes.append(note)
            blocks.append({"type": "note", "n": n})
            continue
        if "notesi" in classes and notes:
            continuation = f'<p class="note-continuation">{inner(el).strip()}</p>'
            notes[-1]["html"] += continuation
            notes[-1]["text"] = normalize_text(notes[-1]["text"] + " " + text_of(el))
            continue
        # Everything else is a paragraph in the reading flow. This includes
        # bodytext-bs, normal-tsa, and the hanging-indent bibliography entries
        # in the general readings section.
        cls = "hang" if "hangs" in classes else ""
        blocks.append(
            {
                "type": "paragraph",
                "html": inner(el).strip(),
                "text": normalize_text(text_of(el)),
                "class": cls,
            }
        )

    # Mark headings that introduce notes (for the jump chips).
    for i, block in enumerate(blocks):
        if block["type"] != "heading":
            continue
        block["has_notes"] = False
        for nxt in blocks[i + 1 :]:
            if nxt["type"] == "heading":
                break
            if nxt["type"] == "note":
                block["has_notes"] = True
                break

    groups = []
    for i, block in enumerate(blocks):
        if block["type"] != "heading" or not block["has_notes"]:
            continue
        note_ids = []
        for nxt in blocks[i + 1 :]:
            if nxt["type"] == "heading":
                break
            if nxt["type"] == "note":
                note_ids.append(nxt["n"])
        groups.append({"title": block["text"], "id": block["id"], "note_ids": note_ids})

    return {
        "title": title,
        "blocks": blocks,
        "groups": groups,
        "notes": notes,
        "by_id": {f"notes{x['n']}": x for x in notes},
        "by_n": {f"n{x['n']}": x for x in notes},
    }


def parse_toc(soup: BeautifulSoup) -> list[dict]:
    entries: list[dict] = []
    for p in soup.select("p.toc-entry, p.toc-entrya, p.toc-chapter, p.toc-level"):
        classes = set(p.get("class", []))
        links = p.find_all("a", href=True)
        href = links[-1]["href"] if links else ""
        text = p.get_text(" ", strip=True)
        if "toc-chapter" in classes:
            number = links[0].get_text(" ", strip=True) if len(links) >= 2 else ""
            label = links[1].get_text(" ", strip=True) if len(links) >= 2 else text
            if not number:
                m = re.match(r"^(\d+)\s+(.*)$", text)
                if m:
                    number, label = m.group(1), m.group(2)
            entries.append(
                {
                    "kind": "chapter",
                    "number": number,
                    "label": label,
                    "href": href,
                    "generated": False,
                }
            )
        elif "toc-level" in classes:
            entries.append(
                {
                    "kind": "section",
                    "label": text,
                    "href": href,
                    "generated": False,
                }
            )
        else:
            entries.append(
                {
                    "kind": "entry",
                    "label": text,
                    "href": href,
                    "generated": False,
                }
            )
    return entries


def parse_index(soup: BeautifulSoup) -> dict:
    title = ""
    entries: list[dict] = []
    for p in soup.body.find_all("p", recursive=False):
        classes = set(p.get("class", []))
        if "fmtitleq" in classes:
            title = p.get_text(" ", strip=True)
            continue
        if classes & {"index", "indexsub", "indext"}:
            text = normalize_text(text_of(p))
            is_sub = "indexsub" in classes or text[:1].islower()
            letter = ""
            if not is_sub:
                key = re.sub(r"^(the|a|an)\s+", "", text, flags=re.I).lstrip("\u201c\u2018\"'")
                if key[:1].isdigit():
                    letter = "#"
                else:
                    m = re.search(r"[A-Za-z]", key)
                    letter = m.group(0).upper() if m else "#"
            entries.append(
                {
                    "class": "index-sub" if is_sub else "index-entry",
                    "id": p.get("id", ""),
                    "html": inner(p).strip(),
                    "text": text,
                    "letter": letter,
                }
            )
    return {"title": title, "entries": entries}


def parse_references(soup: BeautifulSoup) -> dict:
    title = ""
    entries: list[dict] = []
    for p in soup.body.find_all("p", recursive=False):
        classes = set(p.get("class", []))
        if "fmtitleq" in classes:
            title = p.get_text(" ", strip=True)
            continue
        if p.get_text(strip=True):
            entries.append({"id": p.get("id", ""), "html": inner(p).strip()})
    return {"title": title, "entries": entries}


# ---------------------------------------------------------------------------
# Fragment builders
# ---------------------------------------------------------------------------


def heading_html(tag_name: str, el: Tag, level: int, used_ids: set[str]) -> tuple[str, dict]:
    text = el.get_text(" ", strip=True)
    hid = el.get("id") or f"s-{slugify(text)}"
    base = hid
    i = 2
    while hid in used_ids:
        hid = f"{base}-{i}"
        i += 1
    used_ids.add(hid)
    cls = {2: "section-title", 3: "subsection-title", 4: "subsubsection-title"}[level]
    html_out = f'<{tag_name} class="{cls}" id="{html.escape(hid)}">{inner(el).strip()}</{tag_name}>'
    return html_out, {"level": level, "id": hid, "title": text}


def image_html(img: Tag, images: dict, caption_id: str | None, has_caption: bool) -> str:
    src = img.get("src", "")
    name = src.rsplit("/", 1)[-1]
    info = images.get(name)
    if not info:
        raise ValueError(f"Image referenced by the book is missing: {name}")
    alt = img.get("alt", "") or ""
    if has_caption:
        alt = ""
        described = f' aria-describedby="{caption_id}"' if caption_id else ""
    else:
        described = ""
    w = info["width"]
    h = info["height"]
    img_tag = (
        f'<img src="/images/{html.escape(name)}" '
        f'width="{w}" height="{h}" alt="{html.escape(alt)}"{described} '
        f'loading="lazy" decoding="async">'
    )
    picture = (
        f'<picture><source srcset="/images/{html.escape(info["webp"])}" type="image/webp">'
        f"{img_tag}</picture>"
    )
    return (
        f'<a class="lightbox-link" href="/images/{html.escape(name)}" '
        f'aria-label="View figure larger">{picture}</a>'
    )


def build_figure(imgs: list[Tag], captions: list[Tag], images: dict, fig_index: int) -> str:
    caption_html = ""
    caption_id = f"fig-{fig_index}-caption"
    figure_id = ""
    for cap in captions:
        for anchor in cap.find_all("span", id=re.compile(r"^F")):
            if not figure_id:
                figure_id = anchor["id"]
                caption_id = anchor["id"] + "-caption"
            anchor.decompose()
        caption_html += f"<p>{inner(cap).strip()}</p>"
    if not caption_html:
        # No caption paragraph. If alt text reads like a caption, surface it.
        alt = imgs[0].get("alt", "") if imgs else ""
        if alt and re.match(r"^(FIGURE|TABLE)\b", alt, re.I):
            caption_html = f"<p>{html.escape(alt)}</p>"
    has_caption = bool(caption_html)
    body = "".join(image_html(img, images, caption_id, has_caption) for img in imgs)
    if not body:
        return ""
    cls = "figure figure-multi" if len(imgs) > 1 else "figure"
    figcap = (
        f'<figcaption id="{html.escape(caption_id)}">{caption_html}</figcaption>'
        if has_caption
        else ""
    )
    fid = f' id="{html.escape(figure_id)}"' if figure_id else ""
    return f'<figure{fid} class="{cls}" data-count="{len(imgs)}">{body}{figcap}</figure>'


def convert_blocks(
    body: Tag, images: dict, note_map: dict, page_type: str = "chapter"
) -> tuple[str, list[dict], list[str]]:
    """Convert a cleaned body into semantic HTML."""
    blocks = [el for el in body.children if isinstance(el, Tag) and el.name in ("p", "table")]
    out: list[str] = []
    sections: list[dict] = []
    warnings: list[str] = []
    used_ids: set[str] = set()
    fig_index = 0
    i = 0
    first_body_para = True

    def take_class(el: Tag) -> str:
        cls = el.get("class", [])
        return cls[0] if cls else ""

    while i < len(blocks):
        el = blocks[i]
        cls = take_class(el)

        if el.name == "table":
            classes = list(el.get("class", []))
            if "book-table" not in classes:
                classes.insert(0, "book-table")
            el["class"] = classes
            table = str(el)
            out.append(f'<div class="table-wrap">{table}</div>')
            i += 1
            continue

        if cls == "chaptertitle":
            number = el.get_text(" ", strip=True)
            anchors = "".join(str(a) for a in el.find_all(id=True))
            title = ""
            if i + 1 < len(blocks) and take_class(blocks[i + 1]) in (
                "chaptertitlea",
                "chaptertitleb",
            ):
                anchors += "".join(str(a) for a in blocks[i + 1].find_all(id=True))
                title = blocks[i + 1].get_text(" ", strip=True)
                i += 1
            hid = el.get("id") or f"ch-{slugify(title)}"
            out.append(
                f'<header class="chapter-header" id="{html.escape(hid)}">'
                f"{anchors}"
                f'<p class="chapter-number">{html.escape(number)}</p>'
                f'<h1 class="chapter-title">{html.escape(title)}</h1>'
                f'<p class="chapter-meta" data-chrome><!--READTIME--></p>'
                f"</header>"
            )
            i += 1
            continue

        if cls in ("subheading", "subheading4", "subheading5"):
            level = {"subheading": 2, "subheading4": 3, "subheading5": 4}[cls]
            # Remove the TOC backlink wrapper, keep the text.
            for a in el.find_all("a", href=True):
                if a["href"].startswith("/contents/"):
                    a.unwrap()
            tag = {2: "h2", 3: "h3", 4: "h4"}[level]
            h, meta = heading_html(tag, el, level, used_ids)
            out.append(h)
            sections.append(meta)
            i += 1
            continue

        if cls == "fmtitleq":
            for a in el.find_all("a", href=True):
                if a["href"].startswith("/contents/") or a["href"].startswith("/"):
                    a.unwrap()
            hid = el.get("id") or f"title-{page_type}"
            tag = "h1"
            out.append(
                f'<header class="page-head" id="{html.escape(hid)}">'
                f'<h1 class="page-title">{inner(el).strip()}</h1>'
                f'<p class="chapter-meta" data-chrome><!--READTIME--></p>'
                f"</header>"
            )
            i += 1
            continue

        if cls == "image":
            imgs: list[Tag] = []
            anchors = ""
            j = i
            while j < len(blocks) and take_class(blocks[j]) == "image":
                anchors += "".join(str(a) for a in blocks[j].find_all(id=True))
                imgs.extend(blocks[j].find_all("img"))
                j += 1
            caps: list[Tag] = []
            while j < len(blocks) and take_class(blocks[j]) in ("caption", "captiona"):
                caps.append(blocks[j])
                j += 1
            fig_index += 1
            fig = build_figure(imgs, caps, images, fig_index)
            if fig:
                out.append(anchors + fig)
            i = j
            continue

        if cls in ("caption", "captiona"):
            # An orphan caption: keep the text, style it as a caption.
            out.append(f'<p class="orphan-caption">{inner(el).strip()}</p>')
            i += 1
            continue

        if cls in ("bulllist", "bulllista", "bulllists"):
            items = []
            j = i
            while j < len(blocks) and take_class(blocks[j]) in (
                "bulllist",
                "bulllista",
                "bulllists",
            ):
                item = blocks[j]
                strip_leading(item, r"^\s*[•·]\s*")
                items.append(f"<li>{inner(item).strip()}</li>")
                j += 1
            out.append('<ul class="book-list">' + "".join(items) + "</ul>")
            i = j
            continue

        if cls == "list":
            items = []
            start = 1
            j = i
            while j < len(blocks) and take_class(blocks[j]) == "list":
                item = blocks[j]
                m = strip_leading(item, r"^\s*(\d+)\.\s*")
                if m and j == i:
                    start = int(m.group(1))
                items.append(f"<li>{inner(item).strip()}</li>")
                j += 1
            start_attr = f' start="{start}"' if start != 1 else ""
            out.append(f'<ol class="book-list"{start_attr}>' + "".join(items) + "</ol>")
            i = j
            continue

        if cls.startswith("blockquote"):
            items = []
            j = i
            while j < len(blocks) and take_class(blocks[j]).startswith("blockquote"):
                items.append(f"<p>{inner(blocks[j]).strip()}</p>")
                j += 1
            qcls = (
                "book-quote quote-epigraph"
                if cls in ("blockquotea", "blockquotei")
                else "book-quote"
            )
            out.append(f'<blockquote class="{qcls}">' + "".join(items) + "</blockquote>")
            i = j
            continue

        if cls in ("hang", "hang-ts", "hangi"):
            pcls = "hang continuation" if cls in ("hangi", "hang-ts") else "hang"
            out.append(f'<p class="{pcls}">{inner(el).strip()}</p>')
            i += 1
            continue

        if cls in ("right", "right-ts"):
            out.append(f'<p class="signature">{inner(el).strip()}</p>')
            i += 1
            continue

        if cls == "center":
            out.append(f'<p class="center">{inner(el).strip()}</p>')
            i += 1
            continue

        if cls in (
            "book-title",
            "book-titlea",
            "book-titleb",
            "book-titlec",
            "halftitle",
            "halftitlea",
            "halftitleb",
            "halftitlec",
        ):
            out.append(f'<p class="title-line">{inner(el).strip()}</p>')
            i += 1
            continue

        if cls == "edition":
            out.append(f'<p class="title-edition">{inner(el).strip()}</p>')
            i += 1
            continue

        if cls == "book-author":
            out.append(f'<p class="title-author">{inner(el).strip()}</p>')
            i += 1
            continue

        if cls in ("pub", "puba", "pubb"):
            out.append(f'<p class="title-publisher">{inner(el).strip()}</p>')
            i += 1
            continue

        if cls == "fmtitle":
            out.append(f'<h2 class="also-by-title">{inner(el).strip()}</h2>')
            i += 1
            continue

        if cls == "fmtitlea":
            out.append(f'<p class="also-by-author">{inner(el).strip()}</p>')
            i += 1
            continue

        if cls == "normalf1":
            out.append(f'<h3 class="also-by-heading">{inner(el).strip()}</h3>')
            i += 1
            continue

        if cls in ("normalf", "normalfa"):
            out.append(f'<p class="also-by-item">{inner(el).strip()}</p>')
            i += 1
            continue

        if cls == "normalfi":
            out.append(f'<p class="also-by-note">{inner(el).strip()}</p>')
            i += 1
            continue

        if cls == "dedication":
            out.append(f'<p class="dedication">{inner(el).strip()}</p>')
            i += 1
            continue

        if cls.startswith("copyright"):
            out.append(f'<p class="copyright">{inner(el).strip()}</p>')
            i += 1
            continue

        # Normal paragraph.
        if not el.get_text(strip=True) and not el.find("img"):
            anchor_html = "".join(str(a) for a in el.find_all(id=True))
            if anchor_html:
                out.append(anchor_html)
            i += 1
            continue
        pcls = ""
        if page_type == "chapter" and first_body_para:
            pcls = ' class="lede"'
            first_body_para = False
        out.append(f"<p{pcls}>{inner(el).strip()}</p>")
        i += 1

    return "".join(out), sections, warnings


def convert_simple_page(
    soup: BeautifulSoup, images: dict, note_map: dict, page_type: str
) -> tuple[str, list[dict], list[str]]:
    return convert_blocks(soup.body, images, note_map, page_type)


def convert_front_matter(soups: dict[str, BeautifulSoup], images: dict) -> str:
    out = ['<h1 class="front-title" data-chrome>Front Matter</h1>']
    labels = {
        "Halftitle.html": "Half Title",
        "Fm.html": "Also by Don Norman",
        "Title.html": "Title Page",
        "Copyright.html": "Copyright",
        "Dedication.html": "Dedication",
    }
    ids = {
        "Halftitle.html": "halftitle",
        "Fm.html": "also-by",
        "Title.html": "title",
        "Copyright.html": "copyright",
        "Dedication.html": "dedication",
    }
    for name in FRONT_MATTER_FILES:
        soup = soups[name]
        body = soup.body
        out.append(
            f'<section class="front-section" id="{ids[name]}">'
            f'<p class="front-label" data-chrome>{html.escape(labels[name])}</p>'
        )
        if name == "Halftitle.html":
            for p in body.find_all("p"):
                out.append(f'<p class="title-line">{inner(p).strip()}</p>')
        elif name == "Title.html":
            for p in body.find_all("p"):
                cls = (p.get("class") or ["p"])[0]
                out.append(f'<p class="title-line {cls}">{inner(p).strip()}</p>')
        elif name == "Dedication.html":
            for p in body.find_all("p"):
                out.append(f'<p class="dedication">{inner(p).strip()}</p>')
        elif name == "Copyright.html":
            for p in body.find_all("p"):
                out.append(f'<p class="copyright">{inner(p).strip()}</p>')
        elif name == "Fm.html":
            for p in body.find_all("p"):
                cls = (p.get("class") or ["p"])[0]
                text = inner(p).strip()
                if cls == "fmtitle":
                    out.append(f'<h2 class="also-by-title">{text}</h2>')
                elif cls == "fmtitlea":
                    out.append(f'<p class="also-by-author">{text}</p>')
                elif cls == "normalf1":
                    out.append(f'<h3 class="also-by-heading">{text}</h3>')
                elif cls in ("normalf", "normalfa"):
                    out.append(f'<p class="also-by-item">{text}</p>')
                elif cls == "normalfi":
                    out.append(f'<p class="also-by-note">{text}</p>')
                elif text:
                    out.append(f"<p>{text}</p>")
        out.append("</section>")
    return "".join(out)


def convert_notes_page(soup: BeautifulSoup, notes_data: dict) -> str:
    out = []
    if notes_data["title"]:
        out.append(
            f'<header class="page-head"><h1 class="page-title" id="notes">{html.escape(notes_data["title"])}</h1>'
            f'<p class="chapter-meta" data-chrome><!--READTIME--></p></header>'
        )
    out.append('<div class="notes-jump" data-chrome>')
    for g in notes_data["groups"]:
        out.append(f'<a href="#{g["id"]}">{html.escape(smart_title(g["title"]))}</a>')
    out.append("</div>")

    by_n = {n["n"]: n for n in notes_data["notes"]}
    for block in notes_data["blocks"]:
        if block["type"] == "heading":
            out.append(f'<h2 class="notes-group" id="{block["id"]}">{block["html"]}</h2>')
        elif block["type"] == "paragraph":
            cls = f' class="{block["class"]}"' if block.get("class") else ""
            out.append(f"<p{cls}>{block['html']}</p>")
        elif block["type"] == "note":
            note = by_n[block["n"]]
            backlink = ""
            if note.get("has_anchor"):
                backlink = (
                    f'<a class="note-back" href="/chapters/{note.get("chapter_num", "")}/#notes{note["n"]}" '
                    f'data-generated="true" aria-label="Back to the reference">↩</a>'
                )
            out.append(
                f'<article class="note" id="{note["id"]}">'
                f'<div class="note-page">{html.escape(note["page"])}</div>'
                f'<div class="note-body">{note["html"]}{backlink}</div>'
                f"</article>"
            )
    return "".join(out)


def convert_index_page(soup: BeautifulSoup, index_data: dict) -> str:
    out = []
    out.append(
        '<header class="page-head"><h1 class="page-title" id="ind">'
        + html.escape(index_data["title"])
        + "</h1></header>"
    )
    letters = []
    for entry in index_data["entries"]:
        letter = entry.get("letter", "")
        if letter and (not letters or (letter != letters[-1] and letter > letters[-1])):
            letters.append(letter)
    out.append('<div class="index-tools" data-chrome>')
    out.append(
        '<label class="index-filter"><span>Filter the index</span>'
        '<input type="search" id="index-filter" placeholder="Type a name or term…" autocomplete="off"></label>'
    )
    out.append('<nav class="index-letters" aria-label="Index letters">')
    for letter in letters:
        out.append(f'<a href="#letter-{letter}">{letter}</a>')
    out.append("</nav></div>")
    out.append('<p class="index-count" data-chrome></p>')
    current = None
    open_list = False
    for entry in index_data["entries"]:
        letter = entry.get("letter", "")
        if letter and (current is None or (letter != current and letter > current)):
            if open_list:
                out.append("</ul>")
            current = letter
            out.append(
                f'<h2 class="index-letter" id="letter-{letter}" data-generated="true" data-pagefind-ignore="true">{letter}</h2>'
                f'<ul class="index-list" data-letter="{letter}">'
            )
            open_list = True
        if not open_list:
            out.append('<ul class="index-list">')
            open_list = True
        eid = f' id="{html.escape(entry["id"])}"' if entry["id"] else ""
        out.append(
            f'<li{eid} class="{entry["class"]}" data-index-text="{html.escape(entry["text"])}">{entry["html"]}</li>'
        )
    if open_list:
        out.append("</ul>")
    return "".join(out)


def convert_references_page(soup: BeautifulSoup, refs_data: dict) -> str:
    out = [
        f'<header class="page-head"><h1 class="page-title" id="ref">{html.escape(refs_data["title"])}</h1>'
        f'<p class="chapter-meta" data-chrome><!--READTIME--></p></header>'
    ]
    out.append('<ol class="reference-list">')
    for entry in refs_data["entries"]:
        eid = f' id="{html.escape(entry["id"])}"' if entry["id"] else ""
        out.append(f"<li{eid}>{entry['html']}</li>")
    out.append("</ol>")
    return "".join(out)


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------


def process_images(zf: zipfile.ZipFile, cleaned: dict[str, BeautifulSoup], cover_src: str) -> dict:
    PUBLIC_IMAGES.mkdir(parents=True, exist_ok=True)
    for p in PUBLIC_IMAGES.glob("*"):
        if p.is_file():
            p.unlink()

    names: set[str] = set()
    for soup in cleaned.values():
        for img in soup.find_all("img"):
            src = img.get("src", "")
            if src:
                names.add(src.rsplit("/", 1)[-1])
    if cover_src:
        names.add(cover_src.rsplit("/", 1)[-1])

    images: dict[str, dict] = {}
    for name in sorted(names):
        try:
            data = zf.read(f"OEBPS/images/{name}")
        except KeyError:
            print(f"  ! missing image in EPUB: {name}")
            continue
        jpg_path = PUBLIC_IMAGES / name
        jpg_path.write_bytes(data)
        try:
            im = Image.open(io.BytesIO(data))
            if im.mode not in ("RGB", "L"):
                im = im.convert("RGB")
            webp_name = name.rsplit(".", 1)[0] + ".webp"
            webp_path = PUBLIC_IMAGES / webp_name
            im.save(webp_path, "WEBP", quality=86, method=6)
            images[name] = {"webp": webp_name, "width": im.width, "height": im.height}
        except Exception as exc:  # pragma: no cover - defensive
            images[name] = {"webp": name, "width": 0, "height": 0}
            print(f"  ! could not convert {name}: {exc}")

    if cover_src:
        cover_name = cover_src.rsplit("/", 1)[-1]
        shutil.copyfile(PUBLIC_IMAGES / cover_name, PUBLIC_IMAGES / "cover.jpg")
        if images.get(cover_name):
            shutil.copyfile(
                PUBLIC_IMAGES / images[cover_name]["webp"], PUBLIC_IMAGES / "cover.webp"
            )
        images["cover.jpg"] = {
            "webp": "cover.webp",
            "width": images.get(cover_name, {}).get("width", 438),
            "height": images.get(cover_name, {}).get("height", 662),
        }
        if cover_name != "cover.jpg":
            for suffix in (".jpg", ".webp"):
                leftover = PUBLIC_IMAGES / (cover_name.rsplit(".", 1)[0] + suffix)
                if leftover.exists():
                    leftover.unlink()
            images.pop(cover_name, None)
    return images


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    CONTENT.mkdir(parents=True, exist_ok=True)
    PAGES.mkdir(parents=True, exist_ok=True)
    PUBLIC_IMAGES.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(EPUB) as zf:
        opf = BeautifulSoup(zf.read("OEBPS/package.opf"), "xml")
        meta = {
            "title": opf.find("dc:title").get_text(strip=True),
            "subtitle": "Revised and Expanded Edition",
            "author": opf.find("dc:creator").get_text(strip=True),
            "publisher": opf.find("dc:publisher").get_text(strip=True),
            "date": opf.find("dc:date").get_text(strip=True)[:4] if opf.find("dc:date") else "",
            "isbn": "9780465072996",
            "language": "en",
            "description": BeautifulSoup(opf.find("dc:description").get_text(), "lxml").get_text(
                " ", strip=True
            )
            if opf.find("dc:description")
            else "",
        }

        raw = {name: zf.read(f"OEBPS/{name}") for name in SPINE}
        raw_soups = {name: parse_html(data) for name, data in raw.items()}

        # Notes first: chapters need the page-number map for their superscripts.
        notes_soup = clean_soup(raw_soups["Notes.html"])
        notes_source_text = normalize_text(text_of(notes_soup.body))
        notes_data = parse_notes(notes_soup)
        note_map = notes_data["by_id"]

        cleaned: dict[str, BeautifulSoup] = {"Notes.html": notes_soup}
        for name in SPINE:
            if name == "Notes.html":
                continue
            cleaned[name] = clean_soup(parse_html(raw[name]), note_map)

        cover_src = "images/9780465072996.jpg"
        images = process_images(zf, cleaned, cover_src)

        # Source-text baseline (before conversion).
        source_text = {
            name: normalize_text(text_of(cleaned[name].body))
            for name in SPINE
            if name != "Cover.html"
        }
        source_text["Notes.html"] = notes_source_text

        # Which endnote anchors actually exist in the chapters?
        chapter_anchors: dict[str, int] = {}
        for file, num, _title in CHAPTERS:
            for m in re.finditer(r'id="(notes\d+)"', raw[file].decode("utf-8")):
                chapter_anchors[m.group(1)] = num
        for note in notes_data["notes"]:
            note["has_anchor"] = f"notes{note['n']}" in chapter_anchors
            note["chapter_num"] = chapter_anchors.get(f"notes{note['n']}", "")

        toc = parse_toc(cleaned["Contents.html"])
        index_data = parse_index(cleaned["Index.html"])
        refs_data = parse_references(cleaned["References.html"])

        pages: list[dict] = []
        fragments: dict[str, str] = {}

        # Chapters
        for file, num, title in CHAPTERS:
            soup = cleaned[file]
            fragment, sections, warnings = convert_blocks(soup.body, images, note_map, "chapter")
            pid = f"chapter-{num}"
            fragment = fragment.replace(
                "<!--READTIME-->",
                '<span class="readtime">Calculating…</span>',
            )
            fragments[pid] = fragment
            pages.append(
                {
                    "id": pid,
                    "type": "chapter",
                    "route": f"/chapters/{num}/",
                    "number": num,
                    "title": title,
                    "short_title": f"Chapter {num}",
                    "source_files": [file],
                    "sections": sections,
                    "words": len(source_text[file].split()),
                    "figure_count": fragment.count("<figure"),
                    "note_count": fragment.count('class="note-ref"'),
                    "warnings": warnings,
                }
            )

        # Simple narrative pages
        for pid, file, title, route in [
            ("preface", "Preface.html", "Preface to the Revised Edition", "/preface/"),
            ("acknowledgments", "Acknowledgments.html", "Acknowledgments", "/acknowledgments/"),
        ]:
            fragment, sections, warnings = convert_simple_page(cleaned[file], images, note_map, pid)
            fragment = fragment.replace(
                "<!--READTIME-->", '<span class="readtime">Calculating…</span>'
            )
            fragments[pid] = fragment
            pages.append(
                {
                    "id": pid,
                    "type": "narrative",
                    "route": route,
                    "title": title,
                    "short_title": title,
                    "source_files": [file],
                    "sections": sections,
                    "words": len(source_text[file].split()),
                    "warnings": warnings,
                }
            )

        # Front matter
        front_html = convert_front_matter(cleaned, images)
        fragments["front-matter"] = front_html
        pages.append(
            {
                "id": "front-matter",
                "type": "frontmatter",
                "route": "/front-matter/",
                "title": "Front Matter",
                "short_title": "Front matter",
                "source_files": FRONT_MATTER_FILES,
                "sections": [],
                "words": sum(len(source_text[f].split()) for f in FRONT_MATTER_FILES),
                "warnings": [],
            }
        )

        # Contents is rendered by build.py from the TOC data.
        pages.append(
            {
                "id": "contents",
                "type": "contents",
                "route": "/contents/",
                "title": "Contents",
                "short_title": "Contents",
                "source_files": ["Contents.html"],
                "sections": [],
                "words": len(source_text["Contents.html"].split()),
                "warnings": [],
            }
        )

        # Notes
        notes_html = convert_notes_page(notes_soup, notes_data)
        notes_html = notes_html.replace(
            "<!--READTIME-->", '<span class="readtime">Calculating…</span>'
        )
        fragments["notes"] = notes_html
        pages.append(
            {
                "id": "notes",
                "type": "notes",
                "route": "/notes/",
                "title": "General Readings and Notes",
                "short_title": "Notes",
                "source_files": ["Notes.html"],
                "sections": [],
                "words": len(source_text["Notes.html"].split()),
                "note_count": len(notes_data["notes"]),
                "warnings": [],
            }
        )

        # References
        refs_html = convert_references_page(cleaned["References.html"], refs_data)
        refs_html = refs_html.replace(
            "<!--READTIME-->", '<span class="readtime">Calculating…</span>'
        )
        fragments["references"] = refs_html
        pages.append(
            {
                "id": "references",
                "type": "references",
                "route": "/references/",
                "title": "References",
                "short_title": "References",
                "source_files": ["References.html"],
                "sections": [],
                "words": len(source_text["References.html"].split()),
                "reference_count": len(refs_data["entries"]),
                "warnings": [],
            }
        )

        # Index
        index_html = convert_index_page(cleaned["Index.html"], index_data)
        fragments["index"] = index_html
        pages.append(
            {
                "id": "index",
                "type": "index",
                "route": "/index-of-terms/",
                "title": "Index",
                "short_title": "Index",
                "source_files": ["Index.html"],
                "sections": [],
                "words": len(source_text["Index.html"].split()),
                "index_count": len(index_data["entries"]),
                "warnings": [],
            }
        )

        # Landing page is generated, not a source page.
        pages.append(
            {
                "id": "home",
                "type": "home",
                "route": "/",
                "title": meta["title"],
                "short_title": "Home",
                "source_files": ["Cover.html"],
                "sections": [],
                "words": 0,
                "warnings": [],
            }
        )

        # Write fragments
        for pid, fragment in fragments.items():
            (PAGES / f"{pid}.html").write_text(fragment, encoding="utf-8")

        # Reading order: front matter, preface, chapters, back matter.
        reading_order = [
            "front-matter",
            "preface",
            *[f"chapter-{n}" for n in range(1, 8)],
            "acknowledgments",
            "notes",
            "references",
            "index",
        ]

        book = {
            "meta": meta,
            "pages": pages,
            "toc": toc,
            "reading_order": reading_order,
            "notes": notes_data["notes"],
            "notes_groups": notes_data["groups"],
            "stats": {
                "words": sum(len(source_text[name].split()) for name in source_text),
                "chapter_words": sum(len(source_text[f].split()) for f, _, _ in CHAPTERS),
                "figures": sum(p.get("figure_count", 0) for p in pages),
                "notes": len(notes_data["notes"]),
                "references": len(refs_data["entries"]),
                "index_entries": len(index_data["entries"]),
                "images": len([n for n in images if n != "cover.jpg"]),
            },
        }
        (CONTENT / "book.json").write_text(
            json.dumps(book, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (CONTENT / "source-text.json").write_text(
            json.dumps(source_text, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (CONTENT / "notes-popover.json").write_text(
            json.dumps(
                {
                    f"n{n['n']}": {
                        "page": n["page"],
                        "text": n["text"],
                        "href": f"/notes/#n{n['n']}",
                    }
                    for n in notes_data["notes"]
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        print(f"Extracted {len(pages)} pages")
        print(f"  chapters: {len(CHAPTERS)}")
        print(f"  words:    {book['stats']['words']:,}")
        print(f"  figures:  {book['stats']['figures']}")
        print(f"  notes:    {book['stats']['notes']}")
        print(f"  refs:     {book['stats']['references']}")
        print(f"  index:    {book['stats']['index_entries']}")
        print(f"  images:   {book['stats']['images']}")


if __name__ == "__main__":
    main()
