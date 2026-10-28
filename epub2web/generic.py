"""Generic EPUB → semantic page fragments.

This is the deterministic, heuristic path. It handles ordinary EPUB 2/3
markup: semantic headings, paragraphs, lists, tables, figures, images, and
notes links. For print-conversion class soup it applies conservative class
heuristics. The fidelity gate verifies every rendered page against the source
before a build can succeed.
"""

from __future__ import annotations

import base64
import binascii
import contextlib
import hashlib
import html
import io
import json
import logging
import re
import warnings
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, NavigableString, Tag, XMLParsedAsHTMLWarning
from PIL import Image, ImageOps

from .epub import Epub
from .progress import ProgressCallback, report
from .text import (
    inner,
    match_key,
    normalize_text,
    slugify,
    split_title,
    strip_leading,
    text_of,
    year_from_date,
)

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
logger = logging.getLogger(__name__)

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

DANGEROUS_TAGS = (
    "script",
    "style",
    "noscript",
    "nav",
    "iframe",
    "frame",
    "frameset",
    "object",
    "embed",
    "applet",
    "form",
    "input",
    "button",
    "textarea",
    "select",
    "option",
    "optgroup",
    "link",
    "meta",
    "base",
    "template",
    "svg",
    "video",
    "audio",
    "source",
    "track",
    "canvas",
)
DANGEROUS_ATTRS = {
    "style",
    "srcdoc",
    "formaction",
    "action",
    "background",
    "poster",
    "ping",
    "xlink:href",
    "srcset",
    "imagesrcset",
    "sizes",
}
UNSAFE_URL_PREFIXES = (
    "javascript:",
    "vbscript:",
    "file:",
    "data:text/html",
    "data:application/xhtml",
    "data:image/svg",
)
DATA_IMAGE_RE = re.compile(
    r"^data:image/(png|jpe?g|gif|webp|avif);base64,([A-Za-z0-9+/=\s]+)$",
    re.IGNORECASE | re.DOTALL,
)
RASTER_EXTENSIONS = {
    "jpeg": ".jpg",
    "png": ".png",
    "gif": ".gif",
    "webp": ".webp",
    "avif": ".avif",
}


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


def safe_url(value: str, tag_name: str = "", attribute: str = "") -> bool:
    compact = re.sub(r"[\x00-\x20]+", "", value or "").lower()
    if not compact:
        return True
    if compact.startswith(UNSAFE_URL_PREFIXES):
        return False
    return not (
        tag_name == "img"
        and attribute == "src"
        and compact.startswith("data:")
        and not compact.startswith("data:image/")
    )


SVG_DANGEROUS_TAGS = {
    "script",
    "style",
    "foreignobject",
    "iframe",
    "object",
    "embed",
    "audio",
    "video",
    "animate",
    "animatemotion",
    "animatetransform",
    "set",
    "discard",
    "handler",
}
SVG_DANGEROUS_ATTRS = {
    "action",
    "attributename",
    "formaction",
    "srcdoc",
    "src",
    "style",
    "xml:base",
}
SVG_UNSAFE_VALUE_RE = re.compile(r"(?:javascript|vbscript|file|data)\s*:", re.IGNORECASE)
SVG_URL_RE = re.compile(r"url\(\s*['\"]?([^)'\"]+)['\"]?\s*\)", re.IGNORECASE)


def sanitize_svg(data: bytes) -> bytes:
    soup = BeautifulSoup(data, "xml")
    if soup.find() is None:
        raise ValueError("empty SVG")
    for el in soup.find_all(True):
        if el.name.lower() in SVG_DANGEROUS_TAGS:
            el.decompose()
    for tag in soup.find_all(True):
        for attr in list(tag.attrs):
            name = attr.lower()
            value = str(tag.attrs[attr])
            compact = re.sub(r"[\x00-\x20]+", "", value).lower()
            if name.startswith("on") or name in SVG_DANGEROUS_ATTRS:
                del tag.attrs[attr]
                continue
            if name in ("href", "xlink:href"):
                if not compact.startswith("#"):
                    del tag.attrs[attr]
                continue
            if SVG_UNSAFE_VALUE_RE.search(compact):
                del tag.attrs[attr]
                continue
            if "url(" in compact:
                targets = [
                    re.sub(r"[\x00-\x20]+", "", match).lower()
                    for match in SVG_URL_RE.findall(value)
                ]
                if not targets or any(not target.startswith("#") for target in targets):
                    del tag.attrs[attr]
    return str(soup).encode("utf-8")


