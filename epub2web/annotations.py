"""Native highlight and note documents.

Annotations are private reader data. They are stored outside the generated
site and keyed by a book's normalized-text ``content_id`` so they survive
re-zipping and metadata-only EPUB changes. This module owns the portable JSON
shape, validation, identity, and merge rules; it does not touch the browser
store or any reader application's files.

The browser implementation mirrors this schema, but this module is the
canonical definition and the target for future CLI import/export commands.
"""

from __future__ import annotations

import contextlib
import copy
import json
import os
import re
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "epub2web.annotations"
VERSION = 1
ANNOTATION_TYPES = frozenset({"highlight", "bookmark"})
HIGHLIGHT_COLORS = ("yellow", "green", "blue", "pink", "purple")

# Stable UUIDv5 namespace for deterministic imported-annotation ids.
ANNOTATION_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://epub2web.local/annotations")

_CONTENT_ID_RE = re.compile(r"^[0-9a-f]{64}$")


class AnnotationError(ValueError):
    """Raised when an annotation document or record is malformed."""


# -- timestamps ---------------------------------------------------------
def parse_timestamp(value: Any) -> datetime:
    """Parse an ISO 8601 timestamp as UTC.

    Naive timestamps are treated as UTC, matching calibre's merge behavior.
    """
    if not isinstance(value, str) or not value.strip():
        raise AnnotationError("timestamp must be a non-empty ISO 8601 string")
    text = value.strip()
    if "T" not in text:
        raise AnnotationError(f"timestamp is missing a time: {value!r}")
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise AnnotationError(f"invalid timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def format_timestamp(value: datetime) -> str:
    """Format a datetime as a canonical UTC timestamp."""
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def now_timestamp() -> str:
    return format_timestamp(datetime.now(timezone.utc))


# -- identity -----------------------------------------------------------
def annotation_id(content_id: str, app: str, origin_id: str) -> str:
    """Derive a stable id for an annotation imported from another app."""
    if not content_id or not app or not origin_id:
        raise AnnotationError("content_id, app, and origin_id are required for an imported id")
    return str(uuid.uuid5(ANNOTATION_NAMESPACE, "\0".join((content_id, app, origin_id))))


def _canonical_uuid(value: Any, field: str = "id") -> str:
    if not isinstance(value, str) or not value.strip():
        raise AnnotationError(f"{field} must be a non-empty UUID string")
    try:
        return str(uuid.UUID(value.strip()))
    except (AttributeError, ValueError) as exc:
        raise AnnotationError(f"{field} is not a valid UUID: {value!r}") from exc


# -- validation ---------------------------------------------------------
def _expect_mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AnnotationError(f"{field} must be an object")
    return value


def _optional_string(
    record: Mapping[str, Any],
    field: str,
    *,
    prefix: str = "",
    allow_empty: bool = True,
) -> str:
    value = record.get(field, "")
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise AnnotationError(f"{prefix}{field} must be a string")
    if not allow_empty and not value.strip():
        raise AnnotationError(f"{prefix}{field} must not be empty")
    return value


def _optional_bool(record: Mapping[str, Any], field: str, *, prefix: str = "") -> bool:
    value = record.get(field, False)
    if not isinstance(value, bool):
        raise AnnotationError(f"{prefix}{field} must be a boolean")
    return value


def _optional_int(
    record: Mapping[str, Any], field: str, *, prefix: str = "", minimum: int = 0
) -> int | None:
    value = record.get(field)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise AnnotationError(f"{prefix}{field} must be an integer")
    if value < minimum:
        raise AnnotationError(f"{prefix}{field} must be at least {minimum}")
    return value


def _validate_position(value: Any, field: str) -> dict[str, Any]:
    position = dict(_expect_mapping(value, field))
    for key in ("dom_path", "cfi"):
        if key in position:
            position[key] = _optional_string(position, key, prefix=f"{field}.")
    for key in ("offset", "char"):
        parsed = _optional_int(position, key, prefix=f"{field}.", minimum=0)
        if parsed is not None:
            position[key] = parsed
    unknown = set(position) - {"dom_path", "cfi", "offset", "char"}
    if unknown:
        raise AnnotationError(f"{field} has unknown fields: {', '.join(sorted(unknown))}")
    return position


def _validate_anchor(value: Any) -> dict[str, Any]:
    anchor = dict(_expect_mapping(value, "anchor"))
    for key in ("page_key", "chapter_key", "spine_href", "cfi", "prefix", "suffix"):
        if key in anchor:
            anchor[key] = _optional_string(anchor, key, prefix="anchor.")
    spine_index = _optional_int(anchor, "spine_index", prefix="anchor.", minimum=0)
    if spine_index is not None:
        anchor["spine_index"] = spine_index
    if "progression" in anchor:
        progression = anchor["progression"]
        if isinstance(progression, bool) or not isinstance(progression, (int, float)):
            raise AnnotationError("anchor.progression must be a number")
        if not 0 <= float(progression) <= 1:
            raise AnnotationError("anchor.progression must be between 0 and 1")
        anchor["progression"] = float(progression)
    for key in ("start", "end"):
        if key in anchor:
            anchor[key] = _validate_position(anchor[key], f"anchor.{key}")
    unknown = set(anchor) - {
        "page_key",
        "chapter_key",
        "spine_href",
        "spine_index",
        "cfi",
        "start",
        "end",
        "prefix",
        "suffix",
        "progression",
    }
    if unknown:
        raise AnnotationError(f"anchor has unknown fields: {', '.join(sorted(unknown))}")
    return anchor


def _validate_style(value: Any) -> dict[str, Any]:
    style = dict(_expect_mapping(value, "style"))
    if "color" in style:
        color = style["color"]
        if not isinstance(color, str) or not color.strip():
            raise AnnotationError("style.color must be a non-empty string")
        color = color.strip()
        if color not in HIGHLIGHT_COLORS:
            raise AnnotationError(f"style.color must be one of {', '.join(HIGHLIGHT_COLORS)}")
        style["color"] = color
    unknown = set(style) - {"color"}
    if unknown:
        raise AnnotationError(f"style has unknown fields: {', '.join(sorted(unknown))}")
    return style


def _validate_origin(value: Any) -> dict[str, Any]:
    origin = dict(_expect_mapping(value, "origin"))
    if "app" in origin:
        origin["app"] = _optional_string(origin, "app", prefix="origin.", allow_empty=False)
    if "id" in origin:
        origin["id"] = _optional_string(origin, "id", prefix="origin.")
    if "raw" in origin and not _is_json_value(origin["raw"]):
        raise AnnotationError("origin.raw must be JSON data")
    unknown = set(origin) - {"app", "id", "raw"}
    if unknown:
        raise AnnotationError(f"origin has unknown fields: {', '.join(sorted(unknown))}")
    return origin


def _is_json_value(value: Any) -> bool:
    if value is None or isinstance(value, (str, int, float, bool)):
        return True
    if isinstance(value, list):
        return all(_is_json_value(item) for item in value)
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and _is_json_value(item) for key, item in value.items())
    return False


