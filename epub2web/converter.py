"""Convert a planned reading page into a semantic HTML fragment."""

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass, field
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


@dataclass
class ConversionState:
    """Mutable state shared by the block handlers for one page."""

    page: PagePlan
    blocks: list[tuple[Tag, str]]
    out: list[str] = field(default_factory=list)
    sections: list[PageSection] = field(default_factory=list)
    source_ids: set[str] = field(default_factory=set)
    used_ids: set[str] = field(default_factory=set)
    figure_index: int = 0
    first_para: bool = True
    index_anchors: dict[str, str] = field(default_factory=dict)


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
        state = ConversionState(page=page, blocks=blocks)
        for block, _ in blocks:
            for tag in [block, *block.find_all(id=True)]:
                if tag.get("id"):
                    state.source_ids.add(tag["id"])

        index = self._append_page_header(state)
        while index < len(state.blocks):
            index = self._convert_block(state, index)
        self._insert_index_navigation(state)
        return dedupe_fragment_ids("".join(state.out)), state.sections

    # -- page header ------------------------------------------------------
    def _append_page_header(self, state: ConversionState) -> int:
        if not state.blocks:
            state.out.append(self._fallback_header(state.page))
            return 0

        first, first_path = state.blocks[0]
        first_cls = class_names(first)
        if not (
            first.name in ("h1", "h2", "h3")
            or "chaptertitle" in first_cls
            or "fmtitleq" in first_cls
        ):
            state.out.append(self._fallback_header(state.page))
            return 0

        consumed = [(first, first_path)]
        index = 1
        # "CHAPTER ONE" + title as two adjacent paragraphs/headings.
        if (
            first.name == "p"
            and "chaptertitle" in first_cls
            and index < len(state.blocks)
            and (
                state.blocks[index][0].name in ("h1", "h2", "h3")
                or "chaptertitle" in class_names(state.blocks[index][0])
            )
        ):
            consumed.append(state.blocks[index])
            index += 1
        state.out.append(self._header_for(state, consumed))
        return index

    @staticmethod
    def _fallback_header(page: PagePlan) -> str:
        return (
            f'<header class="chapter-header" data-chrome>'
            f'<h1 class="chapter-title">{html.escape(page.title)}</h1>'
            f'<p class="chapter-meta" data-chrome dir="auto"><!--READTIME--></p></header>'
        )

    def _header_for(self, state: ConversionState, elements: list[tuple[Tag, str]]) -> str:
        text = " ".join(heading_text(e) for e, _ in elements).strip()
        anchors_parts: list[str] = []
        anchor_tags: list[Tag] = []
        has_content_link = False
        for element, _ in elements:
            for tag in element.find_all(id=True):
                if tag.get_text(strip=True):
                    # A real link in the heading (usually a footnote marker)
                    # must stay in the title and keep its id.
                    has_content_link = True
                elif tag.name in ("a", "span") and not tag.find(True):
                    # Empty anchors mark a chapter location. Move them outside
                    # the generated heading so their ids survive.
                    anchor_tags.append(tag)
                    anchors_parts.append(f'<span id="{html.escape(tag["id"])}"></span>')
        anchors = "".join(anchors_parts)
        for tag in anchor_tags:
            tag.attrs.pop("id", None)

        inner_html = " ".join(self._inline(e, path).strip() for e, path in elements)
        _, number_label, title = parse_label(text)
        plain_title = any("fmtitleq" in class_names(e) for e, _ in elements)
        # Keep the source wording exactly; the split is only layout. If the
        # heading contains a footnote/link marker, keep the whole heading as
        # the title so the marker is not duplicated or lost. Contents links
        # around section titles are navigation, not prose, so use the plain
        # heading text for those title paragraphs.
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

        heading_id = next((e["id"] for e, _ in elements if e.get("id")), "")
        if not heading_id:
            heading_id = f"ch-{slugify(state.page.title)}"
        state.used_ids.add(heading_id)
        number = f'<p class="chapter-number">{number_html}</p>' if number_html else ""
        return (
            f'<header class="chapter-header" id="{html.escape(heading_id)}">'
            f'{anchors}{number}<h1 class="chapter-title">{title_html}</h1>'
            f'<p class="chapter-meta" data-chrome dir="auto"><!--READTIME--></p></header>'
        )

    # -- block dispatch ---------------------------------------------------
    def _convert_block(self, state: ConversionState, index: int) -> int:
        el, source_path = state.blocks[index]
        name = el.name
        cls = class_names(el)

        if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            return self._convert_heading(state, index, el, source_path)
        if name in ("img", "picture"):
            return self._convert_image_element(state, index, el, source_path)
        if "image" in cls or (name == "p" and el.find("img")):
            return self._convert_image_paragraph(state, index, el, source_path, cls)
        if "caption" in cls:
            state.out.append(
                f'<p class="orphan-caption">{self._inline(el, source_path).strip()}</p>'
            )
            return index + 1
        if name in ("ul", "ol"):
            return self._convert_list(state, index, el, source_path)
        if name == "dl":
            return self._convert_definition_list(state, index, el, source_path)
        if name == "pre":
            state.out.append(f'<pre class="book-pre">{self._inline(el, source_path)}</pre>')
            return index + 1
        if name == "math":
            state.out.append(str(el))
            return index + 1
        if name == "blockquote":
            return self._convert_blockquote(state, index, el, source_path)
        if name == "table":
            return self._convert_table(state, index, el, source_path)
        if name == "figure":
            return self._convert_figure(state, index, el, source_path)
        if "quote" in cls or "epigraph" in cls:
            return self._convert_quote_group(state, index, source_path)
        if "list" in cls or "bullet" in cls:
            return self._convert_bullet_group(state, index, source_path)
        if "subhead" in cls or "section" in cls or "heading" in cls or "chap-sub" in cls:
            return self._convert_subhead(state, index, el, source_path, cls)
        if not el.get_text(strip=True) and not el.find("img"):
            return self._convert_empty_block(state, index, el)
        return self._convert_paragraph(state, index, el, source_path, cls)

    def _convert_heading(
        self,
        state: ConversionState,
        index: int,
        el: Tag,
        source_path: str,
    ) -> int:
        name = el.name
        level = {"h1": 2, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}[name]
        level = min(level, 4)
        tag = {2: "h2", 3: "h3", 4: "h4"}[level]
        heading_id = self._add_id(state, el)
        cls = {2: "section-title", 3: "subsection-title", 4: "subsubsection-title"}[level]
        state.out.append(
            f'<{tag} class="{cls}" id="{html.escape(heading_id)}">'
            f"{self._inline(el, source_path).strip()}</{tag}>"
        )
        if state.page.type == "chapter" and level in (2, 3):
            state.sections.append({"level": level, "id": heading_id, "title": heading_text(el)})
        return index + 1

    def _convert_image_element(
        self,
        state: ConversionState,
        index: int,
        el: Tag,
        source_path: str,
    ) -> int:
        imgs = [el] if el.name == "img" else el.find_all("img")
        j = index + 1
        while (
            j < len(state.blocks)
            and state.blocks[j][0].name == "img"
            and state.blocks[j][1] == source_path
        ):
            imgs.append(state.blocks[j][0])
            j += 1
        caps = []
        while (
            j < len(state.blocks)
            and state.blocks[j][1] == source_path
            and "caption" in class_names(state.blocks[j][0])
        ):
            caps.append(state.blocks[j][0])
            j += 1
        state.figure_index += 1
        figure = self._figure(imgs, caps, source_path, state.figure_index)
        if figure:
            state.out.append(figure)
        return j

    def _convert_image_paragraph(
        self,
        state: ConversionState,
        index: int,
        el: Tag,
        source_path: str,
        cls: str,
    ) -> int:
        if el.name == "p" and el.get_text(strip=True):
            paragraph_cls = self._paragraph_classes(state, el, cls)
            paragraph_id = f' id="{html.escape(el["id"])}"' if el.get("id") else ""
            state.out.append(
                f"{self._index_anchor(state, el, cls)}<p{paragraph_id}{paragraph_cls}>"
                f"{self._inline(el, source_path).strip()}</p>"
            )
            return index + 1

        imgs = el.find_all("img")
        anchors = self._anchors(el)
        j = index + 1
        while j < len(state.blocks):
            next_el, next_path = state.blocks[j]
            next_cls = class_names(next_el)
            image_only = (
                next_el.name == "p" and next_el.find("img") and not next_el.get_text(strip=True)
            )
            if next_path != source_path or not (
                ("image" in next_cls and not next_el.get_text(strip=True)) or image_only
            ):
                break
            imgs.extend(next_el.find_all("img"))
            anchors += self._anchors(next_el)
            j += 1
        caps = []
        while (
            j < len(state.blocks)
            and state.blocks[j][1] == source_path
            and (
                "caption" in class_names(state.blocks[j][0])
                or state.blocks[j][0].name == "figcaption"
            )
        ):
            caps.append(state.blocks[j][0])
            j += 1
        state.figure_index += 1
        figure = self._figure(imgs, caps, source_path, state.figure_index)
        if figure:
            state.out.append(anchors + figure)
        return j

    def _convert_list(
        self,
        state: ConversionState,
        index: int,
        el: Tag,
        source_path: str,
    ) -> int:
        el.attrs.pop("class", None)
        el["class"] = "book-list"
        state.out.append(self._clean_tree(el, source_path))
        return index + 1

    def _convert_definition_list(
        self,
        state: ConversionState,
        index: int,
        el: Tag,
        source_path: str,
    ) -> int:
        el.attrs.pop("class", None)
        el["class"] = "book-dl"
        state.out.append(self._clean_tree(el, source_path))
        return index + 1

    def _convert_blockquote(
        self,
        state: ConversionState,
        index: int,
        el: Tag,
        source_path: str,
    ) -> int:
        el.attrs.pop("class", None)
        el["class"] = "book-quote"
        state.out.append(self._clean_tree(el, source_path))
        return index + 1

    def _convert_table(
        self,
        state: ConversionState,
        index: int,
        el: Tag,
        source_path: str,
    ) -> int:
        el["class"] = ["book-table"]
        state.out.append(f'<div class="table-wrap">{self._clean_tree(el, source_path)}</div>')
        return index + 1

    def _convert_figure(
        self,
        state: ConversionState,
        index: int,
        el: Tag,
        source_path: str,
    ) -> int:
        state.figure_index += 1
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
        figure = self._figure(imgs, caps, source_path, state.figure_index)
        state.out.append(self._anchors(el) + figure)
        return index + 1

    def _convert_quote_group(
        self,
        state: ConversionState,
        index: int,
        source_path: str,
    ) -> int:
        items = []
        j = index
        while (
            j < len(state.blocks)
            and state.blocks[j][1] == source_path
            and (
                "quote" in class_names(state.blocks[j][0])
                or "epigraph" in class_names(state.blocks[j][0])
            )
        ):
            items.append(f"<p>{self._inline(state.blocks[j][0], source_path).strip()}</p>")
            j += 1
        state.out.append(
            '<blockquote class="book-quote quote-epigraph">' + "".join(items) + "</blockquote>"
        )
        return j

    def _convert_bullet_group(
        self,
        state: ConversionState,
        index: int,
        source_path: str,
    ) -> int:
        items = []
        j = index
        start = 1
        while (
            j < len(state.blocks)
            and state.blocks[j][1] == source_path
            and (
                "list" in class_names(state.blocks[j][0])
                or "bullet" in class_names(state.blocks[j][0])
            )
        ):
            item = state.blocks[j][0]
            match = strip_leading(item, r"^\s*(?:[•·]|\d+\.)\s*")
            if match and match.group(0).strip().endswith("."):
                number = re.match(r"\d+", match.group(0))
                if number:
                    start = int(number.group(0))
            items.append(f"<li>{self._inline(item, source_path).strip()}</li>")
            j += 1
        tag = "ol" if start != 1 else "ul"
        attr = f' start="{start}"' if tag == "ol" and start != 1 else ""
        state.out.append(f'<{tag} class="book-list"{attr}>' + "".join(items) + f"</{tag}>")
        return j

    def _convert_subhead(
        self,
        state: ConversionState,
        index: int,
        el: Tag,
        source_path: str,
        cls: str,
    ) -> int:
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
        heading_id = self._add_id(state, el)
        css_class = "subsection-title" if level == 3 else "section-title"
        state.out.append(
            f'<{tag} class="{css_class}" id="{html.escape(heading_id)}">'
            f"{self._inline(el, source_path).strip()}</{tag}>"
        )
        if state.page.type == "chapter" and level in (2, 3):
            state.sections.append({"level": level, "id": heading_id, "title": heading_text(el)})
        return index + 1

    @staticmethod
    def _convert_empty_block(state: ConversionState, index: int, el: Tag) -> int:
        anchors = "".join(str(a) for a in el.find_all(id=True))
        if anchors:
            state.out.append(anchors)
        return index + 1

    def _convert_paragraph(
        self,
        state: ConversionState,
        index: int,
        el: Tag,
        source_path: str,
        cls: str,
    ) -> int:
        paragraph_cls = self._paragraph_classes(state, el, cls)
        paragraph_id = f' id="{html.escape(el["id"])}"' if el.get("id") else ""
        state.out.append(
            f"{self._index_anchor(state, el, cls)}<p{paragraph_id}{paragraph_cls}>"
            f"{self._inline(el, source_path).strip()}</p>"
        )
        return index + 1

    # -- generated anchors ------------------------------------------------
    @staticmethod
    def _add_id(state: ConversionState, el: Tag) -> str:
        text = heading_text(el)
        if el.get("id"):
            heading_id = el["id"]
        else:
            heading_id = f"s-{slugify(text)}"
            base = heading_id
            n = 2
            while heading_id in state.source_ids or heading_id in state.used_ids:
                heading_id = f"{base}-{n}"
                n += 1
        state.used_ids.add(heading_id)
        return heading_id

    @staticmethod
    def _paragraph_classes(state: ConversionState, el: Tag, cls: str) -> str:
        classes: list[str] = []
        if state.page.type == "chapter" and state.first_para and "right" not in cls:
            classes.append("lede")
            state.first_para = False
        if el.find("img", attrs={"data-dropcap": "true"}):
            classes.append("has-dropcap-image")
        if "indexsub" in cls:
            classes.append("index-subentry")
        elif "index" in cls:
            classes.append("index-entry")
        if "hangs" in cls:
            classes.append("hanging")
        return f' class="{" ".join(classes)}"' if classes else ""

    @staticmethod
    def _index_anchor(state: ConversionState, el: Tag, cls: str) -> str:
        if "index" not in cls or "indexsub" in cls:
            return ""
        text = heading_text(el)
        if not index_main_entry(text):
            return ""
        letter = index_letter(text)
        if not letter or letter in state.index_anchors:
            return ""
        anchor_id = f"index-{letter.lower()}"
        state.index_anchors[letter] = anchor_id
        return f'<span id="{anchor_id}" class="index-anchor"></span>'

    @staticmethod
    def _insert_index_navigation(state: ConversionState) -> None:
        if not state.index_anchors:
            return
        nav_links = []
        for letter in INDEX_LETTERS:
            anchor_id = state.index_anchors.get(letter)
            if anchor_id:
                nav_links.append(f'<a href="#{anchor_id}">{letter}</a>')
            else:
                nav_links.append(
                    f'<span class="index-nav-empty" aria-hidden="true">{letter}</span>'
                )
        state.out.insert(
            1,
            '<nav class="index-nav" aria-label="Index letters" data-chrome>'
            '<span class="index-nav-title">A\u2013Z</span>' + "".join(nav_links) + "</nav>",
        )

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
