"""Deterministic EPUB container reader.

Supports EPUB 2 (NCX) and EPUB 3 (nav document), plus the common OPF
metadata/cover conventions. No network, no LLM, no heuristics about prose.
"""

from __future__ import annotations

import posixpath
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlsplit

import warnings

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


@dataclass
class ManifestItem:
    id: str
    href: str          # relative to the OPF directory, URL-decoded
    path: str          # zip path
    media_type: str
    properties: str = ""


@dataclass
class TocEntry:
    label: str
    href: str          # original href
    path: str          # resolved zip path ('' if external)
    fragment: str
    depth: int
    children: list["TocEntry"] = field(default_factory=list)


@dataclass
class GuideRef:
    type: str
    title: str
    href: str
    path: str
    fragment: str


class Epub:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.zf = zipfile.ZipFile(self.path)
        self.opf_path = self._find_opf()
        self.opf_dir = posixpath.dirname(self.opf_path)
        self.opf = BeautifulSoup(self.zf.read(self.opf_path), "xml")
        self.metadata = self._read_metadata()
        self.manifest: dict[str, ManifestItem] = self._read_manifest()
        self.spine: list[ManifestItem] = self._read_spine()
        self.guide: list[GuideRef] = self._read_guide()
        self.nav_item = self._find_nav_item()
        self.toc: list[TocEntry] = self._read_toc()
        self.cover_item = self._find_cover()

    # -- helpers ---------------------------------------------------------
    @staticmethod
    def _text(node) -> str:
        return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip() if node else ""

    @staticmethod
    def _resolve(base_path: str, href: str) -> tuple[str, str]:
        if not href:
            return "", ""
        parts = urlsplit(href)
        if parts.scheme or href.startswith("//"):
            return "", parts.fragment
        path = unquote(parts.path)
        if not path:
            return base_path, parts.fragment
        joined = posixpath.normpath(posixpath.join(posixpath.dirname(base_path), path))
        if joined.startswith("../"):
            joined = joined.lstrip("./")
        return joined, parts.fragment

    def _find_opf(self) -> str:
        container = BeautifulSoup(self.zf.read("META-INF/container.xml"), "xml")
        rootfile = container.find("rootfile")
        if not rootfile or not rootfile.get("full-path"):
            raise ValueError("EPUB has no rootfile in META-INF/container.xml")
        return rootfile["full-path"]

    # -- metadata --------------------------------------------------------
    def _read_metadata(self) -> dict:
        md = self.opf.find("metadata")
        if not md:
            return {}
        title = self._text(md.find("dc:title")) or self._text(md.find("title"))
        creators = []
        for node in md.find_all("dc:creator"):
            name = self._text(node)
            if name:
                creators.append(name)
        if not creators:
            creators = [self._text(n) for n in md.find_all("creator") if self._text(n)]

        dates = []
        for node in md.find_all("dc:date"):
            event = (node.get("opf:event") or node.get("event") or "").lower()
            if event != "conversion":
                dates.append(self._text(node))
        if not dates:
            dates = [self._text(n) for n in md.find_all("date") if self._text(n)]

        identifiers = []
        for node in md.find_all(["dc:identifier", "identifier"]):
            value = self._text(node)
            scheme = (node.get("opf:scheme") or node.get("scheme") or "").lower()
            if value:
                identifiers.append({"value": value, "scheme": scheme})
        isbn = next((i["value"] for i in identifiers if i["scheme"] == "isbn"), "")
        if not isbn:
            m = re.search(r"97[89][\d-]{10,}", " ".join(i["value"] for i in identifiers))
            if m:
                isbn = m.group(0)

        description = ""
        node = md.find("dc:description")
        if node:
            description = BeautifulSoup(self._text(node), "lxml").get_text(" ", strip=True)

        subjects = [self._text(n) for n in md.find_all("dc:subject") if self._text(n)]
        cover_id = ""
        for meta in md.find_all("meta"):
            if (meta.get("name") or "").lower() == "cover":
                cover_id = meta.get("content") or ""
                break

        return {
            "title": title,
            "creator": " and ".join(creators),
            "creators": creators,
            "language": self._text(md.find("dc:language")) or self._text(md.find("language")) or "en",
            "publisher": self._text(md.find("dc:publisher")) or self._text(md.find("publisher")),
            "date": dates[0] if dates else "",
            "isbn": isbn,
            "identifiers": identifiers,
            "description": description,
            "rights": self._text(md.find("dc:rights")) or self._text(md.find("rights")),
            "subjects": subjects,
            "cover_id": cover_id,
        }

    # -- manifest / spine -------------------------------------------------
    def _read_manifest(self) -> dict[str, ManifestItem]:
        manifest = {}
        for item in self.opf.find_all("item"):
            item_id = item.get("id") or ""
            href = item.get("href") or ""
            if not item_id or not href:
                continue
            path, _ = self._resolve(self.opf_path, href)
            manifest[item_id] = ManifestItem(
                id=item_id,
                href=href,
                path=path,
                media_type=item.get("media-type") or "",
                properties=item.get("properties") or "",
            )
        return manifest

    def _read_spine(self) -> list[ManifestItem]:
        spine = self.opf.find("spine")
        result = []
        if not spine:
            return result
        for ref in spine.find_all("itemref"):
            item = self.manifest.get(ref.get("idref") or "")
            if not item:
                continue
            if item.media_type not in ("application/xhtml+xml", "text/html"):
                continue
            result.append(item)
        return result

    def _read_guide(self) -> list[GuideRef]:
        guide = self.opf.find("guide")
        result = []
        if not guide:
            return result
        for ref in guide.find_all("reference"):
            href = ref.get("href") or ""
            path, fragment = self._resolve(self.opf_path, href)
            result.append(GuideRef(
                type=ref.get("type") or "",
                title=ref.get("title") or "",
                href=href,
                path=path,
                fragment=fragment,
            ))
        return result

    # -- nav / NCX --------------------------------------------------------
    def _find_nav_item(self) -> ManifestItem | None:
        for item in self.manifest.values():
            if "nav" in item.properties.split():
                return item
        return None

    def _read_toc(self) -> list[TocEntry]:
        if self.nav_item:
            entries = self._read_nav(self.nav_item)
            if entries:
                return entries
        return self._read_ncx()

    def _read_nav(self, item: ManifestItem) -> list[TocEntry]:
        try:
            soup = BeautifulSoup(self.zf.read(item.path), "lxml")
        except Exception:
            return []
        nav = None
        for candidate in soup.find_all("nav"):
            epub_type = candidate.get("epub:type") or candidate.get("type") or ""
            if "toc" in epub_type.split():
                nav = candidate
                break
        if nav is None:
            nav = soup.find("nav")
        if nav is None:
            return []
        entries: list[TocEntry] = []

        def walk(ol, depth):
            for li in ol.find_all("li", recursive=False):
                a = li.find("a", recursive=False)
                if a is None:
                    # EPUB3 sometimes wraps the label in a span and puts
                    # links in a nested list.
                    span = li.find("span", recursive=False)
                    label = self._text(span) if span else ""
                    href = ""
                    path = ""
                    fragment = ""
                else:
                    label = self._text(a)
                    href = a.get("href") or ""
                    path, fragment = self._resolve(item.path, href)
                nested = li.find("ol", recursive=False)
                if label:
                    entry = TocEntry(
                        label=label, href=href, path=path, fragment=fragment,
                        depth=depth, children=[],
                    )
                    entries.append(entry)
                    if nested is not None:
                        child_before = len(entries)
                        walk(nested, depth + 1)
                        entry.children = entries[child_before:]
                elif nested is not None:
                    walk(nested, depth)

        ol = nav.find("ol")
        if ol:
            walk(ol, 0)
        return entries

    def _read_ncx(self) -> list[TocEntry]:
        ncx_item = None
        spine = self.opf.find("spine")
        toc_id = spine.get("toc") if spine else None
        if toc_id:
            ncx_item = self.manifest.get(toc_id)
        if ncx_item is None:
            ncx_item = next((i for i in self.manifest.values()
                             if i.media_type == "application/x-dtbncx+xml"), None)
        if ncx_item is None:
            return []
        try:
            soup = BeautifulSoup(self.zf.read(ncx_item.path), "xml")
        except Exception:
            return []
        nav_map = soup.find("navMap")
        if nav_map is None:
            return []
        entries: list[TocEntry] = []

        def walk(node, depth):
            for point in node.find_all("navPoint", recursive=False):
                label_node = point.find("navLabel")
                text_node = label_node.find("text") if label_node else None
                content = point.find("content")
                label = self._text(text_node)
                href = content.get("src") if content else ""
                path, fragment = self._resolve(ncx_item.path, href)
                if label:
                    entries.append(TocEntry(
                        label=label, href=href, path=path, fragment=fragment,
                        depth=depth, children=[],
                    ))
                nested = point.find("navPoint")
                if nested is not None:
                    walk(point, depth + 1)

        walk(nav_map, 0)
        return entries

    # -- cover ------------------------------------------------------------
    def _find_cover(self) -> ManifestItem | None:
        for item in self.manifest.values():
            if "cover-image" in item.properties.split():
                return item
        cover_id = self.metadata.get("cover_id")
        if cover_id and cover_id in self.manifest:
            return self.manifest[cover_id]
        for ref in self.guide:
            if ref.type == "cover":
                item = next((i for i in self.manifest.values() if i.path == ref.path), None)
                if item and item.media_type.startswith("image/"):
                    return item
                if item and item.media_type in ("application/xhtml+xml", "text/html"):
                    # A wrapper page: find the first image inside it.
                    try:
                        soup = BeautifulSoup(self.zf.read(item.path), "lxml")
                        img = soup.find("img")
                        if img and img.get("src"):
                            path, _ = self._resolve(item.path, img["src"])
                            return next((i for i in self.manifest.values() if i.path == path), None)
                    except Exception:
                        pass
        return None

    # -- public helpers ---------------------------------------------------
    def read(self, path: str) -> bytes:
        return self.zf.read(path)

    def html_spine(self) -> list[ManifestItem]:
        return [item for item in self.spine
                if item.media_type in ("application/xhtml+xml", "text/html")]

    def toc_flat(self) -> list[TocEntry]:
        flat = []
        def walk(entries):
            for entry in entries:
                flat.append(entry)
                walk(entry.children)
        walk(self.toc)
        return flat

    def close(self):
        self.zf.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
