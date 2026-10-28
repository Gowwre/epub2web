"""Internal link, anchor, image, and duplicate-id checks for a rendered site."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from .paths import normalize_base_path, strip_base_path
from .progress import ProgressCallback
from .progress import report as report_progress

logger = logging.getLogger(__name__)


def _is_external(href: str) -> bool:
    return href.startswith("//") or bool(urlsplit(href).scheme)


def _target_path(dist: Path, base: Path, path: str) -> Path | None:
    if not path:
        return base
    if path.startswith("/"):
        candidate = (dist / path.lstrip("/")).resolve()
    else:
        candidate = (base.parent / path).resolve()
    try:
        candidate.relative_to(dist.resolve())
    except ValueError:
        return None
    if path.endswith("/") or candidate.is_dir():
        candidate = candidate / "index.html"
    return candidate


def check_site_links(
    dist_dir: str | Path,
    base_path: str = "",
    progress: ProgressCallback | None = None,
) -> dict:
    dist = Path(dist_dir).resolve()
    base_path = normalize_base_path(base_path)

    def local_path(value: str) -> str | None:
        """Return a site-relative path, or None when a subpath is missing."""
        path = urlsplit(value).path
        if (
            path.startswith("/")
            and base_path
            and not (path == base_path or path.startswith(base_path + "/"))
        ):
            return None
        return strip_base_path(path, base_path)

    html_files = sorted(dist.rglob("*.html"))
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
    total_pages = len(soups)
    report_progress(progress, "links", "Checking links", 0, total_pages)

    for page_index, (path, soup) in enumerate(soups.items(), 1):
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href == "#" or _is_external(href):
                continue
            checked += 1
            parts = urlsplit(href)
            local = local_path(href)
            if local is None:
                broken.append(
                    {
                        "file": str(path.relative_to(dist)),
                        "href": href,
                        "reason": "missing base path",
                    }
                )
                continue
            target = _target_path(dist, path, local) if parts.path else path
            if target is None or not target.exists():
                broken.append(
                    {"file": str(path.relative_to(dist)), "href": href, "reason": "missing file"}
                )
                continue
            if target.suffix != ".html" or not parts.fragment:
                continue
            target_ids = ids.get(target)
            if target_ids is None:
                target_soup = BeautifulSoup(target.read_text(encoding="utf-8"), "lxml")
                target_ids = {t["id"] for t in target_soup.find_all(id=True)}
                ids[target] = target_ids
            if parts.fragment not in target_ids:
                broken.append(
                    {"file": str(path.relative_to(dist)), "href": href, "reason": "missing anchor"}
                )

        for img in soup.find_all("img", src=True):
            src = img["src"]
            if _is_external(src):
                continue
            checked += 1
            local = local_path(src)
            if local is None:
                broken.append(
                    {
                        "file": str(path.relative_to(dist)),
                        "href": src,
                        "reason": "missing base path",
                    }
                )
                continue
            target = _target_path(dist, path, local)
            if target is None or not target.exists():
                broken.append(
                    {"file": str(path.relative_to(dist)), "href": src, "reason": "missing image"}
                )

        for tags, attribute in (
            (soup.find_all("link", href=True), "href"),
            (soup.find_all("script", src=True), "src"),
        ):
            for element in tags:
                value = element[attribute].strip()
                if not value or _is_external(value) or value.startswith("#"):
                    continue
                checked += 1
                local = local_path(value)
                if local is None:
                    broken.append(
                        {
                            "file": str(path.relative_to(dist)),
                            "href": value,
                            "reason": "missing base path",
                        }
                    )
                    continue
                target = _target_path(dist, path, local)
                if target is None or not target.exists():
                    broken.append(
                        {
                            "file": str(path.relative_to(dist)),
                            "href": value,
                            "reason": "missing asset",
                        }
                    )

        for source in soup.find_all("source", srcset=True):
            # Data URIs contain commas, so do not split those. Generated
            # srcsets are plain paths; source EPUB srcsets are not emitted.
            if "data:" in source["srcset"]:
                continue
            for item in source["srcset"].split(","):
                src = item.strip().split(" ")[0]
                if not src or _is_external(src):
                    continue
                checked += 1
                local = local_path(src)
                if local is None:
                    broken.append(
                        {
                            "file": str(path.relative_to(dist)),
                            "href": src,
                            "reason": "missing base path",
                        }
                    )
                    continue
                target = _target_path(dist, path, local)
                if target is None or not target.exists():
                    broken.append(
                        {
                            "file": str(path.relative_to(dist)),
                            "href": src,
                            "reason": "missing source",
                        }
                    )

        for attribute in ("aria-describedby", "aria-labelledby"):
            for tag in soup.find_all(attrs={attribute: True}):
                for ref in tag[attribute].split():
                    if ref not in ids[path]:
                        broken.append(
                            {
                                "file": str(path.relative_to(dist)),
                                "href": f"#{ref}",
                                "reason": f"missing {attribute} target",
                            }
                        )
        report_progress(progress, "links", "Checking links", page_index, total_pages)

    for stylesheet in sorted(dist.rglob("*.css")):
        text = stylesheet.read_text(encoding="utf-8")
        for match in re.finditer(r"url\(\s*['\"]?([^'\"\)]+)['\"]?\s*\)", text):
            value = match.group(1).strip()
            if not value or _is_external(value) or value.startswith(("#", "data:")):
                continue
            checked += 1
            local = local_path(value)
            if local is None:
                broken.append(
                    {
                        "file": str(stylesheet.relative_to(dist)),
                        "href": value,
                        "reason": "missing base path",
                    }
                )
                continue
            target = _target_path(dist, stylesheet, local)
            if target is None or not target.exists():
                broken.append(
                    {
                        "file": str(stylesheet.relative_to(dist)),
                        "href": value,
                        "reason": "missing stylesheet asset",
                    }
                )

    for item in broken:
        logger.info("broken reference", extra=item)
    for item in duplicates:
        logger.info("duplicate id", extra=item)
    logger.info(
        "link gate",
        extra={
            "status": "pass" if not broken and not duplicates else "fail",
            "pages": len(html_files),
            "checked": checked,
            "broken": len(broken),
            "duplicates": len(duplicates),
        },
    )
    return {
        "ok": not duplicates and not broken,
        "pages": len(html_files),
        "checked": checked,
        "duplicates": duplicates,
        "broken": broken,
    }