def validate_annotation(record: Any, *, index: int | None = None) -> dict[str, Any]:
    """Validate one annotation and return a normalized copy."""
    prefix = f"annotations[{index}]: " if index is not None else "annotation: "
    source = _expect_mapping(record, f"{prefix}record")
    annotation = copy.deepcopy(dict(source))

    annotation["id"] = _canonical_uuid(source.get("id"), f"{prefix}id")
    kind = source.get("type")
    if kind not in ANNOTATION_TYPES:
        raise AnnotationError(f"{prefix}type must be one of {sorted(ANNOTATION_TYPES)}")
    annotation["type"] = kind
    annotation["created"] = format_timestamp(
        parse_timestamp(source.get("created", source.get("updated")))
    )
    annotation["updated"] = format_timestamp(
        parse_timestamp(source.get("updated", source.get("created")))
    )
    annotation["deleted"] = _optional_bool(source, "deleted", prefix=prefix)
    annotation["note"] = _optional_string(source, "note", prefix=prefix)
    annotation["quote"] = _optional_string(source, "quote", prefix=prefix)

    if "style" in source:
        annotation["style"] = _validate_style(source["style"])
    else:
        annotation["style"] = {}
    if "anchor" in source:
        annotation["anchor"] = _validate_anchor(source["anchor"])
    else:
        annotation["anchor"] = {}
    if "origin" in source:
        annotation["origin"] = _validate_origin(source["origin"])

    for field in ("needs_review", "conflict"):
        if field in source:
            annotation[field] = _optional_bool(source, field, prefix=prefix)
    if "review_reason" in source:
        annotation["review_reason"] = _optional_string(source, "review_reason", prefix=prefix)
    return annotation


