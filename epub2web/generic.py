"""Generic EPUB → semantic page fragments.

This is the deterministic, heuristic path. It handles ordinary EPUB 2/3
markup: semantic headings, paragraphs, lists, tables, figures, images, and
notes links. For print-conversion class soup it applies conservative class
heuristics; a book-specific profile can override the result when exact
fidelity matters (see the DOET profile used by the CLI).
"""

from __future__ import annotations

import html
import io
import json
import posixpath
import re
import shutil
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image
import warnings

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning, NavigableString, Tag

from .epub import Epub, ManifestItem
from .text import inner, normalize_text, slugify, strip_leading, text_of

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

FRONT_LABELS = {
    "title page", "title", "copyright", "dedication", "contents", "table of contents",
    "half title", "also by", "frontispiece", "preface", "foreword", "cover",
}
BACK_LABELS = {
    "notes", "note", "endnotes", "references", "bibliography", "index", "appendix",
    "acknowledgments", "acknowledgements", "afterword", "glossary", "colophon",
    "license", "copyright page",
}
CHAPTER_RE = re.compile(
    r"^(chapter|part|book)\s+([0-9]+|[IVXLCDM]+|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)"
    r"([.:]?)\s*(.*)$",
    re.I,
)
NUMBER_RE = re.compile(r"^(\d+)([.:)]?)\s+(.*)$")


def clean_doc(soup: BeautifulSoup) -> BeautifulSoup:
    body = soup.body
    if body is None:
        return soup
    for el in body.find_all(["script", "style", "noscript", "nav"]):
        el.decompose()
    for el in body.find_all(attrs={"hidden": True}):
        el.decompose()
    for el in body.find_all(style=True):
        if "display:none" in el.get("style", "").replace(" ", "").lower():
            el.decompose()
    for el in body.find_all(class_=re.compile(r"^(hide|hidden)$", re.I)):
        if el.get_text(strip=True):
            continue
        if el.find(["img", "table"]):
            el.decompose()
        else:
            el.replace_with(" ")
    # Print-conversion spacers carry the space between a label and its text.
    for el in body.find_all("span", class_=re.compile(r"^space")):
        el.replace_with(" ")
    for el in body.find_all("hr"):
        el.decompose()

    # Keep ids from layout containers before flattening them. If the
    # container wraps a heading/paragraph, move the id onto that block so it
    # remains the first block (important for chapter-header detection).
    for el in body.find_all(["div", "section"]):
        if el.get("id"):
            target = el.find(["h1", "h2", "h3", "h4", "h5", "h6", "p", "table", "figure"])
            if target is not None and not target.get("id"):
                target["id"] = el["id"]
            else:
                span = soup.new_tag("span")
                span["class"] = "anchor"
                span["id"] = el["id"]
                el.insert_before(span)
        el.unwrap()

    for a in body.find_all("a", id=re.compile(r"^page_")):
        span = soup.new_tag("span")
        span["class"] = "page-anchor"
        span["id"] = a["id"]
        a.replace_with(span)
    for a in body.find_all("a"):
        if not a.get("href") and a.get("id") and not a.get_text(strip=True):
            span = soup.new_tag("span")
            span["class"] = "anchor"
            span["id"] = a["id"]
            a.replace_with(span)

    while True:
        span = body.find("span", id=False)
        if span is None:
            break
        span.unwrap()

    # Divs were flattened; prose that lived directly inside a div is now a
    # bare text node. Wrap each run of text/<br> so it is not lost.
    inline_tags = {
        "a", "abbr", "b", "bdi", "bdo", "br", "cite", "code", "data", "dfn",
        "em", "i", "img", "kbd", "mark", "q", "s", "samp", "small", "span",
        "strong", "sub", "sup", "time", "u", "var", "wbr",
    }

    def flush_run(run):
        if not run:
            return
        if not any((isinstance(x, Tag) or (isinstance(x, NavigableString) and x.strip())) for x in run):
            return
        paragraph = soup.new_tag("p")
        run[0].insert_before(paragraph)
        for node in run:
            paragraph.append(node.extract())

    run = []
    for child in list(body.children):
        if isinstance(child, NavigableString) or (isinstance(child, Tag) and child.name in inline_tags):
            run.append(child)
        else:
            flush_run(run)
            run = []
    flush_run(run)

    for p in body.find_all("p"):
        if p.get_text(strip=True) or p.find(["img", "table"]) or p.find(id=True):
            continue
        p.decompose()

    for tag in body.find_all(True):
        if tag.name not in ("p", "table", "td", "th", "tr", "colgroup", "col", "h1", "h2", "h3", "h4", "h5", "h6"):
            tag.attrs.pop("class", None)
        tag.attrs.pop("style", None)
    for tag in body.find_all(["table", "td", "th", "tr", "colgroup", "col"]):
        for attr in ("width", "height", "align", "valign", "cellpadding", "cellspacing", "border"):
            tag.attrs.pop(attr, None)
    return soup


