"""Internal link, anchor, image, and duplicate-id checks for a rendered site."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup


def _is_external(href: str) -> bool:
    return bool(re.match(r"^(https?:|mailto:|tel:|javascript:|data:)", href, re.I))


def _target_path(dist: Path, base: Path, path: str) -> Path | None:
    if not path:
        return base
    if path.startswith("/"):
        candidate = dist / path.lstrip("/")
    else:
        candidate = (base.parent / path).resolve()
    try:
        candidate.relative_to(dist.resolve())
    except ValueError:
        return None
    if path.endswith("/") or candidate.is_dir():
        candidate = candidate / "index.html"
    return candidate


def check_site_links(dist_dir: str | Path) -> dict:
    dist = Path(dist_dir).resolve()
    html_files = sorted(p for p in dist.rglob("*.html") if "pagefind" not in p.parts)
    soups: dict[Path, BeautifulSoup] = {}
    ids: dict[Path, set[str]] = {}
    duplicates: list[dict] = []

    for path in html_files:
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "lxml")
        soups[path] = soup
        found: set[str] = set()
        dups: list[str] = []
        for tag in soup.find_all(id=True):
            value = tag["id"]
            if value in found:
                dups.append(value)
            found.add(value)
        ids[path] = found
        for value in dups:
            duplicates.append({"file": str(path.relative_to(dist)), "id": value})

    broken: list[dict] = []
    checked = 0

    for path, soup in soups.items():
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href == "#" or _is_external(href) or href.startswith("/pagefind/"):
                continue
            checked += 1
            parts = urlsplit(href)
            target = _target_path(dist, path, parts.path) if parts.path else path
            if target is None or not target.exists():
                broken.append({"file": str(path.relative_to(dist)), "href": href, "reason": "missing file"})
                continue
            if target.suffix != ".html" or not parts.fragment:
                continue
            if target == path:
                target_ids = ids[path]
            else:
                target_ids = ids.get(target)
                if target_ids is None:
                    target_soup = BeautifulSoup(target.read_text(encoding="utf-8"), "lxml")
                    target_ids = {t["id"] for t in target_soup.find_all(id=True)}
                    ids[target] = target_ids
            if parts.fragment not in target_ids:
                broken.append({"file": str(path.relative_to(dist)), "href": href, "reason": "missing anchor"})

        for img in soup.find_all("img", src=True):
            src = img["src"]
            if _is_external(src):
                continue
            checked += 1
            target = _target_path(dist, path, urlsplit(src).path)
            if target is None or not target.exists():
                broken.append({"file": str(path.relative_to(dist)), "href": src, "reason": "missing image"})

        for source in soup.find_all("source", srcset=True):
            for item in source["srcset"].split(","):
                src = item.strip().split(" ")[0]
                if not src or _is_external(src):
                    continue
                checked += 1
                target = _target_path(dist, path, urlsplit(src).path)
                if target is None or not target.exists():
                    broken.append({"file": str(path.relative_to(dist)), "href": src, "reason": "missing source"})

        for tag in soup.find_all(attrs={"aria-describedby": True}):
            for ref in tag["aria-describedby"].split():
                if ref not in ids[path]:
                    broken.append({"file": str(path.relative_to(dist)), "href": f"#{ref}", "reason": "missing aria-describedby target"})

    return {
        "ok": not duplicates and not broken,
        "pages": len(html_files),
        "checked": checked,
        "duplicates": duplicates,
        "broken": broken,
    }
