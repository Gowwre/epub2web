#!/usr/bin/env python3
"""Text-fidelity gate.

Compares the words in each built page (inside <main>, ignoring generated
chrome) with the words in the corresponding EPUB source files. The comparison
is token-for-token and order-sensitive. Any added, dropped, or moved word
fails the build.
"""

from __future__ import annotations

import difflib
import json
import re
import sys
import unicodedata
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
CONTENT = ROOT / "content"

BLOCK_TAGS = {
    "address", "article", "aside", "blockquote", "caption", "dd", "div", "dl",
    "dt", "fieldset", "figcaption", "figure", "footer", "form", "h1", "h2",
    "h3", "h4", "h5", "h6", "header", "hr", "li", "main", "nav", "ol", "p",
    "pre", "section", "table", "tbody", "td", "tfoot", "th", "thead", "tr", "ul",
}

PAGE_SOURCE_FILES = {
    "front-matter": ["Halftitle.html", "Fm.html", "Title.html", "Copyright.html", "Dedication.html"],
    "contents": ["Contents.html"],
    "preface": ["Preface.html"],
    "chapter-1": ["Chapter001.html"],
    "chapter-2": ["Chapter002.html"],
    "chapter-3": ["Chapter003.html"],
    "chapter-4": ["Chapter004.html"],
    "chapter-5": ["Chapter005.html"],
    "chapter-6": ["Chapter006.html"],
    "chapter-7": ["Chapter007.html"],
    "acknowledgments": ["Acknowledgments.html"],
    "notes": ["Notes.html"],
    "references": ["References.html"],
    "index": ["Index.html"],
}


def extract_text(root: Tag) -> str:
    parts: list[str] = []

    def walk(node):
        if isinstance(node, NavigableString):
            parts.append(str(node))
            return
        if not isinstance(node, Tag):
            return
        if node.name in ("script", "style"):
            return
        if node.has_attr("data-chrome") or node.has_attr("data-generated"):
            return
        if node.name == "br":
            parts.append("\n")
            return
        block = node.name in BLOCK_TAGS
        if block:
            parts.append("\n")
        for child in node.children:
            walk(child)
        if block:
            parts.append("\n")

    walk(root)
    return "".join(parts)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\u00ad", "").replace("\u200b", "").replace("\ufeff", "")
    text = text.replace("\u00a0", " ")
    lines = []
    for line in text.splitlines():
        line = line.strip()
        line = re.sub(r"^[•·]\s*", "", line)
        line = re.sub(r"^\d+\.\s+", "", line)
        if line:
            lines.append(line)
    return re.sub(r"\s+", " ", " ".join(lines)).strip()


def tokens(text: str) -> list[str]:
    return normalize(text).split()


def route_to_file(route: str) -> Path:
    if route == "/":
        return DIST / "index.html"
    return DIST / route.strip("/") / "index.html"


def first_diff(source: list[str], output: list[str]) -> str:
    matcher = difflib.SequenceMatcher(a=source, b=output, autojunk=False)
    lines = []
    shown = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        lines.append(f"    {tag}: source[{i1}:{i2}]={source[i1:i2][:12]}  output[{j1}:{j2}]={output[j1:j2][:12]}")
        shown += 1
        if shown >= 8:
            break
    return "\n".join(lines)


def main() -> int:
    book = json.loads((CONTENT / "book.json").read_text(encoding="utf-8"))
    source_text = json.loads((CONTENT / "source-text.json").read_text(encoding="utf-8"))
    pages = {p["id"]: p for p in book["pages"]}

    failures = 0
    rows = []
    for page_id, files in PAGE_SOURCE_FILES.items():
        page = pages.get(page_id)
        if not page:
            rows.append((page_id, "MISSING PAGE", 0, 0, "FAIL"))
            failures += 1
            continue
        path = route_to_file(page["route"])
        if not path.exists():
            rows.append((page_id, "MISSING FILE", 0, 0, "FAIL"))
            failures += 1
            continue

        source = normalize(" ".join(source_text[name] for name in files))
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "lxml")
        main = soup.find("main")
        output = normalize(extract_text(main)) if main else ""
        src_tokens = source.split()
        out_tokens = output.split()
        token_ok = src_tokens == out_tokens
        char_ok = source == output
        ok = token_ok and char_ok
        status = "ok" if ok else ("MISMATCH" if not token_ok else "CHAR MISMATCH")
        if not ok:
            failures += 1
            if token_ok:
                matcher = difflib.SequenceMatcher(a=source, b=output, autojunk=False)
                char_detail = "    character-level difference: " + repr(matcher.get_opcodes()[:5])
            else:
                char_detail = first_diff(src_tokens, out_tokens)
        else:
            char_detail = ""
        rows.append((page_id, status, len(src_tokens), len(out_tokens), char_detail))

    # --- structural checks -------------------------------------------------
    stats = book["stats"]
    counts = {
        "notes": (stats["notes"], sum(1 for n in book["notes"])),
        "references": (stats["references"], len(book["pages"])),
        "index": (stats["index_entries"], 0),
    }
    index_page = (DIST / "index-of-terms" / "index.html")
    if index_page.exists():
        index_soup = BeautifulSoup(index_page.read_text(encoding="utf-8"), "lxml")
        counts["index"] = (stats["index_entries"], len(index_soup.select("[data-index-text]")))
    notes_page = DIST / "notes" / "index.html"
    if notes_page.exists():
        notes_soup = BeautifulSoup(notes_page.read_text(encoding="utf-8"), "lxml")
        counts["notes"] = (stats["notes"], len(notes_soup.select("article.note")))
    refs_page = DIST / "references" / "index.html"
    if refs_page.exists():
        refs_soup = BeautifulSoup(refs_page.read_text(encoding="utf-8"), "lxml")
        counts["references"] = (stats["references"], len(refs_soup.select(".reference-list > li")))

    print("Text fidelity")
    print("=" * 78)
    for page_id, status, src_count, out_count, detail in rows:
        mark = "✓" if status == "ok" else "✗"
        print(f"  {mark} {page_id:<18} {status:<9} source {src_count:>7,} tokens   output {out_count:>7,}")
        if detail:
            print(detail)
    print()
    print("Structural counts")
    print("=" * 78)
    for key, (expected, actual) in counts.items():
        mark = "✓" if expected == actual else "✗"
        if expected != actual:
            failures += 1
        print(f"  {mark} {key:<12} source {expected:>7,}   output {actual:>7,}")

    # Cover image check
    cover = DIST / "images" / "cover.jpg"
    print(f"  {'✓' if cover.exists() else '✗'} cover image  {'present' if cover.exists() else 'MISSING'}")
    if not cover.exists():
        failures += 1

    total_source = sum(len(tokens(source_text[name])) for name in source_text)
    total_output = sum(r[3] for r in rows)
    print()
    print(f"Total compared tokens: source {total_source:,} / output {total_output:,}")
    print(f"Result: {'PASS' if failures == 0 else 'FAIL'} ({failures} failure{'s' if failures != 1 else ''})")

    report = {
        "pass": failures == 0,
        "failures": failures,
        "pages": [
            {"page": r[0], "status": r[1], "source_tokens": r[2], "output_tokens": r[3], "detail": r[4]}
            for r in rows
        ],
        "counts": {k: {"expected": v[0], "actual": v[1]} for k, v in counts.items()},
    }
    (CONTENT / "fidelity-report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
