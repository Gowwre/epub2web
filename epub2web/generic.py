"""Deterministic EPUB extraction orchestration.

This module reads and sanitizes spine documents, plans reading pages, converts
them into semantic fragments, processes images, and writes the book metadata.
The fidelity gate verifies every rendered page against its source before a
build can succeed.
"""

from __future__ import annotations

import base64
import binascii
import contextlib
import hashlib
import io
import json
import logging
import re
import warnings
from pathlib import Path

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from PIL import Image, ImageOps

from .clean import clean_doc, sanitize_svg, svg_size
from .converter import PageConverter
from .epub import Epub, ManifestItem
from .models import PagePlan
from .navigation import SiteTocBuilder
from .planner import PagePlanner
from .progress import ProgressCallback, report
from .text import reading_units, slugify, split_title, year_from_date

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
logger = logging.getLogger(__name__)

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
        self.items: list[ManifestItem] = []
        self.cleaned: dict[str, BeautifulSoup] = {}
        self.cover_info: dict | None = None
        self.cover_source = ""
        self.images: dict[str, dict] = {}
        self.image_errors: list[str] = []
        self.pages: list[PagePlan] = []
        self.page_by_path: dict[str, PagePlan] = {}
        self.route_by_path: dict[str, str] = {}
        self.route_by_target: dict[tuple[str, str], str] = {}
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

            self.pages = PagePlanner(
                book=self.book,
                items=self.items,
                cleaned=self.cleaned,
                cover_info=self.cover_info,
            ).plan()
            logger.debug("pages planned", extra={"count": len(self.pages)})
            if not self.pages:
                raise ValueError("no readable pages found in the EPUB spine")
            self._build_route_maps()
            converter = PageConverter(
                book=self.book,
                images=self.images,
                route_by_path=self.route_by_path,
                route_by_target=self.route_by_target,
            )

            fragments = {}
            source_text = {}
            total_pages = len(self.pages)
            self._report("extract-pages", "Laying out pages", 0, total_pages)
            for index, page in enumerate(self.pages, 1):
                page.images = sum(
                    1
                    for part in page.parts
                    for block in part.blocks
                    for img in ([block] if block.name == "img" else block.find_all("img"))
                )
                page_source = page.source_text
                source_text[page.id] = page_source
                fragment, sections = converter.convert(page)
                page.sections = sections
                page.figure_count = fragment.count("<figure")
                page.words = len(page_source.split())
                page.characters = sum(1 for character in page_source if not character.isspace())
                page.reading_units = reading_units(page_source)
                fragments[page.id] = fragment
                self._report("extract-pages", "Laying out pages", index, total_pages)

            self.pages = [page for page in self.pages if page.id in fragments]
            if not self.pages:
                raise ValueError("no readable pages found in the EPUB spine")
            self.page_by_path = {page.source_files[0]: page for page in self.pages}
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
    def _build_route_maps(self) -> None:
        """Map source files and anchors to the page that now contains them."""
        self.route_by_path = {}
        self.route_by_target = {}
        self.page_by_path = {}
        for page in self.pages:
            for part in page.parts:
                path = part.path
                self.route_by_path.setdefault(path, page.route)
                self.page_by_path.setdefault(path, page)
                for block in part.blocks:
                    for tag in [block, *block.find_all(id=True)]:
                        anchor_id = tag.get("id")
                        if anchor_id:
                            self.route_by_target.setdefault((path, anchor_id), page.route)

    # -- conversion -------------------------------------------------------
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
            page.in_toc = page.id in site_toc.page_ids

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

        pages = [page.to_dict() for page in self.pages]

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