def validate_book(book: Any) -> dict[str, Any]:
    source = _expect_mapping(book, "book")
    data = copy.deepcopy(dict(source))
    content_id = source.get("content_id")
    if not isinstance(content_id, str) or not _CONTENT_ID_RE.fullmatch(content_id):
        raise AnnotationError("book.content_id must be a 64-character lowercase SHA-256 hash")
    data["content_id"] = content_id

    source_sha256 = source.get("source_sha256", "")
    if source_sha256 not in (None, "") and (
        not isinstance(source_sha256, str) or not _CONTENT_ID_RE.fullmatch(source_sha256)
    ):
        raise AnnotationError("book.source_sha256 must be a 64-character lowercase SHA-256 hash")
    data["source_sha256"] = source_sha256 or ""

    for field in ("title", "author", "isbn"):
        data[field] = _optional_string(source, field, prefix="book.")
    aliases = source.get("aliases", [])
    if not isinstance(aliases, list):
        raise AnnotationError("book.aliases must be a list")
    normalized_aliases = []
    for index, alias in enumerate(aliases):
        item = _expect_mapping(alias, f"book.aliases[{index}]")
        scheme = _optional_string(
            item, "scheme", prefix=f"book.aliases[{index}].", allow_empty=False
        )
        value = _optional_string(item, "value", prefix=f"book.aliases[{index}].", allow_empty=False)
        normalized_aliases.append({"scheme": scheme, "value": value})
    data["aliases"] = normalized_aliases
    return data


def validate_document(data: Any) -> dict[str, Any]:
    """Validate a native annotation document and return a normalized copy."""
    source = _expect_mapping(data, "document")
    if source.get("schema") != SCHEMA:
        raise AnnotationError(f"document.schema must be {SCHEMA!r}")
    version = source.get("version")
    if isinstance(version, bool) or not isinstance(version, int) or version != VERSION:
        raise AnnotationError(f"document.version must be {VERSION}")
    book = validate_book(source.get("book"))
    annotations = source.get("annotations")
    if not isinstance(annotations, list):
        raise AnnotationError("document.annotations must be a list")

    normalized = []
    seen_ids = set()
    seen_origins = set()
    for index, record in enumerate(annotations):
        annotation = validate_annotation(record, index=index)
        if annotation["id"] in seen_ids:
            raise AnnotationError(f"duplicate annotation id: {annotation['id']}")
        seen_ids.add(annotation["id"])
        origin = annotation.get("origin") or {}
        origin_key = (origin.get("app", ""), origin.get("id", ""))
        if origin_key[0] and origin_key[1]:
            if origin_key in seen_origins:
                raise AnnotationError(
                    f"duplicate annotation origin: {origin_key[0]}/{origin_key[1]}"
                )
            seen_origins.add(origin_key)
        normalized.append(annotation)

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "book": book,
        "annotations": normalized,
    }


def make_document(
    book: Mapping[str, Any], annotations: Iterable[Mapping[str, Any]] = ()
) -> dict[str, Any]:
    """Build and validate a native document for a book."""
    return validate_document(
        {
            "schema": SCHEMA,
            "version": VERSION,
            "book": dict(book),
            "annotations": list(annotations),
        }
    )