def svg_size(data: bytes) -> tuple[int, int]:
    soup = BeautifulSoup(data, "xml")
    svg = soup.find("svg")
    if svg is None:
        return 0, 0

    def length(value) -> float:
        match = re.match(r"^\s*([0-9.]+)(?:px)?\s*$", str(value or ""), re.IGNORECASE)
        return float(match.group(1)) if match else 0.0

    width, height = length(svg.get("width")), length(svg.get("height"))
    if not (width and height):
        viewbox = re.split(r"[\s,]+", str(svg.get("viewBox") or "").strip())
        if len(viewbox) == 4:
            width, height = length(viewbox[2]), length(viewbox[3])
    return (int(width), int(height)) if width > 0 and height > 0 else (0, 0)


def dedupe_fragment_ids(fragment: str) -> str:
    """Keep the first occurrence of every id in a generated page fragment."""
    soup = BeautifulSoup(fragment, "lxml")
    root = soup.body or soup
    seen: set[str] = set()
    for tag in root.find_all(id=True):
        value = tag["id"]
        if value in seen:
            del tag["id"]
        else:
            seen.add(value)
    return "".join(
        str(child) if isinstance(child, Tag) else html.escape(str(child), quote=False)
        for child in root.contents
    )


def repair_malformed_external_hrefs(body: Tag) -> None:
    """Repair a common print-conversion typo: ``(https://...``.

    A leading parenthesis before an absolute URL makes the link relative. Keep
    the punctuation in the visible text, but normalize the href.
    """
    for a in body.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith("(") and href[1:].lower().startswith(("http://", "https://")):
            a["href"] = href[1:]


def repair_missing_note_anchors(soup: BeautifulSoup, body: Tag) -> None:
    """Add anchors for paired ``#fnN``/``#ffnN`` links when the EPUB lost ids.

    Some print-conversion pipelines keep footnote references and backlinks but
    strip the matching ``id`` attributes. Pair the two link forms and insert
    empty anchors so navigation works without changing the text.
    """
    existing = {tag["id"] for tag in body.find_all(id=True)}
    links = body.find_all("a", href=True)

    def href(link: Tag) -> str:
        return (link.get("href") or "").strip()

    for link in links:
        match = re.fullmatch(r"#fn(\d+)", href(link))
        if not match:
            continue
        target_id = f"fn{match.group(1)}"
        if target_id in existing:
            continue
        backlink = f"#ffn{match.group(1)}"
        item = next(
            (
                li
                for li in body.find_all("li")
                if any(href(candidate) == backlink for candidate in li.find_all("a", href=True))
            ),
            None,
        )
        if item is None:
            continue
        anchor = soup.new_tag("span")
        anchor["id"] = target_id
        item.insert(0, anchor)
        existing.add(target_id)

    for link in links:
        match = re.fullmatch(r"#ffn(\d+)", href(link))
        if not match:
            continue
        target_id = f"ffn{match.group(1)}"
        if target_id in existing:
            continue
        reference = next(
            (candidate for candidate in links if href(candidate) == f"#fn{match.group(1)}"),
            None,
        )
        if reference is None:
            continue
        anchor = soup.new_tag("span")
        anchor["id"] = target_id
        reference.insert_before(anchor)
        existing.add(target_id)


