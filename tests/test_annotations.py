from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from epub2web.annotations import (
    AnnotationError,
    MergeReport,
    annotation_id,
    dumps_document,
    load_document,
    loads_document,
    make_document,
    merge_documents,
    parse_timestamp,
    validate_annotation,
    validate_document,
    write_document,
)

CONTENT_ID = "a" * 64
OTHER_CONTENT_ID = "b" * 64
SOURCE_SHA256 = "c" * 64


def book(**overrides):
    data = {
        "content_id": CONTENT_ID,
        "source_sha256": SOURCE_SHA256,
        "title": "A Tiny Book",
        "author": "Test Author",
        "isbn": "",
        "aliases": [],
    }
    data.update(overrides)
    return data


def annotation(**overrides):
    data = {
        "id": str(uuid.uuid4()),
        "type": "highlight",
        "created": "2026-11-04T10:00:00.000Z",
        "updated": "2026-11-04T10:00:00.000Z",
        "deleted": False,
        "note": "",
        "quote": "Hello world.",
        "style": {"color": "yellow"},
        "anchor": {
            "page_key": "f5d698c04cb99ab4",
            "spine_href": "OEBPS/ch1.xhtml",
            "spine_index": 0,
            "cfi": "epubcfi(/6/4/2/1:0,/6/4/2/1:12)",
            "start": {"dom_path": "/p[1]/text()[1]", "offset": 0, "char": 0},
            "end": {"dom_path": "/p[1]/text()[1]", "offset": 12, "char": 12},
            "prefix": "",
            "suffix": "",
            "progression": 0.1,
        },
    }
    data.update(overrides)
    return data


def document(*annotations, book_data=None):
    return {
        "schema": "epub2web.annotations",
        "version": 1,
        "book": book_data or book(),
        "annotations": list(annotations),
    }


def test_valid_document_round_trips_and_normalizes() -> None:
    record = annotation(created="2026-11-04T12:00:00+02:00")
    parsed = validate_document(document(record))
    assert parsed["annotations"][0]["created"] == "2026-11-04T10:00:00.000Z"
    assert parsed["book"]["content_id"] == CONTENT_ID

    restored = loads_document(dumps_document(parsed))
    assert restored == parsed


def test_naive_timestamps_are_utc_and_date_only_is_rejected() -> None:
    assert parse_timestamp("2026-11-04T10:00:00").isoformat() == "2026-11-04T10:00:00+00:00"
    assert (
        parse_timestamp("2026-11-04T10:00:00.123456+02:00").isoformat()
        == "2026-11-04T08:00:00.123456+00:00"
    )
    with pytest.raises(AnnotationError):
        parse_timestamp("2026-11-04")


def test_imported_ids_are_deterministic() -> None:
    first = annotation_id(CONTENT_ID, "calibre", "2f0c")
    second = annotation_id(CONTENT_ID, "calibre", "2f0c")
    assert first == second
    assert uuid.UUID(first)
    assert annotation_id(OTHER_CONTENT_ID, "calibre", "2f0c") != first


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {"schema": "other", "version": 1, "book": book(), "annotations": []},
        {"schema": "epub2web.annotations", "version": 2, "book": book(), "annotations": []},
        {"schema": "epub2web.annotations", "version": 1.0, "book": book(), "annotations": []},
        {"schema": "epub2web.annotations", "version": 1, "book": {}, "annotations": []},
        {
            "schema": "epub2web.annotations",
            "version": 1,
            "book": book(content_id="not-a-hash"),
            "annotations": [],
        },
        {
            "schema": "epub2web.annotations",
            "version": 1,
            "book": book(),
            "annotations": "nope",
        },
    ],
)
def test_document_shape_is_rejected(payload) -> None:
    with pytest.raises(AnnotationError):
        validate_document(payload)


@pytest.mark.parametrize(
    "record",
    [
        annotation(id="not-a-uuid"),
        annotation(type="note"),
        annotation(created=""),
        annotation(updated="2026-11-04"),
        annotation(deleted="no"),
        annotation(note=42),
        annotation(quote=42),
        annotation(style=[]),
        annotation(style={"color": ""}),
        annotation(style={"color": "orange"}),
        annotation(anchor=[]),
        annotation(anchor={"progression": 2}),
        annotation(anchor={"unknown": True}),
        annotation(anchor={"start": {"offset": -1}}),
        annotation(origin={"app": ""}),
        annotation(origin={"app": "calibre", "unknown": True}),
    ],
)
def test_malformed_annotation_is_rejected(record) -> None:
    with pytest.raises(AnnotationError):
        validate_annotation(record)


