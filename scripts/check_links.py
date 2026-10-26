#!/usr/bin/env python3
"""Check internal links, anchors, images, and duplicate ids in dist/."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"


def target_path(base: Path, path: str) -> Path | None:
    if not path:
        return base
    if path.startswith("/"):
        candidate = DIST / path.lstrip("/")
    else:
        candidate = (base.parent / path).resolve()
    try:
        candidate.relative_to(DIST.resolve())
    except ValueError:
        return None
    if path.endswith("/") or candidate.is_dir():
        candidate = candidate / "index.html"
    return candidate


def is_external(href: str) -> bool:
    return bool(re.match(r"^(https?:|mailto:|tel:|javascript:|data:)", href, re.I))


def main() -> int:
    html_files = sorted(p for p in DIST.rglob("*.html") if "pagefind" not in p.parts)
    soups: dict[Path, BeautifulSoup] = {}
    ids: dict[Path, set[str]] = {}
    duplicates: list[tuple[Path, str]] = []

    for path in html_files:
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "lxml")
        soups[path] = soup
        found, dups = set(), []
        for tag in soup.find_all(id=True):
            value = tag["id"]
            if value in found:
                dups.append(value)
            found.add(value)
        ids[path] = found
        duplicates.extend((path, value) for value in dups)

    broken: list[tuple[Path, str, str]] = []
    checked = 0

    for path, soup in soups.items():
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href == "#" or is_external(href):
                continue
            if href.startswith("/pagefind/"):
                continue
            checked += 1
            parts = urlsplit(href)
            target = target_path(path, parts.path) if parts.path else path
            if target is None or not target.exists():
                broken.append((path, href, "missing file"))
                continue
            if not target.suffix == ".html":
                continue
            if parts.fragment:
                if target == path:
                    target_ids = ids[path]
                else:
                    target_ids = ids.get(target)
                    if target_ids is None:
                        target_soup = BeautifulSoup(target.read_text(encoding="utf-8"), "lxml")
                        target_ids = {t["id"] for t in target_soup.find_all(id=True)}
                        ids[target] = target_ids
                if parts.fragment not in target_ids:
                    broken.append((path, href, "missing anchor"))

        for img in soup.find_all("img", src=True):
            src = img["src"]
            if is_external(src):
                continue
            target = target_path(path, urlsplit(src).path)
            checked += 1
            if target is None or not target.exists():
                broken.append((path, src, "missing image"))

        for source in soup.find_all("source", srcset=True):
            for item in source["srcset"].split(","):
                src = item.strip().split(" ")[0]
                if not src or is_external(src):
                    continue
                target = target_path(path, urlsplit(src).path)
                checked += 1
                if target is None or not target.exists():
                    broken.append((path, src, "missing source"))

        for tag in soup.find_all(attrs={"aria-describedby": True}):
            for ref in tag["aria-describedby"].split():
                if ref not in ids[path]:
                    broken.append((path, f"#{ref}", "missing aria-describedby target"))

    print("Internal link check")
    print("=" * 78)
    print(f"  pages checked: {len(html_files)}")
    print(f"  links/assets checked: {checked:,}")
    print(f"  duplicate ids: {len(duplicates)}")
    for path, value in duplicates[:20]:
        print(f"    {path.relative_to(DIST)}  duplicate id #{value}")
    print(f"  broken references: {len(broken)}")
    for path, href, reason in broken[:60]:
        print(f"    {path.relative_to(DIST)}  ->  {href}  ({reason})")
    if len(broken) > 60:
        print(f"    … and {len(broken) - 60} more")

    ok = not duplicates and not broken
    print(f"Result: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
