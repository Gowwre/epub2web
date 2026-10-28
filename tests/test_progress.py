import io
import json
from pathlib import Path

from epub2web.generic import GenericExtractor
from epub2web.links import check_site_links
from epub2web.progress import PROGRESS_PREFIX, ProgressPrinter
from epub2web.render import render_site
from epub2web.verify import verify_site


def test_progress_printer_is_monotonic_and_complete():
    stream = io.StringIO()
    printer = ProgressPrinter(stream=stream)
    printer("read", "Reading EPUB", 0, 2)
    printer("read", "Reading EPUB", 1, 2)
    printer("read", "Reading EPUB", 2, 2)
    printer("extract-images", "Optimizing images", 0, 2)
    printer("extract-images", "Optimizing images", 2, 2)
    printer("publish", "Publishing site", 1, 1)

    events = [
        json.loads(line.removeprefix(PROGRESS_PREFIX)) for line in stream.getvalue().splitlines()
    ]
    assert [event["phase"] for event in events] == [
        "read",
        "read",
        "read",
        "extract-images",
        "extract-images",
        "publish",
    ]
    percents = [event["percent"] for event in events]
    assert percents == sorted(percents)
    assert events[-1]["percent"] == 1.0
    assert all(event["current"] <= event["total"] for event in events)


def test_core_reports_all_working_phases(tiny_epub, tmp_path: Path):
    events: list[tuple[str, str, int, int]] = []
    content = tmp_path / "content"
    images = tmp_path / "images"
    site = tmp_path / "site"

    def progress(phase: str, label: str, current: int, total: int) -> None:
        events.append((phase, label, current, total))

    GenericExtractor(tiny_epub, content, images, progress=progress).run()
    render_site(content, site, progress=progress)
    verify_site(content, site, verbose=False, progress=progress)
    check_site_links(site, progress=progress)

    phases = {event[0] for event in events}
    assert {
        "read",
        "extract-images",
        "extract-pages",
        "extract-write",
        "render-pages",
        "render-assets",
        "verify",
        "links",
    } <= phases
    assert any(event[0] == "extract-images" and event[2] > 0 for event in events)
    assert any(event[0] == "verify" and event[2] == event[3] for event in events)