def test_duplicate_ids_and_origins_are_rejected() -> None:
    shared = str(uuid.uuid4())
    with pytest.raises(AnnotationError, match="duplicate annotation id"):
        validate_document(
            document(
                annotation(id=shared),
                annotation(id=shared),
            )
        )
    with pytest.raises(AnnotationError, match="duplicate annotation origin"):
        validate_document(
            document(
                annotation(origin={"app": "calibre", "id": "one"}),
                annotation(origin={"app": "calibre", "id": "one"}),
            )
        )


def test_merge_newer_record_wins() -> None:
    older = annotation(updated="2026-11-04T10:00:00.000Z")
    newer = annotation(
        id=older["id"],
        updated="2026-11-04T11:00:00.000Z",
        note="A newer note.",
    )
    merged, report = merge_documents(document(older), document(newer))

    assert report == MergeReport(added=0, updated=1, unchanged=0, ignored=0)
    assert merged["annotations"][0]["note"] == "A newer note."
    assert merged["annotations"][0]["updated"] == "2026-11-04T11:00:00.000Z"


def test_merge_older_record_is_ignored() -> None:
    newer = annotation(updated="2026-11-04T11:00:00.000Z", note="Keep me.")
    older = annotation(id=newer["id"], updated="2026-11-04T10:00:00.000Z", note="Stale.")
    merged, report = merge_documents(document(newer), document(older))

    assert report.ignored == 1
    assert merged["annotations"][0]["note"] == "Keep me."


def test_merge_equal_timestamp_prefers_a_resolved_anchor() -> None:
    unresolved = annotation(anchor={}, quote="")
    resolved = annotation(
        id=unresolved["id"],
        updated=unresolved["updated"],
        anchor={"page_key": "f5d698c04cb99ab4", "progression": 0.2},
        quote="Hello world.",
    )
    merged, report = merge_documents(document(unresolved), document(resolved))

    assert report.updated == 1
    assert merged["annotations"][0]["anchor"]["page_key"] == "f5d698c04cb99ab4"


def test_newer_tombstone_wins_and_old_active_record_cannot_resurrect_it() -> None:
    active = annotation(updated="2026-11-04T10:00:00.000Z")
    removed = annotation(
        id=active["id"],
        updated="2026-11-04T11:00:00.000Z",
        deleted=True,
        quote="",
    )
    merged, report = merge_documents(document(active), document(removed))

    assert report.updated == 1
    assert merged["annotations"][0]["deleted"] is True

    resurrected, report = merge_documents(merged, document(active))
    assert report.ignored == 1
    assert resurrected["annotations"][0]["deleted"] is True


def test_merge_matches_origin_and_keeps_the_local_id() -> None:
    local = annotation(
        id=str(uuid.uuid4()),
        origin={"app": "calibre", "id": "calibre-uuid"},
        updated="2026-11-04T10:00:00.000Z",
        note="Old note.",
    )
    incoming = annotation(
        id=str(uuid.uuid4()),
        origin={"app": "calibre", "id": "calibre-uuid"},
        updated="2026-11-04T11:00:00.000Z",
        note="Imported note.",
    )
    merged, report = merge_documents(document(local), document(incoming))

    assert report.updated == 1
    assert merged["annotations"][0]["id"] == local["id"]
    assert merged["annotations"][0]["note"] == "Imported note."


def test_merge_adds_new_records_and_refuses_other_books() -> None:
    first = annotation(quote="First.")
    second = annotation(quote="Second.")
    merged, report = merge_documents(document(first), document(second))
    assert report.added == 1
    assert [item["quote"] for item in merged["annotations"]] == ["First.", "Second."]

    with pytest.raises(AnnotationError, match="different books"):
        merge_documents(
            document(first),
            document(second, book_data=book(content_id=OTHER_CONTENT_ID)),
        )


def test_document_files_are_written_atomically_and_read_back(tmp_path: Path) -> None:
    target = tmp_path / "private" / "annotations.json"
    source = make_document(book(), [annotation(note="Private note.")])
    write_document(target, source)

    assert load_document(target) == source
    assert not (target.parent / f".{target.name}.tmp").exists()

    target.write_text("{not json", encoding="utf-8")
    with pytest.raises(AnnotationError, match="not valid JSON"):
        load_document(target)


def test_json_input_rejects_garbage() -> None:
    with pytest.raises(AnnotationError):
        loads_document("null")
    with pytest.raises(AnnotationError):
        loads_document(json.dumps(["not", "a", "document"]))