def parse_label(label: str) -> tuple[str, str, str]:
    """Return (display_title, number_label, short_title)."""
    label = re.sub(r"\s+", " ", label).strip()
    m = CHAPTER_RE.match(label)
    if m:
        number_label = f"{m.group(1).upper()} {m.group(2)}{m.group(3)}"
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
            value = value[len(prefix) + 1:].strip()
            break
    m = re.match(r"([0-9]+|[IVXLCDM]+)", value)
    return m.group(1) if m else ""


def heading_text(el: Tag) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()


def first_heading(soup: BeautifulSoup) -> Tag | None:
    body = soup.body
    if body is None:
        return None
    # Chapter markers from print conversions take priority.
    for p in body.find_all("p"):
        cls = " ".join(p.get("class", [])).lower()
        if "chaptertitle" in cls:
            return p
    for tag in ("h1", "h2", "h3", "h4"):
        el = body.find(tag)
        if el is not None and el.get_text(strip=True):
            return el
    for p in body.find_all("p"):
        cls = " ".join(p.get("class", [])).lower()
        if any(k in cls for k in ("title", "heading", "subhead")):
            if len(p.get_text(" ", strip=True)) < 140:
                return p
    return None


def image_info(epub: Epub, images: dict, doc_path: str, src: str) -> dict | None:
    if not src or src.startswith(("data:", "http:", "https:")):
        return None
    path, _ = epub._resolve(doc_path, src)
    return images.get(path)


