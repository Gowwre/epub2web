"""Sanitize and normalize untrusted EPUB documents before page extraction.

Cleaning is deliberately separate from page planning and rendering. The rules
here decide what active content, layout structure, and navigation artifacts are
safe to carry into the generated site.
"""

from __future__ import annotations

import html
import re

from bs4 import BeautifulSoup, NavigableString, Tag

from .dom import class_names

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


def _move_body_id_to_content(soup: BeautifulSoup, body: Tag) -> None:
    """Move a TOC target on ``<body id>`` onto the first real content block."""
    if not body.get("id"):
        return
    target = body.find(["h1", "h2", "h3", "h4", "h5", "h6", "p", "table", "figure"])
    if target is not None and not target.get("id"):
        target["id"] = body["id"]
    else:
        anchor = soup.new_tag("span")
        anchor["class"] = "anchor"
        anchor["id"] = body["id"]
        body.insert(0, anchor)
    del body["id"]


def _repair_image_sources(body: Tag) -> None:
    """Recover lazy-loaded image sources before attributes are stripped."""
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


def _remove_display_none(body: Tag) -> None:
    for el in body.find_all(style=True):
        if "display:none" in el.get("style", "").replace(" ", "").lower():
            el.decompose()


def _remove_dangerous_tags(body: Tag) -> None:
    for el in body.find_all(DANGEROUS_TAGS):
        el.decompose()


def _strip_unsafe_attributes(body: Tag) -> None:
    for tag in body.find_all(True):
        for attr in list(tag.attrs):
            name = attr.lower()
            if (
                name.startswith(("data-", "on"))
                or name in DANGEROUS_ATTRS
                or (name in ("href", "src") and not safe_url(str(tag.attrs[attr]), tag.name, name))
            ):
                del tag.attrs[attr]


def _remove_hidden_content(body: Tag) -> None:
    for el in body.find_all(attrs={"hidden": True}):
        el.decompose()
    for el in body.find_all(class_=re.compile(r"^(hide|hidden)$", re.I)):
        if el.get_text(strip=True):
            continue
        if el.find(["img", "table"]):
            el.decompose()
        else:
            el.replace_with(" ")


def _remove_print_artifacts(body: Tag) -> None:
    # Print-conversion spacers carry the space between a label and its text.
    for el in body.find_all("span", class_=re.compile(r"^space")):
        el.replace_with(" ")
    for el in body.find_all("hr"):
        el.decompose()


def _flatten_layout_containers(soup: BeautifulSoup, body: Tag) -> None:
    """Unwrap layout wrappers while preserving their navigation ids."""
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


def _normalize_link_artifacts(soup: BeautifulSoup, body: Tag) -> None:
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


def _mark_dropcap_images(body: Tag) -> None:
    for span in body.find_all("span"):
        if "dropcap" in class_names(span):
            for img in span.find_all("img"):
                img["data-dropcap"] = "true"


def _unwrap_anonymous_spans(body: Tag) -> None:
    while True:
        span = body.find("span", id=False)
        if span is None:
            break
        span.unwrap()


INLINE_TAGS = {
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


def _wrap_bare_text_runs(soup: BeautifulSoup, body: Tag) -> None:
    """Wrap prose left directly under body after layout wrappers are removed."""
    run = []
    for child in list(body.children):
        if isinstance(child, NavigableString) or (
            isinstance(child, Tag) and child.name in INLINE_TAGS
        ):
            run.append(child)
        else:
            _flush_text_run(soup, run)
            run = []
    _flush_text_run(soup, run)


def _flush_text_run(soup: BeautifulSoup, run: list) -> None:
    if not run:
        return
    if not any((isinstance(x, Tag) or (isinstance(x, NavigableString) and x.strip())) for x in run):
        return
    paragraph = soup.new_tag("p")
    run[0].insert_before(paragraph)
    for node in run:
        paragraph.append(node.extract())


def _remove_empty_paragraphs(body: Tag) -> None:
    for p in body.find_all("p"):
        if p.get_text(strip=True) or p.find(["img", "table"]) or p.find(id=True):
            continue
        p.decompose()


def _strip_presentation_attributes(body: Tag) -> None:
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


def _dedupe_ids(body: Tag) -> None:
    # Some EPUBs repeat an id (usually a print page anchor). Keep the first
    # target; the id is a navigation artifact, not content.
    seen_ids: set[str] = set()
    for tag in body.find_all(id=True):
        value = tag["id"]
        if value in seen_ids:
            del tag["id"]
        else:
            seen_ids.add(value)


def clean_doc(soup: BeautifulSoup) -> BeautifulSoup:
    """Remove unsafe or invisible markup and normalize layout containers."""
    body = soup.body
    if body is None:
        return soup

    _move_body_id_to_content(soup, body)
    _repair_image_sources(body)
    _remove_display_none(body)
    _remove_dangerous_tags(body)
    _strip_unsafe_attributes(body)
    _remove_hidden_content(body)
    _remove_print_artifacts(body)
    _flatten_layout_containers(soup, body)
    _normalize_link_artifacts(soup, body)
    _mark_dropcap_images(body)
    _unwrap_anonymous_spans(body)
    _wrap_bare_text_runs(soup, body)
    _remove_empty_paragraphs(body)
    _strip_presentation_attributes(body)
    _dedupe_ids(body)
    repair_malformed_external_hrefs(body)
    repair_missing_note_anchors(soup, body)
    return soup
