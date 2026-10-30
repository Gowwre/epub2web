"""Small DOM helpers for splitting and inspecting cleaned source documents."""

from __future__ import annotations

import copy
import re

from bs4 import Tag

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
