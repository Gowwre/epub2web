"""Script detection and self-hosted font selection.

The generated site embeds only the font subsets it needs. Font files and their
Unicode ranges live in ``theme/assets/fonts/font-manifest.json``; the files are
vendored assets, never fetched at build or runtime.
"""

from __future__ import annotations

import json
from bisect import bisect_left
from functools import lru_cache
from pathlib import Path

DEFAULT_FONT_MANIFEST = (
    Path(__file__).resolve().parent / "theme" / "assets" / "fonts" / "font-manifest.json"
)

# Ranges used to decide which scripts are present. The font manifest contains
# the actual per-file unicode-range values.
SCRIPT_RANGES: dict[str, tuple[tuple[int, int], ...]] = {
    "greek": ((0x0370, 0x03FF), (0x1F00, 0x1FFF)),
    "cyrillic": (
        (0x0400, 0x052F),
        (0x1C80, 0x1C8F),
        (0x2DE0, 0x2DFF),
        (0xA640, 0xA69F),
    ),
    "arabic": (
        (0x0600, 0x06FF),
        (0x0750, 0x077F),
        (0x0870, 0x08FF),
        (0xFB50, 0xFDFF),
        (0xFE70, 0xFEFF),
    ),
    "hebrew": ((0x0590, 0x05FF), (0xFB1D, 0xFB4F)),
    "devanagari": ((0x0900, 0x097F), (0xA8E0, 0xA8FF)),
    "thai": ((0x0E00, 0x0E7F),),
    "cjk": (
        (0x1100, 0x11FF),
        (0x2E80, 0x2FFF),
        (0x3000, 0x303F),
        (0x3040, 0x30FF),
        (0x3130, 0x318F),
        (0x31F0, 0x31FF),
        (0x3400, 0x4DBF),
        (0x4E00, 0x9FFF),
        (0xA960, 0xA97F),
        (0xAC00, 0xD7AF),
        (0xF900, 0xFAFF),
        (0xFF66, 0xFF9F),
        (0x20000, 0x2FA1F),
    ),
}

CJK_RANGES = SCRIPT_RANGES["cjk"]
RTL_LANGUAGES = {
    "ar",
    "arc",
    "ckb",
    "dv",
    "fa",
    "he",
    "iw",
    "khw",
    "ks",
    "pnb",
    "prs",
    "ps",
    "sd",
    "skr",
    "ug",
    "ur",
    "yi",
}
CHARACTER_METRIC_LANGUAGES = {"ja", "ko", "th", "zh"}


def _language_key(language: str) -> str:
    return (language or "").strip().lower().replace("_", "-")


def base_language(language: str) -> str:
    return _language_key(language).split("-", 1)[0]


def is_rtl_language(language: str) -> bool:
    key = _language_key(language)
    parts = key.split("-")
    return base_language(language) in RTL_LANGUAGES or "arab" in parts or "hebr" in parts


def uses_character_metrics(language: str) -> bool:
    return base_language(language) in CHARACTER_METRIC_LANGUAGES


def _in_ranges(codepoint: int, ranges: tuple[tuple[int, int], ...]) -> bool:
    return any(start <= codepoint <= end for start, end in ranges)


def detect_scripts(text: str) -> set[str]:
    """Return the script families present in *text*."""
    found: set[str] = set()
    for character in text:
        codepoint = ord(character)
        if codepoint < 0x0300:
            continue
        for script, ranges in SCRIPT_RANGES.items():
            if script not in found and _in_ranges(codepoint, ranges):
                found.add(script)
                if len(found) == len(SCRIPT_RANGES):
                    return found
    return found


def _parse_unicode_range(value: str) -> tuple[tuple[int, int], ...]:
    ranges = []
    for token in value.split(","):
        token = token.strip().removeprefix("U+").removeprefix("u+")
        if not token:
            continue
        if "-" in token:
            start, end = token.split("-", 1)
        else:
            start = end = token
        ranges.append((int(start, 16), int(end, 16)))
    return tuple(ranges)


@lru_cache(maxsize=1)
def load_font_manifest(path: str | Path | None = None) -> dict:
    manifest_path = Path(path) if path is not None else DEFAULT_FONT_MANIFEST
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _intersects_codepoints(ranges: tuple[tuple[int, int], ...], codepoints: list[int]) -> bool:
    for start, end in ranges:
        index = bisect_left(codepoints, start)
        if index < len(codepoints) and codepoints[index] <= end:
            return True
    return False


