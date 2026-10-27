from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest
from epub2web.controller import (
    BuildController,
    BuildEvent,
    BuildState,
    default_output_dir,
    worker_command,
)
from epub2web.gui import main as gui_main
from epub2web.worker import main as worker_main

CH1 = "OEBPS/ch1.xhtml"


def test_tk_app_imports_when_tk_is_available():
    try:
        import tkinter  # noqa: F401
    except ImportError as exc:
        pytest.skip(f"Tkinter is not available: {exc}")
    import epub2web.tk_app  # noqa: F401


def test_gui_worker_flag_routes_to_cli(tiny_epub, tmp_path: Path):
    site = tmp_path / "site"
    code = gui_main(
        [
            "--worker",
            str(tiny_epub),
            "-o",
            str(site),
            "--log-dir",
            str(tmp_path / "logs"),
            "--report-dir",
            str(tmp_path / "reports"),
        ]
    )
    assert code == 0
    assert (site / "index.html").exists()
    assert (site / "search-index.json").exists()


def test_worker_main_builds_site(tiny_epub, tmp_path: Path):
    site = tmp_path / "site"
    code = worker_main(
        [
            str(tiny_epub),
            "-o",
            str(site),
            "--log-dir",
            str(tmp_path / "logs"),
            "--report-dir",
            str(tmp_path / "reports"),
        ]
    )
    assert code == 0
    assert (site / "index.html").exists()


def test_worker_command_uses_module_when_not_frozen(monkeypatch, tmp_path: Path):
    monkeypatch.delattr(sys, "frozen", raising=False)
    command = worker_command(
        "book.epub",
        "book-site",
        serve=False,
        log_dir=tmp_path / "logs",
        report_dir=tmp_path / "reports",
    )
    assert command[0] == sys.executable
    assert command[1:3] == ["-m", "epub2web.worker"]
    assert "--serve" not in command
    assert "--log-dir" in command
    assert "--report-dir" in command


def test_worker_command_uses_worker_flag_when_frozen(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    command = worker_command(
        "book.epub",
        "book-site",
        serve=True,
        port=0,
        open_browser=False,
        log_dir=tmp_path / "logs",
        report_dir=tmp_path / "reports",
    )
    assert command[0] == sys.executable
    assert command[1] == "--worker"
    assert "--serve" in command
    assert command[command.index("--port") + 1] == "0"
    assert "--no-browser" in command


def test_default_output_dir_uses_documents(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    (tmp_path / "Documents").mkdir()
    assert default_output_dir("My Book.epub") == (
        tmp_path / "Documents" / "epub2web" / "My Book-site"
    )


def test_default_output_dir_falls_back_to_home(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert default_output_dir("My Book.epub") == (tmp_path / "epub2web" / "My Book-site")


def test_default_output_dir_can_use_metadata_title(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert default_output_dir("book.epub", title="Vol. 1") == (
        tmp_path / "epub2web" / "Vol. 1-site"
    )


def test_default_output_dir_sanitizes_unsafe_names(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert default_output_dir("A<B>C.epub") == (tmp_path / "epub2web" / "A-B-C-site")
    assert default_output_dir("设计.epub") == (tmp_path / "epub2web" / "设计-site")


def test_controller_builds_and_reports_success(tiny_epub, tmp_path: Path):
    events: list[BuildEvent] = []
    site = tmp_path / "site"
    controller = BuildController(
        events.append,
        serve=False,
        log_dir=tmp_path / "logs",
        report_dir=tmp_path / "reports",
    )
    controller.start(tiny_epub, site)

    assert controller.wait(60) == 0
    assert controller.state is BuildState.SUCCEEDED
    assert (site / "index.html").exists()

    success = [event for event in events if event.kind == "success"]
    assert success
    assert success[0].data["site"].endswith("index.html")
    assert success[0].data["verify"] is True
    assert success[0].data["links"] is True


def test_controller_reports_failure_and_support_report(epub_factory, tmp_path: Path):
    bad = epub_factory(
        "bad.epub",
        replacements={CH1: [(b'src="images/cover.png"', b'src="images/missing.png"')]},
    )
    events: list[BuildEvent] = []
    controller = BuildController(
        events.append,
        serve=False,
        log_dir=tmp_path / "logs",
        report_dir=tmp_path / "reports",
    )
    controller.start(bad, tmp_path / "site")

    assert controller.wait(60) == 2
    assert controller.state is BuildState.FAILED
    failure = [event for event in events if event.kind == "failure"]
    assert failure
    assert "could not process image references" in failure[0].message
    report = failure[0].data["report"]
    assert report
    assert Path(report).exists()
    assert controller.report_path == Path(report)


def test_controller_reports_cli_usage_error(tiny_epub, tmp_path: Path):
    site = tmp_path / "site"
    site.mkdir()
    (site / "keep.txt").write_text("not an epub2web site", encoding="utf-8")
    events: list[BuildEvent] = []
    controller = BuildController(
        events.append,
        serve=False,
        log_dir=tmp_path / "logs",
        report_dir=tmp_path / "reports",
    )
    controller.start(tiny_epub, site)

    assert controller.wait(60) == 2
    failure = [event for event in events if event.kind == "failure"]
    assert failure
    assert "output already exists" in failure[0].message
    assert (site / "keep.txt").read_text(encoding="utf-8") == "not an epub2web site"


def test_controller_reports_link_gate_failure(epub_factory, tmp_path: Path):
    bad = epub_factory(
        "bad-link.epub",
        replacements={
            CH1: [(b"</body>", b'<p><a href="missing.xhtml">broken link</a></p></body>')]
        },
    )
    events: list[BuildEvent] = []
    controller = BuildController(
        events.append,
        serve=False,
        log_dir=tmp_path / "logs",
        report_dir=tmp_path / "reports",
    )
    controller.start(bad, tmp_path / "site")

    assert controller.wait(60) == 1
    failure = [event for event in events if event.kind == "failure"]
    assert failure
    assert failure[0].message == "Build rejected by the internal-link gate."
    assert failure[0].data["links"] is False


def test_controller_starts_and_stops_preview(tiny_epub, tmp_path: Path):
    events: list[BuildEvent] = []
    controller = BuildController(
        events.append,
        serve=True,
        port=0,
        open_browser=False,
        log_dir=tmp_path / "logs",
        report_dir=tmp_path / "reports",
    )
    try:
        controller.start(tiny_epub, tmp_path / "site")
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline and not controller.preview_url:
            if not controller.is_running:
                break
            time.sleep(0.05)
        assert controller.preview_url
        assert controller.preview_url.startswith("http://127.0.0.1:")
        assert any(event.kind == "preview" for event in events)
    finally:
        controller.stop()

    assert not controller.is_running
    assert controller.state is BuildState.STOPPED
    assert any(event.kind == "stopped" for event in events)
