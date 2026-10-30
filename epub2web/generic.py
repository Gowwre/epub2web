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
import copy
import hashlib
import html
import io
import json
import logging
import re
import unicodedata
import warnings
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup, NavigableString, Tag, XMLParsedAsHTMLWarning
from PIL import Image, ImageOps

from .epub import Epub, TocEntry
from .navigation import SiteTocBuilder
from .progress import ProgressCallback, report
from .text import (
    inner,
    match_key,
    normalize_text,
    reading_units,
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
PAGE_BLOCK_TAGS = {
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
}

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


def _file_sha256(path: Path) -> str:
    """Return a deterministic identity for the EPUB file itself."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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

    for span in body.find_all("span"):
        if "dropcap" in class_names(span):
            for img in span.find_all("img"):
                img["data-dropcap"] = "true"

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


INDEX_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
INDEX_LEADING_PUNCT_RE = re.compile(r"^[^0-9A-Za-z]+")
INDEX_ARTICLE_RE = re.compile(r"^(?:a|an|the)\s+", re.IGNORECASE)


def index_letter(text: str) -> str:
    """Return the filing letter for an index entry, ignoring articles."""
    value = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    value = INDEX_LEADING_PUNCT_RE.sub("", value)
    if not value or not value[0].isalpha():
        return ""
    value = INDEX_ARTICLE_RE.sub("", value)
    value = INDEX_LEADING_PUNCT_RE.sub("", value)
    if not value or not value[0].isalpha():
        return ""
    return value[0].upper()


def index_main_entry(text: str) -> bool:
    """Reject lowercase subentries that print conversions mislabel as index entries."""
    value = text.strip()
    if not value:
        return False
    if value[0] in "\"'\u2018\u2019\u201c\u201d\u00ab\u00bb":
        return True
    stripped = INDEX_LEADING_PUNCT_RE.sub("", value)
    if not stripped or stripped[0].isdigit() or stripped[0].isupper():
        return True
    first_word = re.split(r"\s+", stripped, maxsplit=1)[0]
    return any(char.isupper() for char in first_word[1:])


def class_names(el: Tag) -> str:
    return " ".join(el.get("class", [])).lower()


def heading_text(el: Tag) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()


def direct_page_blocks(body: Tag) -> list[Tag]:
    """Return the block-level children the page converter can render."""
    return [
        child for child in body.children if isinstance(child, Tag) and child.name in PAGE_BLOCK_TAGS
    ]


def first_heading_in_blocks(blocks: list[Tag]) -> Tag | None:
    """Find the first heading-like element in an already split page."""
    for block in blocks:
        if block.name == "p" and "chaptertitle" in class_names(block):
            return block
    for name in ("h1", "h2", "h3", "h4"):
        for block in blocks:
            if block.name == name and block.get_text(strip=True):
                return block
            for element in block.find_all(name):
                if element.get_text(strip=True):
                    return element
    for block in blocks:
        if block.name != "p":
            continue
        cls = class_names(block)
        if (
            any(key in cls for key in ("title", "heading", "subhead"))
            and len(block.get_text(" ", strip=True)) < 140
        ):
            return block
    return None


def has_visible_content(block: Tag) -> bool:
    """Whether a block still contains text or a rendered object."""
    if block.get_text(" ", strip=True):
        return True
    if block.name in ("img", "picture", "table", "figure", "math"):
        return True
    return block.find(["img", "picture", "table", "figure", "math"]) is not None


def element_index_path(root: Tag, node: Tag) -> list[int]:
    """Return child indexes from *root* down to *node*, or ``[]``."""
    path: list[int] = []
    current: Tag | None = node
    while current is not root:
        parent = current.parent if current is not None else None
        if parent is None:
            return []
        path.append(list(parent.children).index(current))
        current = parent
    path.reverse()
    return path


def node_at_path(root: Tag, path: list[int]) -> Tag | None:
    current = root
    for index in path:
        children = list(current.children)
        if index >= len(children):
            return None
        child = children[index]
        if not isinstance(child, Tag):
            return None
        current = child
    return current


def split_block_at(block: Tag, anchor: Tag) -> tuple[Tag, Tag] | None:
    """Split a top-level block into content before and after an anchor."""
    path = element_index_path(block, anchor)
    if not path:
        return None
    before = copy.deepcopy(block)
    after = copy.deepcopy(block)
    before_anchor = node_at_path(before, path)
    after_anchor = node_at_path(after, path)
    if before_anchor is None or after_anchor is None:
        return None

    node = before_anchor
    parent = node.parent
    for sibling in list(node.next_siblings):
        sibling.extract()
    node.extract()
    node = parent
    while node is not None and node is not before:
        parent = node.parent
        for sibling in list(node.next_siblings):
            sibling.extract()
        node = parent

    node = after_anchor
    while node is not None and node is not after:
        parent = node.parent
        for sibling in list(node.previous_siblings):
            sibling.extract()
        node = parent

    # Both halves keep the ancestors' attributes. Only the trailing half
    # should keep an id so links do not resolve to the earlier half.
    after_ids = {tag.get("id") for tag in [after, *after.find_all(id=True)] if tag.get("id")}
    for tag in [before, *before.find_all(id=True)]:
        if tag.get("id") in after_ids:
            del tag["id"]
    return before, after


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
        self.route_by_target: dict[tuple[str, str], str] = {}
        self.current_route = ""
        self.nav_labels: dict[str, str] = {}
        self.toc: list[dict] = []
        self.toc_tree: list[dict] = []
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
            self._build_route_maps()

            fragments = {}
            source_text = {}
            total_pages = len(self.pages)
            self._report("extract-pages", "Laying out pages", 0, total_pages)
            for index, page in enumerate(self.pages, 1):
                page["images"] = sum(
                    1
                    for part in page["parts"]
                    for block in part.blocks
                    for img in ([block] if block.name == "img" else block.find_all("img"))
                )
                page_source = page["source_text"]
                source_text[page["id"]] = page_source
                fragment, sections = self._convert_page(page)
                page["sections"] = sections
                page["figure_count"] = fragment.count("<figure")
                page["words"] = len(page_source.split())
                page["characters"] = sum(1 for character in page_source if not character.isspace())
                page["reading_units"] = reading_units(page_source)
                fragments[page["id"]] = fragment
                self._report("extract-pages", "Laying out pages", index, total_pages)

            self.pages = [p for p in self.pages if p["id"] in fragments]
            if not self.pages:
                raise ValueError("no readable pages found in the EPUB spine")
            self.page_by_path = {p["source_files"][0]: p for p in self.pages}
            self._build_route_maps()

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

    def _split_entries(self, path: str) -> list:
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
        item,
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
            logger.warning(
                "TOC split would lose text; keeping one page",
                extra={"path": item.path},
            )
            return None
        return segments

    def _fallback_label(self, item, soup: BeautifulSoup, blocks: list[Tag]) -> str:
        label = self._nav_label(item.path)
        if label:
            return label
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
    ) -> dict:
        display, number_label, title = parse_label(label)
        return {
            "source_files": [path],
            "parts": [PagePart(path, blocks)],
            "label": label,
            "display_title": display,
            "title": title,
            "number_label": number_label,
            "number_short": number_short(number_label),
            "marker": False,
            "marker_kind": "",
            "heading": "",
            "words": 0,
            "type": "chapter",
            "id": "",
            "route": "",
            "toc_entry": toc_entry,
            "toc_fragment": toc_entry.fragment if toc_entry else "",
        }

    @staticmethod
    def _append_part(page: dict, part: PagePart) -> None:
        page["parts"].append(part)
        if part.path not in page["source_files"]:
            page["source_files"].append(part.path)

    def _plan_pages(self) -> list[dict]:
        """Turn spine documents into reading pages at their TOC boundaries.

        Content before the first TOC anchor continues the previous page. That
        keeps chapters that span more than one EPUB file together.
        """
        pages: list[dict] = []
        previous_page = None
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
                        self._append_part(previous_page, PagePart(item.path, segment_blocks))
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
                    self._append_part(previous_page, PagePart(item.path, pending_lead))
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
            page_blocks = [block for part in page["parts"] for block in part.blocks]
            page["source_text"] = normalize_text(" ".join(text_of(block) for block in page_blocks))
            heading = first_heading_in_blocks(page_blocks)
            page["heading"] = heading_text(heading) if heading else ""
            heading_class = class_names(heading) if heading else ""
            page["marker_kind"] = marker_kind(page["label"], page["heading"], heading_class)
            page["marker"] = bool(page["marker_kind"])
            page["words"] = len(page["source_text"].split())

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

    def _build_route_maps(self) -> None:
        """Map source files and anchors to the page that now contains them."""
        self.route_by_path = {}
        self.route_by_target = {}
        self.page_by_path = {}
        for page in self.pages:
            for part in page["parts"]:
                path = part.path
                self.route_by_path.setdefault(path, page["route"])
                self.page_by_path.setdefault(path, page)
                for block in part.blocks:
                    for tag in [block, *block.find_all(id=True)]:
                        anchor_id = tag.get("id")
                        if anchor_id:
                            self.route_by_target.setdefault((path, anchor_id), page["route"])

    # -- conversion -------------------------------------------------------
    def _href(self, doc_path: str, href: str) -> str:
        if not href:
            return href
        if href.startswith(("http:", "https:", "ftp:", "//", "mailto:", "tel:", "data:")):
            return href
        parts = urlsplit(href)
        fragment = unquote(parts.fragment)
        if not parts.path:
            if fragment:
                target_route = self.route_by_target.get((doc_path, fragment), "")
                if target_route and target_route != self.current_route:
                    return target_route + f"#{fragment}"
                return f"#{fragment}"
            return href
        target, _ = self.book._resolve(doc_path, href)
        if fragment and (target, fragment) in self.route_by_target:
            return self.route_by_target[(target, fragment)] + f"#{fragment}"
        if target in self.route_by_path:
            return self.route_by_path[target] + (f"#{fragment}" if fragment else "")
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

    def _image_html(self, img: Tag, doc_path: str, has_caption: bool) -> str:
        src = img.get("src") or ""
        info = image_info(self.book, self.images, doc_path, src)
        if not info:
            return ""
        alt = img.get("alt") or ""
        if has_caption:
            alt = ""
        name = html.escape(info["name"])
        w = info["width"]
        h = info["height"]
        attrs = f'width="{w}" height="{h}"' if w and h else ""
        img_tag = f'<img src="/images/{name}" {attrs} alt="{html.escape(alt)}" loading="lazy" decoding="async">'
        if info.get("webp"):
            picture = f'<picture><source srcset="/images/{html.escape(info["webp"])}" type="image/webp">{img_tag}</picture>'
        else:
            picture = img_tag
        return f'<a class="lightbox-link" href="/images/{name}" aria-label="View figure larger">{picture}</a>'

    @staticmethod
    def _take_caption_ids(caps: list[Tag]) -> list[str]:
        """Move caption anchors to the figure so references reveal the image."""
        ids: list[str] = []
        for cap in caps:
            nodes = [cap, *cap.find_all(id=True)]
            for node in nodes:
                node_id = node.get("id")
                if not node_id or node_id in ids:
                    continue
                ids.append(node_id)
                del node["id"]
        return ids

    def _figure(self, imgs: list[Tag], caps: list[Tag], doc_path: str, index: int) -> str:
        caption_id = f"fig-{index}-caption"
        has_caption = bool(caps)
        body = "".join(self._image_html(img, doc_path, has_caption) for img in imgs)
        if not body:
            return ""
        anchor_ids = self._take_caption_ids(caps)
        caption_html = "".join(f"<p>{self._inline(c, doc_path).strip()}</p>" for c in caps)
        has_caption = bool(caption_html)
        cls = "figure figure-multi" if len(imgs) > 1 else "figure"
        figcap = f'<figcaption id="{caption_id}">{caption_html}</figcaption>' if has_caption else ""
        anchors = "".join(f'<span id="{html.escape(node_id)}"></span>' for node_id in anchor_ids)
        return f'{anchors}<figure class="{cls}" data-count="{len(imgs)}">{body}{figcap}</figure>'

    def _convert_page(self, page: dict) -> tuple[str, list[dict]]:
        self.current_route = page["route"]
        blocks = [(block, part.path) for part in page["parts"] for block in part.blocks]
        # divs have been flattened in clean_doc; this is defensive.
        out: list[str] = []
        sections: list[dict] = []
        source_ids: set[str] = set()
        for block, _ in blocks:
            for tag in [block, *block.find_all(id=True)]:
                if tag.get("id"):
                    source_ids.add(tag["id"])
        used_ids: set[str] = set()
        fig_index = [0]
        first_para = True
        index_anchors: dict[str, str] = {}

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

        def paragraph_classes(el: Tag, cls: str) -> str:
            nonlocal first_para
            classes: list[str] = []
            if page["type"] == "chapter" and first_para and "right" not in cls:
                classes.append("lede")
                first_para = False
            if el.find("img", attrs={"data-dropcap": "true"}):
                classes.append("has-dropcap-image")
            if "indexsub" in cls:
                classes.append("index-subentry")
            elif "index" in cls:
                classes.append("index-entry")
            if "hangs" in cls:
                classes.append("hanging")
            return f' class="{" ".join(classes)}"' if classes else ""

        def index_anchor(el: Tag, cls: str) -> str:
            if "index" not in cls or "indexsub" in cls:
                return ""
            text = heading_text(el)
            if not index_main_entry(text):
                return ""
            letter = index_letter(text)
            if not letter or letter in index_anchors:
                return ""
            anchor_id = f"index-{letter.lower()}"
            index_anchors[letter] = anchor_id
            return f'<span id="{anchor_id}" class="index-anchor"></span>'

        def header_for(elements: list[tuple[Tag, str]]) -> str:
            text = " ".join(heading_text(e) for e, _ in elements).strip()
            anchors_parts: list[str] = []
            anchor_tags: list[Tag] = []
            has_content_link = False
            for e, _ in elements:
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
            inner_html = " ".join(self._inline(e, path).strip() for e, path in elements)
            _, number_label, title = parse_label(text)
            plain_title = any("fmtitleq" in class_names(e) for e, _ in elements)
            # Keep the source wording exactly; the split is only layout. If
            # the heading contains a footnote/link marker, keep the whole
            # heading as the title so the marker is not duplicated or lost.
            # Contents links around section titles are navigation, not prose,
            # so use the plain heading text for those title paragraphs.
            if plain_title and not has_content_link:
                number_html = ""
                title_html = html.escape(title)
            elif has_content_link:
                number_html = ""
                title_html = inner_html or html.escape(text)
            elif number_label and title and title != number_label:
                number_html = html.escape(number_label)
                title_html = html.escape(title)
            else:
                number_html = ""
                title_html = inner_html or html.escape(text)
            hid = next((e["id"] for e, _ in elements if e.get("id")), "")
            if not hid:
                hid = f"ch-{slugify(page['title'])}"
            used_ids.add(hid)
            num = f'<p class="chapter-number">{number_html}</p>' if number_html else ""
            return (
                f'<header class="chapter-header" id="{html.escape(hid)}">'
                f'{anchors}{num}<h1 class="chapter-title">{title_html}</h1>'
                f'<p class="chapter-meta" data-chrome dir="auto"><!--READTIME--></p></header>'
            )

        i = 0
        # The first heading becomes the page header, preserving its text.
        if blocks:
            first, first_path = blocks[0]
            first_cls = class_names(first)
            if (
                first.name in ("h1", "h2", "h3")
                or "chaptertitle" in first_cls
                or "fmtitleq" in first_cls
            ):
                consumed = [(first, first_path)]
                i = 1
                # "CHAPTER ONE" + title as two adjacent paragraphs/headings.
                if (
                    first.name == "p"
                    and "chaptertitle" in first_cls
                    and i < len(blocks)
                    and (
                        blocks[i][0].name in ("h1", "h2", "h3")
                        or "chaptertitle" in class_names(blocks[i][0])
                    )
                ):
                    consumed.append(blocks[i])
                    i += 1
                out.append(header_for(consumed))
            else:
                out.append(
                    f'<header class="chapter-header" data-chrome>'
                    f'<h1 class="chapter-title">{html.escape(page["title"])}</h1>'
                    f'<p class="chapter-meta" data-chrome dir="auto"><!--READTIME--></p></header>'
                )
        else:
            out.append(
                f'<header class="chapter-header" data-chrome>'
                f'<h1 class="chapter-title">{html.escape(page["title"])}</h1>'
                f'<p class="chapter-meta" data-chrome dir="auto"><!--READTIME--></p></header>'
            )

        while i < len(blocks):
            el, source_path = blocks[i]
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
                while (
                    j < len(blocks) and blocks[j][0].name == "img" and blocks[j][1] == source_path
                ):
                    imgs.append(blocks[j][0])
                    j += 1
                caps = []
                while (
                    j < len(blocks)
                    and blocks[j][1] == source_path
                    and "caption" in class_names(blocks[j][0])
                ):
                    caps.append(blocks[j][0])
                    j += 1
                fig_index[0] += 1
                fig = self._figure(imgs, caps, source_path, fig_index[0])
                if fig:
                    out.append(fig)
                i = j
                continue

            if "image" in cls or (name == "p" and el.find("img")):
                if name == "p" and el.get_text(strip=True):
                    pcls = paragraph_classes(el, cls)
                    pid = f' id="{html.escape(el["id"])}"' if el.get("id") else ""
                    out.append(
                        f"{index_anchor(el, cls)}<p{pid}{pcls}>{self._inline(el, source_path).strip()}</p>"
                    )
                    i += 1
                    continue
                imgs = el.find_all("img")
                anchors = self._anchors(el)
                j = i + 1
                while j < len(blocks):
                    nxt, nxt_path = blocks[j]
                    nxt_cls = class_names(nxt)
                    image_only = (
                        nxt.name == "p" and nxt.find("img") and not nxt.get_text(strip=True)
                    )
                    if nxt_path != source_path or not (
                        ("image" in nxt_cls and not nxt.get_text(strip=True)) or image_only
                    ):
                        break
                    imgs.extend(nxt.find_all("img"))
                    anchors += self._anchors(nxt)
                    j += 1
                caps = []
                while (
                    j < len(blocks)
                    and blocks[j][1] == source_path
                    and (
                        "caption" in class_names(blocks[j][0]) or blocks[j][0].name == "figcaption"
                    )
                ):
                    caps.append(blocks[j][0])
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
                fig = self._figure(imgs, caps, source_path, fig_index[0])
                out.append(self._anchors(el) + fig)
                i += 1
                continue

            # Paragraph-like blocks.
            if "quote" in cls or "epigraph" in cls:
                items = []
                j = i
                while (
                    j < len(blocks)
                    and blocks[j][1] == source_path
                    and (
                        "quote" in class_names(blocks[j][0])
                        or "epigraph" in class_names(blocks[j][0])
                    )
                ):
                    items.append(f"<p>{self._inline(blocks[j][0], source_path).strip()}</p>")
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
                while (
                    j < len(blocks)
                    and blocks[j][1] == source_path
                    and (
                        "list" in class_names(blocks[j][0]) or "bullet" in class_names(blocks[j][0])
                    )
                ):
                    item = blocks[j][0]
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

            pcls = paragraph_classes(el, cls)
            pid = f' id="{html.escape(el["id"])}"' if el.get("id") else ""
            out.append(
                f"{index_anchor(el, cls)}<p{pid}{pcls}>{self._inline(el, source_path).strip()}</p>"
            )
            i += 1

        if index_anchors:
            nav_links = []
            for letter in INDEX_LETTERS:
                anchor_id = index_anchors.get(letter)
                if anchor_id:
                    nav_links.append(f'<a href="#{anchor_id}">{letter}</a>')
                else:
                    nav_links.append(
                        f'<span class="index-nav-empty" aria-hidden="true">{letter}</span>'
                    )
            out.insert(
                1,
                '<nav class="index-nav" aria-label="Index letters" data-chrome>'
                '<span class="index-nav-title">A\u2013Z</span>' + "".join(nav_links) + "</nav>",
            )

        return dedupe_fragment_ids("".join(out)), sections

    # -- output -----------------------------------------------------------
    def _write_pages(self, fragments: dict[str, str]) -> None:
        for pid, fragment in fragments.items():
            (self.pages_dir / f"{pid}.html").write_text(fragment, encoding="utf-8")

    def _write_toc(self) -> None:
        site_toc = SiteTocBuilder(
            toc_entries=self.book.toc,
            pages=self.pages,
            route_by_path=self.route_by_path,
            route_by_target=self.route_by_target,
        ).build()
        self.toc_tree = [item.as_dict() for item in site_toc.tree]
        self.toc = site_toc.flat
        self.chapter_count = site_toc.chapter_count
        for page in self.pages:
            page["in_toc"] = page["id"] in site_toc.page_ids

    def _write_book(self, source_text: dict[str, str]) -> None:
        md = self.book.metadata
        title = md.get("title") or self.epub_path.stem
        short, subtitle = split_title(title)
        year = year_from_date(md.get("date") or "")
        cover = self.cover_info["name"] if self.cover_info else ""
        cover_webp = self.cover_info.get("webp", "") if self.cover_info else ""
        try:
            reading_id = _file_sha256(self.epub_path)
        except OSError:
            reading_id = ""

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
                    "in_toc": page.get("in_toc", True),
                    "words": page["words"],
                    "characters": page.get("characters", 0),
                    "reading_units": page.get("reading_units", page["words"]),
                    "figure_count": page.get("figure_count", 0),
                    "images": page.get("images", 0),
                }
            )

        stats = {
            "words": sum(p["words"] for p in pages),
            "characters": sum(p["characters"] for p in pages),
            "chapter_words": sum(p["words"] for p in pages if p["type"] == "chapter"),
            "chapter_characters": sum(p["characters"] for p in pages if p["type"] == "chapter"),
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
                "reading_id": reading_id,
            },
            "pages": pages,
            "toc": self.toc,
            "toc_tree": self.toc_tree,
            "reading_order": [p["id"] for p in pages],
            "stats": stats,
        }
        (self.content_dir / "book.json").write_text(
            json.dumps(self.book_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (self.content_dir / "source-text.json").write_text(
            json.dumps(source_text, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