def clean_doc(soup: BeautifulSoup) -> BeautifulSoup:
    body = soup.body
    if body is None:
        return soup
    # Calibre and some other tools put the TOC target on <body id="...">.
    # Move that id onto the first content block so links to it survive.
    if body.get("id"):
        target = body.find(["h1", "h2", "h3", "h4", "h5", "h6", "p", "table", "figure"])
        if target is not None and not target.get("id"):
            target["id"] = body["id"]
        else:
            anchor = soup.new_tag("span")
            anchor["class"] = "anchor"
            anchor["id"] = body["id"]
            body.insert(0, anchor)
        del body["id"]
    # EPUBs are untrusted input. Strip active content and attributes that
    # could execute in the generated site or silently hide text from the
    # fidelity gate (for example, a source element with data-chrome).
    for img in body.find_all("img"):
        if not img.get("src"):
            for attribute in ("data-src", "data-original"):
                if img.get(attribute):
                    img["src"] = img[attribute]
                    break
        if not img.get("src") and img.get("srcset"):
            candidate = img["srcset"].split(",")[0].strip().split(" ")[0]
            if candidate:
                img["src"] = candidate
    for el in body.find_all(style=True):
        if "display:none" in el.get("style", "").replace(" ", "").lower():
            el.decompose()
    for el in body.find_all(DANGEROUS_TAGS):
        el.decompose()
    for tag in body.find_all(True):
        for attr in list(tag.attrs):
            name = attr.lower()
            if (
                name.startswith(("data-", "on"))
                or name in DANGEROUS_ATTRS
                or (name in ("href", "src") and not safe_url(str(tag.attrs[attr]), tag.name, name))
            ):
                del tag.attrs[attr]
    for el in body.find_all(attrs={"hidden": True}):
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
    for el in body.find_all(
        ["div", "section", "article", "main", "header", "footer", "aside", "hgroup", "center"]
    ):
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
    # Empty links are layout artefacts (often Gutenberg's linked-image
    # wrappers). They render nothing and can point outside the spine, so
    # keep their id as an anchor and drop the dead href.
    for a in body.find_all("a", href=True):
        if not a.get_text(strip=True) and not a.find(["img", "picture", "svg"]):
            if a.get("id"):
                span = soup.new_tag("span")
                span["class"] = "anchor"
                span["id"] = a["id"]
                a.replace_with(span)
            else:
                a.decompose()

    while True:
        span = body.find("span", id=False)
        if span is None:
            break
        span.unwrap()

    # Divs were flattened; prose that lived directly inside a div is now a
    # bare text node. Wrap each run of text/<br> so it is not lost.
    inline_tags = {
        "a",
        "abbr",
        "b",
        "bdi",
        "bdo",
        "br",
        "cite",
        "code",
        "data",
        "dfn",
        "em",
        "i",
        "img",
        "kbd",
        "mark",
        "q",
        "s",
        "samp",
        "small",
        "span",
        "strong",
        "sub",
        "sup",
        "time",
        "u",
        "var",
        "wbr",
    }

    def flush_run(run):
        if not run:
            return
        if not any(
            (isinstance(x, Tag) or (isinstance(x, NavigableString) and x.strip())) for x in run
        ):
            return
        paragraph = soup.new_tag("p")
        run[0].insert_before(paragraph)
        for node in run:
            paragraph.append(node.extract())

    run = []
    for child in list(body.children):
        if isinstance(child, NavigableString) or (
            isinstance(child, Tag) and child.name in inline_tags
        ):
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
        if tag.name not in (
            "p",
            "table",
            "td",
            "th",
            "tr",
            "colgroup",
            "col",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
        ):
            tag.attrs.pop("class", None)
        tag.attrs.pop("style", None)
    for tag in body.find_all(["table", "td", "th", "tr", "colgroup", "col"]):
        for attr in ("width", "height", "align", "valign", "cellpadding", "cellspacing", "border"):
            tag.attrs.pop(attr, None)

    # Some EPUBs repeat an id (usually a print page anchor). Keep the first
    # target; the id is a navigation artifact, not content.
    seen_ids: set[str] = set()
    for tag in body.find_all(id=True):
        value = tag["id"]
        if value in seen_ids:
            del tag["id"]
        else:
            seen_ids.add(value)

    repair_malformed_external_hrefs(body)
    repair_missing_note_anchors(soup, body)
    return soup


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


def class_names(el: Tag) -> str:
    return " ".join(el.get("class", [])).lower()


def heading_text(el: Tag) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()


def first_heading(soup: BeautifulSoup) -> Tag | None:
    body = soup.body
    if body is None:
        return None
    # Chapter markers from print conversions take priority.
    for p in body.find_all("p"):
        cls = class_names(p)
        if "chaptertitle" in cls:
            return p
    for tag in ("h1", "h2", "h3", "h4"):
        el = body.find(tag)
        if el is not None and el.get_text(strip=True):
            return el
    for p in body.find_all("p"):
        cls = class_names(p)
        if (
            any(k in cls for k in ("title", "heading", "subhead"))
            and len(p.get_text(" ", strip=True)) < 140
        ):
            return p
    return None


def image_info(epub: Epub, images: dict, doc_path: str, src: str) -> dict | None:
    src = (src or "").strip()
    if not src:
        return None
    if src.startswith("data:"):
        return images.get(src)
    if src.startswith(("http:", "https:", "//")):
        return None
    path, _ = epub._resolve(doc_path, src)
    return images.get(path)