class GenericExtractor:
    def __init__(self, epub_path: str | Path, content_dir: str | Path, images_dir: str | Path):
        self.epub_path = Path(epub_path)
        self.content_dir = Path(content_dir)
        self.pages_dir = self.content_dir / "pages"
        self.images_dir = Path(images_dir)

    # -- page planning ----------------------------------------------------
    def run(self) -> dict:
        self.content_dir.mkdir(parents=True, exist_ok=True)
        self.pages_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)
        for p in self.images_dir.glob("*"):
            if p.is_file():
                p.unlink()

        with Epub(self.epub_path) as book:
            self.book = book
            self.items = [item for item in book.html_spine()
                          if item.path != (book.nav_item.path if book.nav_item else None)]
            self.cleaned: dict[str, BeautifulSoup] = {}
            for item in self.items:
                try:
                    soup = BeautifulSoup(book.read(item.path), "lxml")
                except Exception:
                    continue
                self.cleaned[item.path] = clean_doc(soup)

            self.cover_info = self._process_cover()
            self.images = self._process_images()
            self.pages = self._plan_pages()
            self.page_by_path = {p["source_files"][0]: p for p in self.pages}
            self.route_by_path = {p["source_files"][0]: p["route"] for p in self.pages}

            fragments = {}
            source_text = {}
            for page in self.pages:
                path = page["source_files"][0]
                soup = self.cleaned[path]
                source_text[path] = normalize_text(text_of(soup.body))
                fragment, sections, warnings = self._convert_page(page, soup)
                page["sections"] = sections
                page["warnings"] = warnings
                page["figure_count"] = fragment.count("<figure")
                page["note_count"] = fragment.count("noteref") + fragment.count("footnote")
                page["words"] = len(source_text[path].split())
                fragments[page["id"]] = fragment

            self.pages = [p for p in self.pages if p["id"] in fragments]
            self.page_by_path = {p["source_files"][0]: p for p in self.pages}
            self.route_by_path = {p["source_files"][0]: p["route"] for p in self.pages}

            self._write_toc()
            self._write_pages(fragments)
            self._write_book(source_text)
            return self.book_data

    # -- images -----------------------------------------------------------
    def _process_cover(self) -> dict | None:
        item = self.book.cover_item
        if item is None:
            return None
        data = self.book.read(item.path)
        suffix = Path(item.path).suffix.lower()
        if suffix == ".svg":
            name = "cover.svg"
            (self.images_dir / name).write_bytes(data)
            return {"name": name, "webp": "", "width": 0, "height": 0}
        name = "cover.jpg"
        (self.images_dir / name).write_bytes(data)
        try:
            im = Image.open(io.BytesIO(data))
            if im.mode not in ("RGB", "L"):
                im = im.convert("RGB")
            im.save(self.images_dir / "cover.webp", "WEBP", quality=86, method=6)
            return {"name": name, "webp": "cover.webp", "width": im.width, "height": im.height}
        except Exception:
            return {"name": name, "webp": "", "width": 0, "height": 0}

    def _process_images(self) -> dict[str, dict]:
        used: set[str] = set()
        result: dict[str, dict] = {}
        for doc_path, soup in self.cleaned.items():
            for img in soup.find_all("img"):
                src = img.get("src") or ""
                if not src or src.startswith(("data:", "http:", "https:")):
                    continue
                path, _ = self.book._resolve(doc_path, src)
                if not path or path in result:
                    continue
                try:
                    data = self.book.read(path)
                except KeyError:
                    continue
                base = Path(path).name
                stem, suffix = Path(base).stem, Path(base).suffix.lower()
                name = base
                n = 2
                while name in used:
                    name = f"{stem}-{n}{suffix}"
                    n += 1
                used.add(name)
                (self.images_dir / name).write_bytes(data)
                info = {"name": name, "webp": "", "width": 0, "height": 0}
                if suffix not in (".svg",):
                    try:
                        im = Image.open(io.BytesIO(data))
                        if im.mode not in ("RGB", "L"):
                            im = im.convert("RGB")
                        webp = f"{Path(name).stem}.webp"
                        im.save(self.images_dir / webp, "WEBP", quality=86, method=6)
                        info.update(webp=webp, width=im.width, height=im.height)
                    except Exception:
                        pass
                result[path] = info
        return result

    # -- planning ---------------------------------------------------------
    def _nav_label(self, path: str) -> str:
        for entry in self.book.toc_flat():
            if entry.path == path and entry.label:
                return entry.label
        return ""

    def _plan_pages(self) -> list[dict]:
        pages = []
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
            label = self._nav_label(item.path)
            heading = first_heading(soup)
            htext = heading_text(heading) if heading else ""
            if not label:
                label = htext or self.book._text(BeautifulSoup(self.book.read(item.path), "lxml").find("title")) or Path(item.path).stem
            display, number_label, title = parse_label(label)
            marker = bool(CHAPTER_RE.match(label) or CHAPTER_RE.match(htext))
            if not marker:
                marker = bool(heading and "chaptertitle" in " ".join(heading.get("class", [])).lower())
            pages.append({
                "source_files": [item.path],
                "label": label,
                "display_title": display,
                "title": title,
                "number_label": number_label,
                "number_short": number_short(number_label),
                "marker": marker,
                "heading": htext,
                "words": len(text.split()),
                "type": "chapter",
                "id": "",
                "route": "",
            })

        # Where do the chapters start?
        chapter_start = next((i for i, p in enumerate(pages) if p["marker"]), None)
        if chapter_start is None:
            book_title = normalize_text(self.book.metadata.get("title", "")).lower()
            for i, p in enumerate(pages):
                label = normalize_text(p["label"]).lower()
                if label in FRONT_LABELS or label == book_title:
                    continue
                chapter_start = i
                break
        if chapter_start is None:
            chapter_start = 0

        for i, page in enumerate(pages):
            page["id"] = f"page-{i + 1}"
            page["route"] = f"/read/{i + 1}/"
            label = normalize_text(page["label"]).lower()
            if i < chapter_start:
                page["type"] = "frontmatter"
            elif any(label == b or label.startswith(b + " ") or b in label for b in BACK_LABELS):
                page["type"] = "backmatter"
            else:
                page["type"] = "chapter"
        return pages

    # -- conversion -------------------------------------------------------
    def _href(self, doc_path: str, href: str) -> str:
        if not href:
            return href
        if href.startswith(("http:", "https:", "mailto:", "tel:", "data:")):
            return href
        parts = urlsplit(href)
        if not parts.path:
            return f"#{parts.fragment}" if parts.fragment else href
        target, _ = self.book._resolve(doc_path, href)
        if target in self.route_by_path:
            return self.route_by_path[target] + (f"#{parts.fragment}" if parts.fragment else "")
        if target in self.images:
            return f"/images/{self.images[target]['name']}"
        return href

    @staticmethod
    def _anchors(el: Tag) -> str:
        parts = []
        if el.get("id"):
            parts.append(f'<span id="{html.escape(el["id"])}"></span>')
        for node in el.find_all(id=True):
            if node.name == "img":
                continue
            parts.append(str(node))
        return "".join(parts)

    def _inline(self, el: Tag, doc_path: str) -> str:
        for a in el.find_all("a", href=True):
            a["href"] = self._href(doc_path, a["href"])
        for img in el.find_all("img"):
            info = image_info(self.book, self.images, doc_path, img.get("src") or "")
            if info:
                img["src"] = f"/images/{info['name']}"
            img.attrs.pop("srcset", None)
        for tag in el.find_all(True):
            if tag.name not in ("table", "td", "th", "tr", "colgroup", "col"):
                tag.attrs.pop("class", None)
            tag.attrs.pop("style", None)
        return inner(el)

    def _clean_tree(self, el: Tag, doc_path: str) -> str:
        for a in el.find_all("a", href=True):
            a["href"] = self._href(doc_path, a["href"])
        for img in el.find_all("img"):
            info = image_info(self.book, self.images, doc_path, img.get("src") or "")
            if info:
                img["src"] = f"/images/{info['name']}"
            img.attrs.pop("srcset", None)
        for tag in el.find_all(True):
            if tag.name not in ("table", "td", "th", "tr", "colgroup", "col"):
                tag.attrs.pop("class", None)
            tag.attrs.pop("style", None)
        return str(el)

    def _image_html(self, img: Tag, doc_path: str, has_caption: bool, caption_id: str) -> str:
        src = img.get("src") or ""
        info = image_info(self.book, self.images, doc_path, src)
        if not info:
            return ""
        alt = img.get("alt") or ""
        if has_caption:
            alt = ""
        described = f' aria-describedby="{html.escape(caption_id)}"' if has_caption and caption_id else ""
        name = html.escape(info["name"])
        w = info["width"]
        h = info["height"]
        attrs = f'width="{w}" height="{h}"' if w and h else ""
        img_tag = f'<img src="/images/{name}" {attrs} alt="{html.escape(alt)}"{described} loading="lazy" decoding="async">'
        if info.get("webp"):
            picture = f'<picture><source srcset="/images/{html.escape(info["webp"])}" type="image/webp">{img_tag}</picture>'
        else:
            picture = img_tag
        return f'<a class="lightbox-link" href="/images/{name}" aria-label="View figure larger">{picture}</a>'

    def _figure(self, imgs: list[Tag], caps: list[Tag], doc_path: str, index: int) -> str:
        caption_html = "".join(f"<p>{self._inline(c, doc_path).strip()}</p>" for c in caps)
        caption_id = f"fig-{index}-caption"
        has_caption = bool(caption_html)
        body = "".join(self._image_html(img, doc_path, has_caption, caption_id) for img in imgs)
        if not body:
            return ""
        cls = "figure figure-multi" if len(imgs) > 1 else "figure"
        figcap = f'<figcaption id="{caption_id}">{caption_html}</figcaption>' if has_caption else ""
        return f'<figure class="{cls}" data-count="{len(imgs)}">{body}{figcap}</figure>'

    def _convert_page(self, page: dict, soup: BeautifulSoup) -> tuple[str, list[dict], list[str]]:
        body = soup.body
        blocks = [el for el in body.children if isinstance(el, Tag) and el.name in
                  ("p", "h1", "h2", "h3", "h4", "h5", "h6", "table", "ul", "ol", "blockquote", "figure", "img", "div")]
        # divs have been flattened in clean_doc; this is defensive.
        out: list[str] = []
        sections: list[dict] = []
        warnings: list[str] = []
        source_ids = {tag["id"] for tag in body.find_all(id=True) if tag.get("id")}
        used_ids: set[str] = set()
        fig_index = [0]
        first_para = True

        def add_id(el: Tag) -> str:
            text = heading_text(el)
            if el.get("id"):
                hid = el["id"]
            else:
                hid = f"s-{slugify(text)}"
                base = hid
                n = 2
                while hid in source_ids or hid in used_ids:
                    hid = f"{base}-{n}"
                    n += 1
            used_ids.add(hid)
            return hid

        def header_for(elements: list[Tag]) -> str:
            text = " ".join(heading_text(e) for e in elements).strip()
            inner_html = " ".join(self._inline(e, page["source_files"][0]).strip() for e in elements)
            display, number_label, title = parse_label(text)
            # Keep the source wording exactly; the split is only layout.
            if number_label and title and title != number_label:
                number_html = html.escape(number_label)
                title_html = html.escape(title)
            else:
                number_html = ""
                title_html = inner_html or html.escape(text)
            hid = next((e["id"] for e in elements if e.get("id")), "")
            if not hid:
                hid = f"ch-{slugify(page['title'])}"
            for e in elements:
                hid = hid or e.get("id", "")
            used_ids.add(hid)
            anchors = "".join(str(a) for e in elements for a in e.find_all(id=True))
            num = f'<p class="chapter-number">{number_html}</p>' if number_html else ""
            return (
                f'<header class="chapter-header" id="{html.escape(hid)}">'
                f'{anchors}{num}<h1 class="chapter-title">{title_html}</h1>'
                f'<p class="chapter-meta" data-chrome><!--READTIME--></p></header>'
            )

        i = 0
        # The first heading becomes the page header, preserving its text.
        if blocks:
            first = blocks[0]
            if first.name in ("h1", "h2", "h3") or "chaptertitle" in " ".join(first.get("class", [])).lower():
                consumed = [first]
                i = 1
                # "CHAPTER ONE" + title as two adjacent paragraphs/headings.
                if (first.name == "p" and "chaptertitle" in " ".join(first.get("class", [])).lower()
                        and i < len(blocks)
                        and (blocks[i].name in ("h1", "h2", "h3")
                             or "chaptertitle" in " ".join(blocks[i].get("class", [])).lower())):
                    consumed.append(blocks[i])
                    i += 1
                out.append(header_for(consumed))
            else:
                out.append(
                    f'<header class="chapter-header" data-chrome>'
                    f'<h1 class="chapter-title">{html.escape(page["title"])}</h1>'
                    f'<p class="chapter-meta" data-chrome><!--READTIME--></p></header>'
                )
        else:
            out.append(
                f'<header class="chapter-header" data-chrome>'
                f'<h1 class="chapter-title">{html.escape(page["title"])}</h1>'
                f'<p class="chapter-meta" data-chrome><!--READTIME--></p></header>'
            )

        while i < len(blocks):
            el = blocks[i]
            name = el.name
            cls = " ".join(el.get("class", [])).lower()

            if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
                level = {"h1": 2, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}[name]
                level = min(level, 4)
                tag = {2: "h2", 3: "h3", 4: "h4"}[level]
                hid = add_id(el)
                c = {2: "section-title", 3: "subsection-title", 4: "subsubsection-title"}[level]
                out.append(f'<{tag} class="{c}" id="{html.escape(hid)}">{self._inline(el, page["source_files"][0]).strip()}</{tag}>')
                if page["type"] == "chapter" and level == 2:
                    sections.append({"level": level, "id": hid, "title": heading_text(el)})
                i += 1
                continue

            if name == "img":
                imgs = [el]
                j = i + 1
                while j < len(blocks) and blocks[j].name == "img":
                    imgs.append(blocks[j])
                    j += 1
                caps = []
                while j < len(blocks) and "caption" in " ".join(blocks[j].get("class", [])).lower():
                    caps.append(blocks[j])
                    j += 1
                fig_index[0] += 1
                fig = self._figure(imgs, caps, page["source_files"][0], fig_index[0])
                if fig:
                    out.append(fig)
                i = j
                continue

            if "image" in cls or (name == "p" and el.find("img")):
                if name == "p" and el.get_text(strip=True):
                    pcls = ' class="lede"' if page["type"] == "chapter" and first_para else ""
                    if pcls:
                        first_para = False
                    pid = f' id="{html.escape(el["id"])}"' if el.get("id") else ""
                    out.append(f"<p{pid}{pcls}>{self._inline(el, page['source_files'][0]).strip()}</p>")
                    i += 1
                    continue
                imgs = el.find_all("img")
                anchors = self._anchors(el)
                j = i + 1
                while j < len(blocks) and ("image" in " ".join(blocks[j].get("class", [])).lower()
                                           or (blocks[j].name == "p" and blocks[j].find("img"))):
                    imgs.extend(blocks[j].find_all("img"))
                    anchors += self._anchors(blocks[j])
                    j += 1
                caps = []
                while j < len(blocks) and ("caption" in " ".join(blocks[j].get("class", [])).lower()
                                           or blocks[j].name == "figcaption"):
                    caps.append(blocks[j])
                    j += 1
                fig_index[0] += 1
                fig = self._figure(imgs, caps, page["source_files"][0], fig_index[0])
                if fig:
                    out.append(anchors + fig)
                i = j
                continue

            if "caption" in cls:
                out.append(f'<p class="orphan-caption">{self._inline(el, page["source_files"][0]).strip()}</p>')
                i += 1
                continue

            if name in ("ul", "ol"):
                el.attrs.pop("class", None)
                el["class"] = "book-list"
                out.append(self._clean_tree(el, page["source_files"][0]))
                i += 1
                continue

            if name == "blockquote":
                el.attrs.pop("class", None)
                el["class"] = "book-quote"
                out.append(self._clean_tree(el, page["source_files"][0]))
                i += 1
                continue

            if name == "table":
                classes = list(el.get("class", []))
                if "book-table" not in classes:
                    classes.insert(0, "book-table")
                el["class"] = classes
                out.append(f'<div class="table-wrap">{self._clean_tree(el, page["source_files"][0])}</div>')
                i += 1
                continue

            if name == "figure":
                fig_index[0] += 1
                imgs = el.find_all("img")
                caps = el.find_all("figcaption")
                out.append(self._anchors(el) + self._figure(imgs, caps, page["source_files"][0], fig_index[0]))
                i += 1
                continue

            # Paragraph-like blocks.
            if "quote" in cls or "epigraph" in cls:
                items = []
                j = i
                while j < len(blocks) and ("quote" in " ".join(blocks[j].get("class", [])).lower()
                                           or "epigraph" in " ".join(blocks[j].get("class", [])).lower()):
                    items.append(f"<p>{self._inline(blocks[j], page["source_files"][0]).strip()}</p>")
                    j += 1
                out.append('<blockquote class="book-quote quote-epigraph">' + "".join(items) + "</blockquote>")
                i = j
                continue

            if "list" in cls or "bullet" in cls:
                items = []
                j = i
                start = 1
                while j < len(blocks) and ("list" in " ".join(blocks[j].get("class", [])).lower()
                                           or "bullet" in " ".join(blocks[j].get("class", [])).lower()):
                    item = blocks[j]
                    m = strip_leading(item, r"^\s*(?:[•·]|\d+\.)\s*")
                    if m and m.group(0).strip().endswith("."):
                        try:
                            start = int(re.match(r"\d+", m.group(0)).group(0))
                        except Exception:
                            pass
                    items.append(f"<li>{self._inline(item, page["source_files"][0]).strip()}</li>")
                    j += 1
                tag = "ol" if start != 1 else "ul"
                attr = f' start="{start}"' if tag == "ol" and start != 1 else ""
                out.append(f'<{tag} class="book-list"{attr}>' + "".join(items) + f"</{tag}>")
                i = j
                continue

            if "subhead" in cls or "section" in cls or "heading" in cls:
                if "subheading5" in cls:
                    level = 4
                elif "subheading4" in cls:
                    level = 3
                elif "subheading" in cls or "section" in cls:
                    level = 2
                elif "subhead" in cls:
                    level = 3
                else:
                    level = 2
                tag = {2: "h2", 3: "h3", 4: "h4"}[level]
                hid = add_id(el)
                c = "subsection-title" if level == 3 else "section-title"
                out.append(f'<{tag} class="{c}" id="{html.escape(hid)}">{self._inline(el, page["source_files"][0]).strip()}</{tag}>')
                if page["type"] == "chapter" and level == 2:
                    sections.append({"level": level, "id": hid, "title": heading_text(el)})
                i += 1
                continue

            if not el.get_text(strip=True) and not el.find("img"):
                anchors = "".join(str(a) for a in el.find_all(id=True))
                if anchors:
                    out.append(anchors)
                i += 1
                continue

            pcls = ' class="lede"' if page["type"] == "chapter" and first_para else ""
            if pcls:
                first_para = False
            pid = f' id="{html.escape(el["id"])}"' if el.get("id") else ""
            out.append(f"<p{pid}{pcls}>{self._inline(el, page["source_files"][0]).strip()}</p>")
            i += 1

        return "".join(out), sections, warnings

    # -- output -----------------------------------------------------------
    def _write_pages(self, fragments: dict[str, str]) -> None:
        for pid, fragment in fragments.items():
            (self.pages_dir / f"{pid}.html").write_text(fragment, encoding="utf-8")

    def _write_toc(self) -> None:
        toc = []
        chapters = 0
        for page in self.pages:
            if page["type"] == "chapter":
                chapters += 1
                toc.append({
                    "kind": "chapter",
                    "number": page["number_short"] or str(chapters),
                    "label": page["title"],
                    "href": page["route"],
                    "generated": False,
                })
            else:
                toc.append({
                    "kind": "entry",
                    "label": page["display_title"],
                    "href": page["route"],
                    "generated": False,
                })
            for section in page["sections"]:
                toc.append({
                    "kind": "section",
                    "label": section["title"],
                    "href": f"{page['route']}#{section['id']}",
                    "generated": False,
                })
        self.toc = toc
        self.chapter_count = chapters

    def _write_book(self, source_text: dict[str, str]) -> None:
        md = self.book.metadata
        title = md.get("title") or self.epub_path.stem
        short = re.split(r"\s*[:\u2014]\s*", title, maxsplit=1)[0].strip() or title
        subtitle = ""
        m = re.split(r"\s*[:\u2014]\s*", title, maxsplit=1)
        if len(m) == 2:
            subtitle = m[1].strip()
        year = (md.get("date") or "")[:4]
        cover = self.cover_info["name"] if self.cover_info else ""
        cover_webp = self.cover_info.get("webp", "") if self.cover_info else ""

        pages = []
        for page in self.pages:
            pages.append({
                "id": page["id"],
                "type": page["type"],
                "route": page["route"],
                "title": page["title"],
                "display_title": page["display_title"],
                "short_title": page["title"],
                "number": page.get("number_short", ""),
                "source_files": page["source_files"],
                "sections": page["sections"],
                "words": page["words"],
                "figure_count": page.get("figure_count", 0),
                "note_count": page.get("note_count", 0),
                "warnings": page.get("warnings", []),
            })

        stats = {
            "words": sum(p["words"] for p in pages),
            "chapter_words": sum(p["words"] for p in pages if p["type"] == "chapter"),
            "chapters": self.chapter_count,
            "figures": sum(p.get("figure_count", 0) for p in pages),
            "notes": sum(p.get("note_count", 0) for p in pages),
            "images": len(self.images),
        }

        self.book_data = {
            "meta": {
                "title": title,
                "short_title": short,
                "subtitle": subtitle,
                "author": md.get("creator", ""),
                "publisher": md.get("publisher", ""),
                "date": md.get("date", ""),
                "year": year,
                "isbn": md.get("isbn", ""),
                "language": md.get("language", "en"),
                "description": md.get("description", ""),
                "rights": md.get("rights", ""),
                "cover": cover,
                "cover_webp": cover_webp,
                "cover_width": self.cover_info["width"] if self.cover_info else 0,
                "cover_height": self.cover_info["height"] if self.cover_info else 0,
                "edition": "",
                "source": "EPUB",
            },
            "pages": pages,
            "toc": self.toc,
            "reading_order": [p["id"] for p in pages],
            "stats": stats,
        }
        (self.content_dir / "book.json").write_text(
            json.dumps(self.book_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (self.content_dir / "source-text.json").write_text(
            json.dumps(source_text, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (self.content_dir / "notes-popover.json").write_text("{}\n", encoding="utf-8")