def _has_kana(codepoints: set[int]) -> bool:
    return any(
        0x3040 <= codepoint <= 0x30FF or 0x31F0 <= codepoint <= 0x31FF for codepoint in codepoints
    )


def _has_hangul(codepoints: set[int]) -> bool:
    return any(
        0x1100 <= codepoint <= 0x11FF
        or 0x3130 <= codepoint <= 0x318F
        or 0xAC00 <= codepoint <= 0xD7AF
        for codepoint in codepoints
    )


def _has_han(codepoints: set[int]) -> bool:
    return any(
        0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xF900 <= codepoint <= 0xFAFF
        or 0x20000 <= codepoint <= 0x2FA1F
        for codepoint in codepoints
    )


def language_cjk_region(language: str) -> str:
    key = _language_key(language)
    if key.startswith(("zh-hant", "zh-tw", "zh-hk", "zh-mo")):
        return "tc"
    if key.startswith("zh"):
        return "sc"
    if key.startswith("ja"):
        return "jp"
    if key.startswith("ko"):
        return "kr"
    return "sc"


def _primary_cjk_region(language: str, codepoints: set[int]) -> str:
    key = _language_key(language)
    if key.startswith(("zh", "ja", "ko")):
        return language_cjk_region(language)
    if _has_kana(codepoints):
        return "jp"
    if _has_hangul(codepoints):
        return "kr"
    return "sc"


def cjk_region(language: str, codepoints: set[int]) -> str:
    """Pick the primary CJK regional glyph set for a book."""
    return _primary_cjk_region(language, codepoints)


def cjk_regions(language: str, codepoints: set[int]) -> list[str]:
    """Return every CJK regional set needed by a mixed-script book."""
    regions: set[str] = set()
    if _has_kana(codepoints):
        regions.add("jp")
    if _has_hangul(codepoints):
        regions.add("kr")
    if _has_han(codepoints) or not regions:
        regions.add(language_cjk_region(language))
    primary = _primary_cjk_region(language, codepoints)
    return sorted(regions, key=lambda region: (region != primary, region))


def select_font_faces(
    scripts: set[str],
    language: str,
    codepoints: set[int],
    *,
    manifest: dict | None = None,
) -> tuple[list[dict], list[str]]:
    """Return the manifest faces needed for a book and its CJK regions."""
    data = manifest or load_font_manifest()
    faces = data.get("faces", [])
    selected = [face for face in faces if face.get("script") == "latin"]

    for script in ("greek", "cyrillic", "arabic", "hebrew", "devanagari", "thai"):
        if script in scripts:
            selected.extend(face for face in faces if face.get("script") == script)

    regions: list[str] = []
    if "cjk" in scripts:
        regions = cjk_regions(language, codepoints)
        cjk_codepoints = sorted(
            codepoint for codepoint in codepoints if _in_ranges(codepoint, CJK_RANGES)
        )
        for region in regions:
            cjk_faces = [
                face
                for face in faces
                if face.get("script") == f"cjk-{region}"
                and cjk_codepoints
                and _intersects_codepoints(
                    _parse_unicode_range(face.get("unicode_range", "")), cjk_codepoints
                )
            ]
            if not cjk_faces:
                cjk_faces = [face for face in faces if face.get("script") == f"cjk-{region}"]
            selected.extend(cjk_faces)

    # Keep the manifest's stable order and remove any duplicates.
    seen: set[str] = set()
    unique = []
    for face in selected:
        if face["file"] in seen:
            continue
        seen.add(face["file"])
        unique.append(face)
    return unique, regions


def render_font_css(faces: list[dict]) -> str:
    """Render the @font-face rules for the selected font files."""
    lines = [
        "/* Generated by epub2web. Self-hosted subsets; no remote font requests. */",
        "",
    ]
    for face in faces:
        lines.extend(
            [
                "@font-face {",
                f'  font-family: "{face["family"]}";',
                f"  font-style: {face['style']};",
                f"  font-weight: {face['weight']};",
                "  font-display: swap;",
                f'  src: url("fonts/{face["file"]}") format("woff2");',
                f"  unicode-range: {face['unicode_range']};",
                "}",
                "",
            ]
        )
    return "\n".join(lines)
