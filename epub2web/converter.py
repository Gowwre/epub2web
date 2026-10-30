"""Convert a planned reading page into a semantic HTML fragment."""

from __future__ import annotations

import html
import re
import unicodedata
from urllib.parse import unquote, urlsplit

from bs4 import Tag

from .clean import dedupe_fragment_ids
from .dom import class_names, heading_text
from .epub import Epub
from .labels import parse_label
from .models import PagePlan, PageSection
from .text import inner, slugify, strip_leading

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


class PageConverter:
    """Render one :class:`PagePlan` without writing files or changing routes."""

    def __init__(
        self,
        book: Epub,
        images: dict[str, dict],
        route_by_path: dict[str, str],
        route_by_target: dict[tuple[str, str], str],
    ):
        self.book = book
        self.images = images
        self.route_by_path = route_by_path
        self.route_by_target = route_by_target
        self.current_route = ""

    def convert(self, page: PagePlan) -> tuple[str, list[PageSection]]:
        self.current_route = page.route
        blocks = [(block, part.path) for part in page.parts for block in part.blocks]
        # divs have been flattened in clean_doc; this is defensive.
        out: list[str] = []
        sections: list[PageSection] = []
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
            if page.type == "chapter" and first_para and "right" not in cls:
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
                hid = f"ch-{slugify(page.title)}"
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
                    f'<h1 class="chapter-title">{html.escape(page.title)}</h1>'
                    f'<p class="chapter-meta" data-chrome dir="auto"><!--READTIME--></p></header>'
                )
        else:
            out.append(
                f'<header class="chapter-header" data-chrome>'
                f'<h1 class="chapter-title">{html.escape(page.title)}</h1>'
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
                if page.type == "chapter" and level in (2, 3):
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
                if page.type == "chapter" and level in (2, 3):
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
