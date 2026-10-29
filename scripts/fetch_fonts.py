#!/usr/bin/env python3
"""Download the bundled Google Fonts subsets and write the font manifest.

This is a maintainer script. The generated site never fetches fonts at runtime;
run it only when updating the vendored font files. The resulting WOFF2 files and
``font-manifest.json`` are committed to the repository.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FONT_DIR = ROOT / "epub2web" / "theme" / "assets" / "fonts"
MANIFEST = FONT_DIR / "font-manifest.json"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Family, Google Fonts query, filename prefix, and the subsets to vendor.
FAMILIES = [
    ("Fraunces", "Fraunces:opsz,wght@9..144,100..900", "fraunces", {"latin", "latin-ext"}),
    (
        "Inter",
        "Inter:wght@100..900",
        "inter",
        {"latin", "latin-ext", "greek", "greek-ext", "cyrillic", "cyrillic-ext"},
    ),
    (
        "Literata",
        "Literata:opsz,wght@7..72,200..900",
        "literata",
        {"latin", "latin-ext", "greek", "greek-ext", "cyrillic", "cyrillic-ext"},
    ),
    ("Noto Naskh Arabic", "Noto+Naskh+Arabic:wght@400..700", "noto-naskh-arabic", {"arabic"}),
    ("Noto Sans Arabic", "Noto+Sans+Arabic:wght@100..900", "noto-sans-arabic", {"arabic"}),
    ("Noto Serif Hebrew", "Noto+Serif+Hebrew:wght@100..900", "noto-serif-hebrew", {"hebrew"}),
    ("Noto Sans Hebrew", "Noto+Sans+Hebrew:wght@100..900", "noto-sans-hebrew", {"hebrew"}),
    (
        "Noto Serif Devanagari",
        "Noto+Serif+Devanagari:wght@100..900",
        "noto-serif-devanagari",
        {"devanagari"},
    ),
    (
        "Noto Sans Devanagari",
        "Noto+Sans+Devanagari:wght@100..900",
        "noto-sans-devanagari",
        {"devanagari"},
    ),
    ("Noto Serif Thai", "Noto+Serif+Thai:wght@100..900", "noto-serif-thai", {"thai"}),
    ("Noto Sans Thai", "Noto+Sans+Thai:wght@100..900", "noto-sans-thai", {"thai"}),
]

CJK_FAMILIES = [
    ("sc", "Noto+Serif+SC:wght@200..900"),
    ("tc", "Noto+Serif+TC:wght@200..900"),
    ("jp", "Noto+Serif+JP:wght@200..900"),
    ("kr", "Noto+Serif+KR:wght@200..900"),
]

SUBSET_SCRIPT = {
    "latin": "latin",
    "latin-ext": "latin",
    "greek": "greek",
    "greek-ext": "greek",
    "cyrillic": "cyrillic",
    "cyrillic-ext": "cyrillic",
    "arabic": "arabic",
    "hebrew": "hebrew",
    "devanagari": "devanagari",
    "thai": "thai",
}

CJK_RANGES = (
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
)

FACE_RE = re.compile(
    r"(?:/\*\s*(?P<subset>[^*]+?)\s*\*/\s*)?@font-face\s*\{(?P<body>.*?)\}",
    re.S,
)


def _fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def _css(query: str) -> str:
    return _fetch(f"https://fonts.googleapis.com/css2?family={query}&display=swap").decode("utf-8")


def _property(body: str, name: str) -> str:
    match = re.search(rf"^\s*{re.escape(name)}:\s*([^;]+);", body, re.M)
    return match.group(1).strip() if match else ""


def _parse_ranges(value: str) -> list[tuple[int, int]]:
    ranges = []
    for token in value.split(","):
        token = token.strip().removeprefix("U+")
        if not token:
            continue
        if "-" in token:
            start, end = token.split("-", 1)
        else:
            start = end = token
        ranges.append((int(start, 16), int(end, 16)))
    return ranges


def _intersects(ranges: list[tuple[int, int]], wanted: tuple[tuple[int, int], ...]) -> bool:
    return any(start <= wend and wstart <= end for start, end in ranges for wstart, wend in wanted)


def _faces(css: str) -> list[dict]:
    found = []
    for match in FACE_RE.finditer(css):
        body = match.group("body")
        url = _property(body, "src")
        url_match = re.search(r"url\(([^)]+)\)", url)
        if not url_match:
            continue
        found.append(
            {
                "subset": (match.group("subset") or "").strip(),
                "family": _property(body, "font-family").strip("'\""),
                "style": _property(body, "font-style") or "normal",
                "weight": _property(body, "font-weight") or "400",
                "unicode_range": _property(body, "unicode-range"),
                "url": url_match.group(1).strip("'\""),
            }
        )
    return found


def main() -> int:
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    faces: list[dict] = []
    downloads: dict[str, str] = {}

    for family, query, prefix, wanted_subsets in FAMILIES:
        for face in _faces(_css(query)):
            subset = face["subset"]
            if subset not in wanted_subsets:
                continue
            relative = f"{prefix}-{subset}.woff2"
            faces.append(
                {
                    "script": SUBSET_SCRIPT[subset],
                    "family": family,
                    "style": face["style"],
                    "weight": face["weight"],
                    "file": relative,
                    "unicode_range": face["unicode_range"],
                    "subset": subset,
                }
            )
            downloads[relative] = face["url"]

    for region, query in CJK_FAMILIES:
        cjk_faces = [
            face
            for face in _faces(_css(query))
            if _intersects(_parse_ranges(face["unicode_range"]), CJK_RANGES)
        ]
        for index, face in enumerate(cjk_faces, 1):
            relative = f"cjk/{region}/noto-serif-{region}-{index:03d}.woff2"
            faces.append(
                {
                    "script": f"cjk-{region}",
                    "family": "epub2web-cjk",
                    "style": face["style"],
                    "weight": face["weight"],
                    "file": relative,
                    "unicode_range": face["unicode_range"],
                    "subset": f"cjk-{region}",
                }
            )
            downloads[relative] = face["url"]

    def download(item: tuple[str, str]) -> tuple[str, bytes]:
        relative, url = item
        return relative, _fetch(url)

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(download, downloads.items()))

    for path in FONT_DIR.rglob("*.woff2"):
        path.unlink()
    for relative, data in results:
        path = FONT_DIR / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    manifest = {
        "source": "Google Fonts",
        "license": "SIL Open Font License 1.1",
        "families": {
            "body": "Literata",
            "display": "Fraunces",
            "ui": "Inter",
            "cjk": "epub2web-cjk",
        },
        "faces": sorted(faces, key=lambda face: (face["script"], face["family"], face["file"])),
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    total = sum(path.stat().st_size for path in FONT_DIR.rglob("*.woff2"))
    print(f"Wrote {len(faces)} faces, {len(downloads)} files, {total / 1048576:.1f} MB")
    print(f"Manifest: {MANIFEST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