class GenericExtractor:
    def __init__(
        self,
        epub_path: str | Path,
        content_dir: str | Path,
        images_dir: str | Path,
        progress: ProgressCallback | None = None,
        clean_images: bool = False,
    ):
        self.epub_path = Path(epub_path)
        self.content_dir = Path(content_dir)
        self.pages_dir = self.content_dir / "pages"
        self.images_dir = Path(images_dir)
        self.progress = progress
        self.clean_images = clean_images
        self.book: Epub | None = None
        self.items: list = []
        self.cleaned: dict[str, BeautifulSoup] = {}
        self.cover_info: dict | None = None
        self.cover_source = ""
        self.images: dict[str, dict] = {}
        self.image_errors: list[str] = []
        self.pages: list[dict] = []
        self.page_by_path: dict[str, dict] = {}
        self.route_by_path: dict[str, str] = {}
        self.nav_labels: dict[str, str] = {}
        self.toc: list[dict] = []
        self.chapter_count = 0
        self.book_data: dict = {}

    def _report(self, phase: str, label: str, current: int, total: int) -> None:
        report(self.progress, phase, label, current, total)

    # -- page planning ----------------------------------------------------
    def run(self) -> dict:
        logger.info("extracting book", extra={"epub": str(self.epub_path)})
        self.content_dir.mkdir(parents=True, exist_ok=True)
        self.pages_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)
        if self.clean_images:
            for path in self.images_dir.glob("*"):
                if path.is_file():
                    path.unlink()

        self.image_errors: list[str] = []
        self.cover_source = ""
        with Epub(self.epub_path) as book:
            self.book = book
            self.items = list(book.html_spine())
            if not self.items:
                raise ValueError("EPUB spine contains no readable HTML documents")
            self.nav_labels = {}
            for entry in book.toc_flat():
                if entry.path and entry.label:
                    self.nav_labels.setdefault(entry.path, entry.label)
            logger.debug("spine documents", extra={"count": len(self.items)})
            self.cleaned: dict[str, BeautifulSoup] = {}
            total_docs = len(self.items)
            self._report("read", "Opening book", 0, total_docs)
            for index, item in enumerate(self.items, 1):
                try:
                    soup = BeautifulSoup(book.read(item.path), "lxml")
                except Exception as exc:
                    raise ValueError(f"could not parse {item.path}: {exc}") from exc
                self.cleaned[item.path] = clean_doc(soup)
                self._report("read", "Opening book", index, total_docs)

            self.cover_info = self._process_cover()
            self.images = self._process_images()
            logger.info("images processed", extra={"count": len(self.images)})
            if self.image_errors:
                shown = "\n  ".join(self.image_errors[:8])
                extra = len(self.image_errors) - 8
                if extra > 0:
                    shown += f"\n  … and {extra} more"
                logger.error("image references failed", extra={"count": len(self.image_errors)})
                raise ValueError(f"could not process image references:\n  {shown}")

            self.pages = self._plan_pages()
            logger.debug("pages planned", extra={"count": len(self.pages)})
            if not self.pages:
                raise ValueError("no readable pages found in the EPUB spine")
            self.route_by_path = {p["source_files"][0]: p["route"] for p in self.pages}

            fragments = {}
            source_text = {}
            total_pages = len(self.pages)
            self._report("extract-pages", "Laying out pages", 0, total_pages)
            for index, page in enumerate(self.pages, 1):
                path = page["source_files"][0]
                soup = self.cleaned[path]
                page["images"] = len(soup.body.find_all("img")) if soup.body else 0
                source_text[path] = normalize_text(text_of(soup.body))
                fragment, sections = self._convert_page(page, soup)
                page["sections"] = sections
                page["figure_count"] = fragment.count("<figure")
                page["words"] = len(source_text[path].split())
                fragments[page["id"]] = fragment
                self._report("extract-pages", "Laying out pages", index, total_pages)

            self.pages = [p for p in self.pages if p["id"] in fragments]
            if not self.pages:
                raise ValueError("no readable pages found in the EPUB spine")
            self.page_by_path = {p["source_files"][0]: p for p in self.pages}
            self.route_by_path = {p["source_files"][0]: p["route"] for p in self.pages}

            self._report("extract-write", "Saving book data", 0, 1)
            self._write_toc()
            self._write_pages(fragments)
            self._write_book(source_text)
            self._report("extract-write", "Saving book data", 1, 1)
            stats = self.book_data.get("stats", {})
            logger.info(
                "book extracted",
                extra={
                    "pages": len(self.pages),
                    "words": stats.get("words", 0),
                    "figures": stats.get("figures", 0),
                    "images": stats.get("images", 0),
                },
            )
            return self.book_data

    # -- images -----------------------------------------------------------
    def _unique_image_name(self, stem: str, suffix: str, used: set[str]) -> str:
        name = f"{stem}{suffix}"
        n = 2
        while name in used:
            name = f"{stem}-{n}{suffix}"
            n += 1
        used.add(name)
        return name

    def _write_image(
        self,
        data: bytes,
        stem: str,
        suffix: str,
        used: set[str],
        origin: str,
    ) -> dict | None:
        stem = slugify(stem, fallback="image")
        suffix = (suffix or "").lower()
        if suffix == ".jpeg":
            suffix = ".jpg"
        if suffix == ".svg" or b"<svg" in data.lstrip()[:256].lower():
            try:
                data = sanitize_svg(data)
            except Exception as exc:
                self.image_errors.append(f"{origin}: invalid SVG ({exc})")
                return None
            name = self._unique_image_name(stem, ".svg", used)
            (self.images_dir / name).write_bytes(data)
            width, height = svg_size(data)
            return {"name": name, "webp": "", "width": width, "height": height}

        try:
            im = Image.open(io.BytesIO(data))
            im.load()
            fmt = (im.format or "").lower()
            frames = getattr(im, "n_frames", 1)
        except Exception:
            self.image_errors.append(f"{origin}: image could not be decoded")
            return None
        with contextlib.suppress(Exception):
            im = ImageOps.exif_transpose(im)

        extension = RASTER_EXTENSIONS.get(fmt)
        if extension is None:
            try:
                converted = im.convert("RGBA" if im.mode in ("RGBA", "LA", "P") else "RGB")
                buffer = io.BytesIO()
                converted.save(buffer, "PNG")
                data = buffer.getvalue()
                im = converted
                extension = ".png"
            except Exception:
                self.image_errors.append(f"{origin}: unsupported image format {fmt or 'unknown'}")
                return None

        name = self._unique_image_name(stem, extension, used)
        (self.images_dir / name).write_bytes(data)
        info = {"name": name, "webp": "", "width": im.width, "height": im.height}
        if extension in (".webp", ".avif") or frames > 1:
            return info
        try:
            if im.mode in ("RGB", "L", "RGBA", "LA"):
                webp_im = im
            elif im.mode == "P" and "transparency" in im.info:
                webp_im = im.convert("RGBA")
            else:
                webp_im = im.convert("RGB")
            webp_name = self._unique_image_name(Path(name).stem, ".webp", used)
            webp_im.save(self.images_dir / webp_name, "WEBP", quality=86, method=6)
            info["webp"] = webp_name
        except Exception:
            pass
        return info

    def _process_cover(self) -> dict | None:
        item = self.book.cover_item
        if item is None:
            return None
        self.cover_source = item.path
        try:
            data = self.book.read(item.path)
        except KeyError as exc:
            raise ValueError(f"cover image is missing from the EPUB: {item.path}") from exc
        info = self._write_image(
            data,
            "cover",
            Path(item.path).suffix,
            set(),
            f"cover {item.path}",
        )
        if info is None:
            raise ValueError(f"cover image could not be processed: {item.path}")
        return info

    def _process_data_image(
        self,
        src: str,
        doc_path: str,
        used: set[str],
    ) -> dict | None:
        match = DATA_IMAGE_RE.match(src.strip())
        if not match:
            self.image_errors.append(f"{doc_path}: unsupported data URI image")
            return None
        try:
            data = base64.b64decode(re.sub(r"\s+", "", match.group(2)), validate=True)
        except (binascii.Error, ValueError):
            self.image_errors.append(f"{doc_path}: invalid base64 data URI image")
            return None
        subtype = match.group(1).lower().replace("jpg", "jpeg")
        stem = f"inline-{hashlib.sha256(data).hexdigest()[:12]}"
        return self._write_image(
            data,
            stem,
            RASTER_EXTENSIONS[subtype],
            used,
            f"{doc_path}: embedded data URI image",
        )

    def _process_images(self) -> dict[str, dict]:
        used: set[str] = set()
        if self.cover_info:
            used.add(self.cover_info["name"])
            if self.cover_info.get("webp"):
                used.add(self.cover_info["webp"])
        result: dict[str, dict] = {}
        image_tags = [
            (doc_path, img)
            for doc_path, soup in self.cleaned.items()
            for img in soup.find_all("img")
        ]
        total = len(image_tags)
        if total:
            self._report("extract-images", "Preparing images", 0, total)
        else:
            self._report("extract-images", "No images to prepare", 1, 1)

        for index, (doc_path, img) in enumerate(image_tags, 1):
            try:
                src = (img.get("src") or "").strip()
                if not src:
                    self.image_errors.append(f"{doc_path}: image has no src")
                    continue
                if src.startswith("data:"):
                    if src in result:
                        continue
                    info = self._process_data_image(src, doc_path, used)
                    if info:
                        result[src] = info
                    continue
                if src.startswith(("http:", "https:", "//")):
                    self.image_errors.append(f"{doc_path}: remote image is not supported: {src}")
                    continue
                path, _ = self.book._resolve(doc_path, src)
                if not path:
                    self.image_errors.append(f"{doc_path}: invalid image reference: {src}")
                    continue
                if path in result:
                    continue
                if self.cover_source and path == self.cover_source:
                    result[path] = dict(self.cover_info)
                    continue
                try:
                    data = self.book.read(path)
                except KeyError:
                    self.image_errors.append(
                        f"{doc_path}: image is missing from the EPUB: {src} ({path})"
                    )
                    continue
                info = self._write_image(
                    data,
                    Path(path).stem,
                    Path(path).suffix,
                    used,
                    f"{doc_path}: {src}",
                )
                if info:
                    result[path] = info
            finally:
                if total:
                    self._report("extract-images", "Preparing images", index, total)
        return result

    # -- planning ---------------------------------------------------------
    def _nav_label(self, path: str) -> str:
        return self.nav_labels.get(path, "")

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
                label = htext or self.book._text(soup.find("title")) or Path(item.path).stem
            display, number_label, title = parse_label(label)
            heading_class = class_names(heading) if heading else ""
            kind = marker_kind(label, htext, heading_class)
            pages.append(
                {
                    "source_files": [item.path],
                    "label": label,
                    "display_title": display,
                    "title": title,
                    "number_label": number_label,
                    "number_short": number_short(number_label),
                    "marker": bool(kind),
                    "marker_kind": kind,
                    "heading": htext,
                    "words": len(text.split()),
                    "type": "chapter",
                    "id": "",
                    "route": "",
                }
            )

        # Where do the chapters start?
        chapter_start = next((i for i, p in enumerate(pages) if p["marker"]), None)
        if chapter_start is None:
            book_title = match_key(self.book.metadata.get("title", ""))
            for i, p in enumerate(pages):
                if label_matches(p["label"], FRONT_LABELS):
                    continue
                if book_title and match_key(p["label"]) == book_title:
                    continue
                chapter_start = i
                break
        if chapter_start is None:
            chapter_start = 0

        chapter_markers = [i for i, p in enumerate(pages) if p.get("marker_kind") == "chapter"]
        last_chapter = max(chapter_markers, default=-1)
        back_start = len(pages)
        search_from = max(chapter_start, last_chapter + 1)
        for i, page in enumerate(pages):
            if i >= search_from and label_matches(page["label"], BACK_LABELS):
                back_start = i
                break
        if chapter_markers and back_start == len(pages):
            back_start = last_chapter + 1

        for i, page in enumerate(pages):
            page["id"] = f"page-{i + 1}"
            page["route"] = f"/read/{i + 1}/"
            kind = page.get("marker_kind", "")
            if i < chapter_start:
                page["type"] = "frontmatter"
            elif i >= back_start:
                page["type"] = "backmatter"
            elif kind == "part":
                page["type"] = "part"
            elif kind == "chapter":
                page["type"] = "chapter"
            elif page["words"] < 50 and page["label"].isupper():
                # Short all-caps divider pages are part headings.
                page["type"] = "part"
            else:
                page["type"] = "chapter"
        return pages

    # -- conversion -------------------------------------------------------
    def _href(self, doc_path: str, href: str) -> str:
        if not href:
            return href
        if href.startswith(("http:", "https:", "ftp:", "//", "mailto:", "tel:", "data:")):
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

    def _prepare_html(self, el: Tag, doc_path: str) -> None:
        for a in el.find_all("a", href=True):
            a["href"] = self._href(doc_path, a["href"])
        for img in el.find_all("img"):
            info = image_info(self.book, self.images, doc_path, img.get("src") or "")
            if info:
                img["src"] = f"/images/{info['name']}"
            img.attrs.pop("srcset", None)
        for tag in el.find_all(True):
            tag.attrs.pop("class", None)
            tag.attrs.pop("style", None)

    def _inline(self, el: Tag, doc_path: str) -> str:
        self._prepare_html(el, doc_path)
        return inner(el)

    def _clean_tree(self, el: Tag, doc_path: str) -> str:
        self._prepare_html(el, doc_path)
        return str(el)

    def _image_html(self, img: Tag, doc_path: str, has_caption: bool, caption_id: str) -> str:
        src = img.get("src") or ""
        info = image_info(self.book, self.images, doc_path, src)
        if not info:
            return ""
        alt = img.get("alt") or ""
        if has_caption:
            alt = ""
        described = (
            f' aria-describedby="{html.escape(caption_id)}"' if has_caption and caption_id else ""
        )
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

    def _convert_page(self, page: dict, soup: BeautifulSoup) -> tuple[str, list[dict]]:
        body = soup.body
        source_path = page["source_files"][0]
        blocks = [
            el
            for el in body.children
            if isinstance(el, Tag)
            and el.name
            in (
                "p",
                "h1",
                "h2",
                "h3",
                "h4",
                "h5",
                "h6",
                "table",
                "ul",
                "ol",
                "blockquote",
                "figure",
                "img",
                "picture",
                "div",
                "address",
                "dl",
                "pre",
                "math",
            )
        ]
        # divs have been flattened in clean_doc; this is defensive.
        out: list[str] = []
        sections: list[dict] = []
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
            anchors_parts: list[str] = []
            anchor_tags: list[Tag] = []
            has_content_link = False
            for e in elements:
                for tag in e.find_all(id=True):
                    if tag.get_text(strip=True):
                        # A real link in the heading (usually a footnote
                        # marker) must stay in the title and keep its id.
                        has_content_link = True
                    elif tag.name in ("a", "span") and not tag.find(True):
                        # Empty anchors mark a chapter location. Move them
                        # outside the generated heading so their ids survive.
                        anchor_tags.append(tag)
                        anchors_parts.append(f'<span id="{html.escape(tag["id"])}"></span>')
            anchors = "".join(anchors_parts)
            for tag in anchor_tags:
                tag.attrs.pop("id", None)
            inner_html = " ".join(self._inline(e, source_path).strip() for e in elements)
            _, number_label, title = parse_label(text)
            # Keep the source wording exactly; the split is only layout. If
            # the heading contains a footnote/link marker, keep the whole
            # heading as the title so the marker is not duplicated or lost.
            if has_content_link:
                number_html = ""
                title_html = inner_html or html.escape(text)
            elif number_label and title and title != number_label:
                number_html = html.escape(number_label)
                title_html = html.escape(title)
            else:
                number_html = ""
                title_html = inner_html or html.escape(text)
            hid = next((e["id"] for e in elements if e.get("id")), "")
            if not hid:
                hid = f"ch-{slugify(page['title'])}"
            used_ids.add(hid)
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
            if first.name in ("h1", "h2", "h3") or "chaptertitle" in class_names(first):
                consumed = [first]
                i = 1
                # "CHAPTER ONE" + title as two adjacent paragraphs/headings.
                if (
                    first.name == "p"
                    and "chaptertitle" in class_names(first)
                    and i < len(blocks)
                    and (
                        blocks[i].name in ("h1", "h2", "h3")
                        or "chaptertitle" in class_names(blocks[i])
                    )
                ):
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
            cls = class_names(el)

            if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
                level = {"h1": 2, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}[name]
                level = min(level, 4)
                tag = {2: "h2", 3: "h3", 4: "h4"}[level]
                hid = add_id(el)
                c = {2: "section-title", 3: "subsection-title", 4: "subsubsection-title"}[level]
                out.append(
                    f'<{tag} class="{c}" id="{html.escape(hid)}">{self._inline(el, source_path).strip()}</{tag}>'
                )
                if page["type"] == "chapter" and level in (2, 3):
                    sections.append({"level": level, "id": hid, "title": heading_text(el)})
                i += 1
                continue

            if name in ("img", "picture"):
                imgs = [el] if name == "img" else el.find_all("img")
                j = i + 1
                while j < len(blocks) and blocks[j].name == "img":
                    imgs.append(blocks[j])
                    j += 1
                caps = []
                while j < len(blocks) and "caption" in class_names(blocks[j]):
                    caps.append(blocks[j])
                    j += 1
                fig_index[0] += 1
                fig = self._figure(imgs, caps, source_path, fig_index[0])
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
                    out.append(
                        f"<p{pid}{pcls}>{self._inline(el, page['source_files'][0]).strip()}</p>"
                    )
                    i += 1
                    continue
                imgs = el.find_all("img")
                anchors = self._anchors(el)
                j = i + 1
                while j < len(blocks):
                    nxt = blocks[j]
                    nxt_cls = class_names(nxt)
                    image_only = (
                        nxt.name == "p" and nxt.find("img") and not nxt.get_text(strip=True)
                    )
                    if not (("image" in nxt_cls and not nxt.get_text(strip=True)) or image_only):
                        break
                    imgs.extend(nxt.find_all("img"))
                    anchors += self._anchors(nxt)
                    j += 1
                caps = []
                while j < len(blocks) and (
                    "caption" in class_names(blocks[j]) or blocks[j].name == "figcaption"
                ):
                    caps.append(blocks[j])
                    j += 1
                fig_index[0] += 1
                fig = self._figure(imgs, caps, source_path, fig_index[0])
                if fig:
                    out.append(anchors + fig)
                i = j
                continue

            if "caption" in cls:
                out.append(f'<p class="orphan-caption">{self._inline(el, source_path).strip()}</p>')
                i += 1
                continue

            if name in ("ul", "ol"):
                el.attrs.pop("class", None)
                el["class"] = "book-list"
                out.append(self._clean_tree(el, source_path))
                i += 1
                continue

            if name == "dl":
                el.attrs.pop("class", None)
                el["class"] = "book-dl"
                out.append(self._clean_tree(el, source_path))
                i += 1
                continue

            if name == "pre":
                out.append(f'<pre class="book-pre">{self._inline(el, source_path)}</pre>')
                i += 1
                continue

            if name == "math":
                out.append(str(el))
                i += 1
                continue

            if name == "blockquote":
                el.attrs.pop("class", None)
                el["class"] = "book-quote"
                out.append(self._clean_tree(el, source_path))
                i += 1
                continue

            if name == "table":
                el["class"] = ["book-table"]
                out.append(f'<div class="table-wrap">{self._clean_tree(el, source_path)}</div>')
                i += 1
                continue

            if name == "figure":
                fig_index[0] += 1
                imgs = el.find_all("img")
                caps = el.find_all("figcaption")
                if not caps:
                    caps = [
                        candidate
                        for candidate in el.find_all(["p", "span"])
                        if "caption" in class_names(candidate)
                    ]
                if not caps:
                    caps = [
                        candidate
                        for candidate in el.find_all("p")
                        if candidate.get_text(strip=True) and not candidate.find("img")
                    ]
                out.append(self._anchors(el) + self._figure(imgs, caps, source_path, fig_index[0]))
                i += 1
                continue

            # Paragraph-like blocks.
            if "quote" in cls or "epigraph" in cls:
                items = []
                j = i
                while j < len(blocks) and (
                    "quote" in class_names(blocks[j]) or "epigraph" in class_names(blocks[j])
                ):
                    items.append(f"<p>{self._inline(blocks[j], source_path).strip()}</p>")
                    j += 1
                out.append(
                    '<blockquote class="book-quote quote-epigraph">'
                    + "".join(items)
                    + "</blockquote>"
                )
                i = j
                continue

            if "list" in cls or "bullet" in cls:
                items = []
                j = i
                start = 1
                while j < len(blocks) and (
                    "list" in class_names(blocks[j]) or "bullet" in class_names(blocks[j])
                ):
                    item = blocks[j]
                    m = strip_leading(item, r"^\s*(?:[•·]|\d+\.)\s*")
                    if m and m.group(0).strip().endswith("."):
                        match = re.match(r"\d+", m.group(0))
                        if match:
                            start = int(match.group(0))
                    items.append(f"<li>{self._inline(item, source_path).strip()}</li>")
                    j += 1
                tag = "ol" if start != 1 else "ul"
                attr = f' start="{start}"' if tag == "ol" and start != 1 else ""
                out.append(f'<{tag} class="book-list"{attr}>' + "".join(items) + f"</{tag}>")
                i = j
                continue

            if "subhead" in cls or "section" in cls or "heading" in cls or "chap-sub" in cls:
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
                out.append(
                    f'<{tag} class="{c}" id="{html.escape(hid)}">{self._inline(el, source_path).strip()}</{tag}>'
                )
                if page["type"] == "chapter" and level in (2, 3):
                    sections.append({"level": level, "id": hid, "title": heading_text(el)})
                i += 1
                continue

            if not el.get_text(strip=True) and not el.find("img"):
                anchors = "".join(str(a) for a in el.find_all(id=True))
                if anchors:
                    out.append(anchors)
                i += 1
                continue

            pcls = (
                ' class="lede"'
                if page["type"] == "chapter" and first_para and "right" not in cls
                else ""
            )
            if pcls:
                first_para = False
            pid = f' id="{html.escape(el["id"])}"' if el.get("id") else ""
            out.append(f"<p{pid}{pcls}>{self._inline(el, source_path).strip()}</p>")
            i += 1

        return dedupe_fragment_ids("".join(out)), sections

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
                toc.append(
                    {
                        "kind": "chapter",
                        "number": page["number_short"] or str(chapters),
                        "label": page["title"],
                        "href": page["route"],
                        "generated": False,
                    }
                )
            elif page["type"] == "part":
                toc.append(
                    {
                        "kind": "part",
                        "label": page["display_title"],
                        "href": page["route"],
                        "generated": False,
                    }
                )
            else:
                toc.append(
                    {
                        "kind": "entry",
                        "label": page["display_title"],
                        "href": page["route"],
                        "generated": False,
                    }
                )
            for section in page["sections"]:
                toc.append(
                    {
                        "kind": "section",
                        "label": section["title"],
                        "href": f"{page['route']}#{section['id']}",
                        "generated": False,
                    }
                )
        self.toc = toc
        self.chapter_count = chapters

    def _write_book(self, source_text: dict[str, str]) -> None:
        md = self.book.metadata
        title = md.get("title") or self.epub_path.stem
        short, subtitle = split_title(title)
        year = year_from_date(md.get("date") or "")
        cover = self.cover_info["name"] if self.cover_info else ""
        cover_webp = self.cover_info.get("webp", "") if self.cover_info else ""

        pages = []
        for page in self.pages:
            pages.append(
                {
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
                    "images": page.get("images", 0),
                }
            )

        stats = {
            "words": sum(p["words"] for p in pages),
            "chapter_words": sum(p["words"] for p in pages if p["type"] == "chapter"),
            "chapters": self.chapter_count,
            "figures": sum(p.get("figure_count", 0) for p in pages),
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