# -- merge --------------------------------------------------------------
@dataclass
class MergeReport:
    added: int = 0
    updated: int = 0
    unchanged: int = 0
    ignored: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "added": self.added,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "ignored": self.ignored,
        }


def _has_resolved_anchor(annotation: Mapping[str, Any]) -> bool:
    anchor = annotation.get("anchor") or {}
    return bool(
        anchor.get("start")
        or anchor.get("end")
        or anchor.get("cfi")
        or anchor.get("page_key")
        or annotation.get("quote")
    )


def _origin_key(annotation: Mapping[str, Any]) -> tuple[str, str]:
    origin = annotation.get("origin") or {}
    return str(origin.get("app") or ""), str(origin.get("id") or "")


def merge_documents(
    existing: Mapping[str, Any], incoming: Mapping[str, Any]
) -> tuple[dict[str, Any], MergeReport]:
    """Merge ``incoming`` into ``existing`` using newer-timestamp-wins rules.

    Annotations are matched by id, then by ``(origin.app, origin.id)``. A newer
    tombstone wins over an older active record and cannot be resurrected by an
    older import. Both documents must describe the same ``content_id``.
    """
    base = validate_document(existing)
    update = validate_document(incoming)
    if base["book"]["content_id"] != update["book"]["content_id"]:
        raise AnnotationError("cannot merge annotations from different books")

    report = MergeReport()
    by_id = {annotation["id"]: annotation for annotation in base["annotations"]}
    by_origin = {
        _origin_key(annotation): annotation
        for annotation in base["annotations"]
        if all(_origin_key(annotation))
    }

    for record in update["annotations"]:
        current = by_id.get(record["id"])
        if current is None:
            key = _origin_key(record)
            if all(key):
                current = by_origin.get(key)
        if current is None:
            base["annotations"].append(record)
            by_id[record["id"]] = record
            key = _origin_key(record)
            if all(key):
                by_origin[key] = record
            report.added += 1
            continue

        current_updated = parse_timestamp(current["updated"])
        incoming_updated = parse_timestamp(record["updated"])
        replace = incoming_updated > current_updated or (
            incoming_updated == current_updated
            and _has_resolved_anchor(record)
            and not _has_resolved_anchor(current)
        )
        if not replace:
            if incoming_updated == current_updated:
                report.unchanged += 1
            else:
                report.ignored += 1
            continue

        replacement = copy.deepcopy(record)
        # Preserve the established local id even when the import matched by
        # origin identity rather than by id.
        replacement["id"] = current["id"]
        index = base["annotations"].index(current)
        base["annotations"][index] = replacement
        by_id.pop(current["id"], None)
        by_id[replacement["id"]] = replacement
        old_key = _origin_key(current)
        new_key = _origin_key(replacement)
        if all(old_key):
            by_origin.pop(old_key, None)
        if all(new_key):
            by_origin[new_key] = replacement
        report.updated += 1

    return base, report


# -- files --------------------------------------------------------------
def loads_document(text: str | bytes) -> dict[str, Any]:
    """Parse and validate a native annotation document."""
    try:
        data = json.loads(text)
    except (TypeError, ValueError) as exc:
        raise AnnotationError(f"annotation document is not valid JSON: {exc}") from exc
    return validate_document(data)


def load_document(path: str | Path) -> dict[str, Any]:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise AnnotationError(f"could not read annotation document: {exc}") from exc
    return loads_document(text)


def dumps_document(document: Mapping[str, Any]) -> str:
    """Serialize a validated document as deterministic, human-readable JSON."""
    normalized = validate_document(document)
    return json.dumps(normalized, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


def write_document(path: str | Path, document: Mapping[str, Any]) -> None:
    """Write a document atomically so an interrupted save cannot truncate it."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    text = dumps_document(document)
    temporary = target.with_name(f".{target.name}.tmp")
    try:
        temporary.write_text(text, encoding="utf-8")
        os.replace(temporary, target)
    except OSError:
        with contextlib.suppress(OSError):
            temporary.unlink(missing_ok=True)
        raise
