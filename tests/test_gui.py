from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from epub2web import __version__, updates
from epub2web.controller import (
    BuildController,
    BuildEvent,
    BuildState,
    default_output_dir,
    worker_command,
)
from epub2web.gui import main as gui_main
from epub2web.progress import EVENT_PREFIX
from epub2web.updates import ReleaseInfo
from epub2web.worker import main as worker_main

CH1 = "OEBPS/ch1.xhtml"


def _import_tk_app():
    try:
        import tkinter  # noqa: F401
    except ImportError as exc:
        pytest.skip(f"Tkinter is not available: {exc}")
    from epub2web import tk_app

    return tk_app


def _make_drop_app(tk_app):
    """Build a bare app object for drop-handler tests without a display."""
    import tkinter

    selected: list[Path] = []
    messages: list[str] = []
    app = object.__new__(tk_app.Epub2WebApp)
    app.root = SimpleNamespace(tk=tkinter.Tcl())
    app._source_card = None
    app._drop_highlighted = False
    app._building = False
    app._preview_running = False
    app._select_epub = selected.append
    app._set_status = lambda text, _tone="muted": messages.append(text)
    app._append_log = lambda *_args, **_kwargs: None
    return app, selected, messages


def _drop_payload(*paths: Path) -> str:
    """Build the braced Tcl list that TkDND supplies for dropped files."""
    return " ".join(f"{{{path}}}" for path in paths)


def test_tk_app_imports_when_tk_is_available():
    assert _import_tk_app()


def test_tk_app_displays_version():
    tk_app = _import_tk_app()

    assert tk_app.window_title() == f"epub2web {__version__}"
    expected_label = f"v{__version__}"
    assert expected_label == tk_app.VERSION_LABEL


def test_tk_app_header_links_open_project_pages(monkeypatch):
    tk_app = _import_tk_app()
    opened = []
    monkeypatch.setattr(tk_app.webbrowser, "open", lambda url: opened.append(url) or True)

    app = object.__new__(tk_app.Epub2WebApp)
    app._open_github()
    app._open_website()

    assert opened == [tk_app.GITHUB_URL, tk_app.WEBSITE_URL]
    assert tk_app.GITHUB_URL == "https://github.com/Gowwre/epub2web"
    assert tk_app.WEBSITE_URL == "https://gowwre.github.io/epub2web/"


def test_tk_app_header_links_fall_back_to_visible_address(monkeypatch):
    tk_app = _import_tk_app()
    monkeypatch.setattr(tk_app.webbrowser, "open", lambda _url: False)
    messages = []
    app = object.__new__(tk_app.Epub2WebApp)
    app._show_info = lambda title, message, detail="", detail_label="DETAILS": messages.append(
        (title, detail)
    )

    app._open_github()
    app._open_website()

    assert messages == [
        ("Open GitHub", tk_app.GITHUB_URL),
        ("Open website", tk_app.WEBSITE_URL),
    ]


def test_tk_app_update_check_can_be_disabled(monkeypatch):
    tk_app = _import_tk_app()
    app = object.__new__(tk_app.Epub2WebApp)
    monkeypatch.setenv("EPUB2WEB_NO_UPDATE_CHECK", "1")
    monkeypatch.setattr(
        tk_app.threading,
        "Thread",
        lambda **_kwargs: pytest.fail("update check should be disabled"),
    )

    app._check_for_updates()
    app._check_for_updates(manual=True)


def _make_update_app(tk_app):
    """Build a bare app object for update-check tests without a display."""
    app = object.__new__(tk_app.Epub2WebApp)
    app.update_info = None
    app.update_button = SimpleNamespace(pack=lambda **_kwargs: None)
    app.update_check_button = SimpleNamespace(configure=lambda **_kwargs: None)
    app._updates_enabled = True
    app._update_checking = False
    app._update_check_manual = False
    app._next_update_check = 0.0
    return app


def test_tk_app_reschedules_update_check_after_completion(monkeypatch):
    tk_app = _import_tk_app()
    app = _make_update_app(tk_app)
    app._update_checking = True
    monkeypatch.setattr(tk_app.time, "monotonic", lambda: 1000.0)

    app._apply_update(None)

    assert app._update_checking is False
    assert app._next_update_check == 1000.0 + tk_app.UPDATE_CHECK_INTERVAL


def test_tk_app_update_check_is_due_only_when_idle():
    tk_app = _import_tk_app()
    app = _make_update_app(tk_app)
    app._next_update_check = 10.0

    assert app._update_check_due(9.9) is False
    assert app._update_check_due(10.0) is True

    app._update_checking = True
    assert app._update_check_due(20.0) is False

    app._update_checking = False
    app._updates_enabled = False
    assert app._update_check_due(20.0) is False


def test_tk_app_update_check_button_shows_busy_state():
    tk_app = _import_tk_app()
    app = _make_update_app(tk_app)
    calls = []
    app.update_check_button = SimpleNamespace(configure=lambda **kwargs: calls.append(kwargs))

    app._set_update_check_busy(True)
    app._set_update_check_busy(False)

    assert calls == [
        {"text": "Checking…", "state": "disabled"},
        {"text": tk_app.UPDATE_CHECK_LABEL, "state": "normal"},
    ]


def test_tk_app_update_check_reuses_inflight_check(monkeypatch):
    tk_app = _import_tk_app()
    app = _make_update_app(tk_app)
    app._update_checking = True
    monkeypatch.setattr(
        tk_app.threading,
        "Thread",
        lambda **_kwargs: pytest.fail("should reuse the in-flight check"),
    )

    app._check_for_updates(manual=True)

    assert app._update_check_manual is True


def test_tk_app_update_check_starts_background_thread(monkeypatch):
    tk_app = _import_tk_app()
    app = _make_update_app(tk_app)
    started = []

    class FakeThread:
        def __init__(self, **kwargs):
            started.append(kwargs)

        def start(self):
            started[-1]["started"] = True

    monkeypatch.setattr(tk_app.threading, "Thread", FakeThread)

    app._check_for_updates(manual=True)

    assert app._update_checking is True
    assert app._update_check_manual is True
    assert started == [
        {
            "target": app._fetch_update,
            "daemon": True,
            "name": "epub2web-update",
            "started": True,
        }
    ]


def test_tk_app_manual_check_reports_when_current():
    tk_app = _import_tk_app()
    app = _make_update_app(tk_app)
    messages = []
    app._show_info = lambda title, message, *_args: messages.append((title, message))
    app._show_error = lambda *_args, **_kwargs: pytest.fail("unexpected error")
    app._update_check_manual = True

    app._apply_update(ReleaseInfo("0.0.1", ""))

    assert messages == [
        (
            "No updates available",
            f"You are running epub2web {__version__}, the latest version.",
        )
    ]


def test_tk_app_manual_check_reports_failure():
    tk_app = _import_tk_app()
    app = _make_update_app(tk_app)
    errors = []
    app._show_error = lambda title, message, *_args: errors.append((title, message))
    app._show_info = lambda *_args, **_kwargs: pytest.fail("unexpected info")
    app._update_check_manual = True

    app._apply_update(None)

    assert errors[0][0] == "Could not check for updates"
    assert "could not be reached" in errors[0][1]


def test_tk_app_automatic_check_failure_is_silent():
    tk_app = _import_tk_app()
    app = _make_update_app(tk_app)
    app._show_error = lambda *_args, **_kwargs: pytest.fail("automatic failures are silent")
    app._show_info = lambda *_args, **_kwargs: pytest.fail("automatic failures are silent")

    app._apply_update(None)


def test_tk_app_manual_check_opens_available_update():
    tk_app = _import_tk_app()
    app = _make_update_app(tk_app)
    packed = []
    app.update_button = SimpleNamespace(pack=lambda **kwargs: packed.append(kwargs))
    app._show_update_dialog = lambda: packed.append("dialog")
    app._update_check_manual = True
    release = ReleaseInfo("999.0.0", "notes")

    app._apply_update(release)

    assert app.update_info is release
    assert packed == [{"side": "right", "padx": (0, 8)}, "dialog"]


def test_tk_app_shows_update_button_only_for_newer_release():
    tk_app = _import_tk_app()
    app = object.__new__(tk_app.Epub2WebApp)
    app.update_info = None
    packed = []
    app.update_button = SimpleNamespace(pack=lambda **kwargs: packed.append(kwargs))

    app._apply_update(None)
    app._apply_update(ReleaseInfo("0.0.1", ""))
    assert packed == []

    update = ReleaseInfo("999.0.0", "notes")
    app._apply_update(update)
    app._apply_update(update)

    assert app.update_info is update
    assert packed == [{"side": "right", "padx": (0, 8)}]


def test_tk_app_assets_exist():
    tk_app = _import_tk_app()
    theme = Path(tk_app.__file__).resolve().parent / "theme"
    for name in ("gui-icon.png", "gui-github.png", "gui-github-2x.png"):
        assert (theme / name).is_file(), name


def test_tk_app_enables_dnd_when_the_extension_loads(monkeypatch):
    tk_app = _import_tk_app()
    loaded = []

    class FakeTkinterDnD:
        @staticmethod
        def require(root):
            loaded.append(root)

    monkeypatch.setattr(tk_app, "TkinterDnD", FakeTkinterDnD)
    root = object()

    assert tk_app._enable_dnd(root) is True
    assert loaded == [root]


def test_tk_app_falls_back_when_dnd_cannot_load(monkeypatch):
    tk_app = _import_tk_app()

    class BrokenTkinterDnD:
        @staticmethod
        def require(_root):
            raise RuntimeError("no tkdnd binary")

    monkeypatch.setattr(tk_app, "TkinterDnD", BrokenTkinterDnD)
    assert tk_app._enable_dnd(object()) is False
    assert "could not load" in tk_app._dnd_unavailable_message()

    monkeypatch.setattr(tk_app, "TkinterDnD", None)
    assert tk_app._enable_dnd(object()) is False
    assert "tkinterdnd2 is not installed" in tk_app._dnd_unavailable_message()


def test_tk_app_parses_tkdnd_file_list(tmp_path: Path):
    tk_app = _import_tk_app()
    app, _selected, _messages = _make_drop_app(tk_app)
    first = tmp_path / "My Book.epub"
    second = tmp_path / "Other Book.epub"
    payload = _drop_payload(first, second)

    assert app._drop_paths(payload) == [first, second]
    assert app._drop_paths([str(first), str(second)]) == [first, second]
    assert app._drop_paths("") == []


def test_tk_app_drop_selects_one_epub(tmp_path: Path):
    tk_app = _import_tk_app()
    app, selected, messages = _make_drop_app(tk_app)
    path = tmp_path / "BOOK.EPUB"
    path.write_bytes(b"")

    app._handle_drop(SimpleNamespace(data=_drop_payload(path)))

    assert selected == [path]
    assert messages == []


def test_tk_app_drop_rejects_multiple_files(tmp_path: Path):
    tk_app = _import_tk_app()
    app, selected, messages = _make_drop_app(tk_app)
    payload = _drop_payload(tmp_path / "one.epub", tmp_path / "two.epub")

    app._handle_drop(SimpleNamespace(data=payload))

    assert selected == []
    assert messages == ["Drop one EPUB at a time."]


def test_tk_app_drop_rejects_non_epub(tmp_path: Path):
    tk_app = _import_tk_app()
    app, selected, messages = _make_drop_app(tk_app)
    path = tmp_path / "notes.txt"
    path.write_text("not a book", encoding="utf-8")

    app._handle_drop(SimpleNamespace(data=_drop_payload(path)))

    assert selected == []
    assert messages == ["That file is not an EPUB. Drop a .epub file."]


def test_tk_app_drop_rejects_folders(tmp_path: Path):
    tk_app = _import_tk_app()
    app, selected, messages = _make_drop_app(tk_app)

    app._handle_drop(SimpleNamespace(data=_drop_payload(tmp_path)))

    assert selected == []
    assert messages == ["Drop an EPUB file, not a folder."]


def test_tk_app_drop_ignores_locked_app(tmp_path: Path):
    tk_app = _import_tk_app()
    app, selected, messages = _make_drop_app(tk_app)
    app._building = True
    path = tmp_path / "book.epub"
    path.write_bytes(b"")

    app._handle_drop(SimpleNamespace(data=_drop_payload(path)))

    assert selected == []
    assert messages == ["Stop the current preview before choosing another EPUB."]


def test_tk_app_drop_rejects_empty_payload():
    tk_app = _import_tk_app()
    app, selected, messages = _make_drop_app(tk_app)

    app._handle_drop(SimpleNamespace(data=""))

    assert selected == []
    assert messages == ["Drop one EPUB 2 or 3 file to select it."]


def test_tk_app_drop_highlight_tracks_drag_state():
    tk_app = _import_tk_app()
    app = object.__new__(tk_app.Epub2WebApp)
    calls = []
    app._source_card = SimpleNamespace(configure=lambda **kwargs: calls.append(kwargs))
    app._drop_highlighted = False

    app._set_drop_highlight(True)
    app._set_drop_highlight(True)
    app._set_drop_highlight(False)

    assert calls == [
        {"highlightbackground": tk_app.ACCENT, "highlightcolor": tk_app.ACCENT},
        {"highlightbackground": tk_app.RULE, "highlightcolor": tk_app.RULE},
    ]


def test_tk_app_registers_every_source_card_widget(monkeypatch):
    tk_app = _import_tk_app()

    class FakeWidget:
        def __init__(self, *children):
            self._children = list(children)
            self.registered = []
            self.bound = []

        def winfo_children(self):
            return self._children

        def drop_target_register(self, *types):
            self.registered.append(types)

        def dnd_bind(self, sequence, func):
            self.bound.append((sequence, func))

    child = FakeWidget()
    card = FakeWidget(child)
    app = object.__new__(tk_app.Epub2WebApp)
    app._dnd_enabled = True
    app._source_card = card

    app._register_drop_targets()

    for widget in (card, child):
        assert widget.registered == [(tk_app.DND_FILES,)]
        assert [sequence for sequence, _func in widget.bound] == [
            "<<Drop>>",
            "<<DropEnter>>",
            "<<DropLeave>>",
        ]


def test_tk_app_disabled_dnd_skips_registration(monkeypatch):
    tk_app = _import_tk_app()
    app = object.__new__(tk_app.Epub2WebApp)
    app._dnd_enabled = False
    app._source_card = SimpleNamespace(
        winfo_children=lambda: pytest.fail("should not inspect widgets"),
        drop_target_register=lambda *_args: pytest.fail("should not register"),
    )

    app._register_drop_targets()


def test_tk_app_select_epub_rejects_non_epub(tmp_path: Path):
    tk_app = _import_tk_app()
    path = tmp_path / "notes.txt"
    path.write_text("not a book", encoding="utf-8")
    errors = []
    app = object.__new__(tk_app.Epub2WebApp)
    app._building = False
    app._preview_running = False
    app._show_error = lambda *args: errors.append(args)

    assert app._select_epub(path) is False
    assert errors == [("Not an EPUB", "Choose a reflowable EPUB 2 or 3 file.", str(path))]


def test_tk_app_select_epub_resets_previous_state(tmp_path: Path, monkeypatch):
    tk_app = _import_tk_app()
    path = tmp_path / "My_Book.epub"
    path.write_bytes(b"")
    names = []
    shown_paths = []
    started = []
    app = object.__new__(tk_app.Epub2WebApp)
    app._building = False
    app._preview_running = False
    app.controller = object()
    app.preview_url = "http://127.0.0.1:8000/"
    app._book_title = "Old title"
    app._last_dir = tmp_path
    app._output_parent = None
    app.output = None
    app.output_var = SimpleNamespace(set=lambda _value: None)
    app.file_name_var = SimpleNamespace(set=names.append)
    app.file_path_var = SimpleNamespace(set=shown_paths.append)
    app._reset_log = lambda: None
    app._append_log = lambda *_args, **_kwargs: None
    app._set_status = lambda *_args, **_kwargs: None
    app._set_log_hint = lambda *_args, **_kwargs: None
    app._refresh_controls = lambda: None
    monkeypatch.setattr(
        tk_app.threading,
        "Thread",
        lambda **kwargs: SimpleNamespace(start=lambda: started.append(kwargs)),
    )

    assert app._select_epub(path) is True

    assert app.epub == path
    assert app._last_dir == path.parent
    assert app.controller is None
    assert app.preview_url is None
    assert app._book_title == ""
    assert names == ["My Book"]
    assert shown_paths == [tk_app.Epub2WebApp._display_path(path)]
    assert len(started) == 1
    assert started[0]["args"] == (path,)


def test_gui_self_test_checks_tk():
    try:
        import tkinter  # noqa: F401
    except ImportError as exc:
        pytest.skip(f"Tkinter is not available: {exc}")
    assert gui_main(["--self-test"]) == 0


def test_gui_self_test_reports_missing_dnd(monkeypatch, capsys):
    tk_app = _import_tk_app()
    monkeypatch.setattr(tk_app, "DND_FILES", None)

    assert gui_main(["--self-test"]) == 2
    assert "tkinterdnd2" in capsys.readouterr().err


def test_gui_self_test_reports_missing_certificate_bundle(monkeypatch, capsys):
    _import_tk_app()
    monkeypatch.setattr(updates, "_ssl_context", lambda: None)

    assert gui_main(["--self-test"]) == 2
    assert "certificate bundle" in capsys.readouterr().err


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
    assert "--progress" in command
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


def test_default_output_dir_can_use_custom_parent(tmp_path: Path):
    parent = tmp_path / "library"
    assert default_output_dir("My Book.epub", parent=parent) == (parent / "My Book-site")


def test_tk_app_output_picker_uses_selected_parent(monkeypatch, tmp_path: Path):
    tk_app = _import_tk_app()
    chosen = tmp_path / "library"
    chosen.mkdir()
    initial = tmp_path / "old"
    initial.mkdir()
    calls = []
    monkeypatch.setattr(
        tk_app.filedialog,
        "askdirectory",
        lambda **kwargs: calls.append(kwargs) or str(chosen),
    )
    shown = []
    app = object.__new__(tk_app.Epub2WebApp)
    app.root = None
    app.epub = tmp_path / "My Book.epub"
    app._building = False
    app._preview_running = False
    app._last_dir = tmp_path
    app._output_parent = None
    app._book_title = ""
    app.output = initial / "My Book-site"
    app.output_var = SimpleNamespace(set=shown.append)
    app._set_status = lambda *_args, **_kwargs: None
    app._append_log = lambda *_args, **_kwargs: None

    app._choose_output()

    assert app._output_parent == chosen
    assert app.output == chosen / "My Book-site"
    assert shown == [tk_app.Epub2WebApp._display_path(chosen / "My Book-site")]
    assert calls == [
        {
            "parent": None,
            "title": "Choose where to save the generated site",
            "initialdir": str(initial),
            "mustexist": True,
        }
    ]


def test_tk_app_output_picker_keeps_metadata_title(monkeypatch, tmp_path: Path):
    tk_app = _import_tk_app()
    chosen = tmp_path / "library"
    chosen.mkdir()
    monkeypatch.setattr(tk_app.filedialog, "askdirectory", lambda **_kwargs: str(chosen))
    app = object.__new__(tk_app.Epub2WebApp)
    app.root = None
    app.epub = tmp_path / "book.epub"
    app._building = False
    app._preview_running = False
    app._last_dir = tmp_path
    app._output_parent = None
    app._book_title = "Vol. 1"
    app.output = tmp_path / "epub2web" / "Vol. 1-site"
    app.output_var = SimpleNamespace(set=lambda _value: None)
    app._set_status = lambda *_args, **_kwargs: None
    app._append_log = lambda *_args, **_kwargs: None

    app._choose_output()

    assert app.output == chosen / "Vol. 1-site"


def test_tk_app_output_picker_cancel_keeps_output(monkeypatch, tmp_path: Path):
    tk_app = _import_tk_app()
    monkeypatch.setattr(tk_app.filedialog, "askdirectory", lambda **_kwargs: "")
    app = object.__new__(tk_app.Epub2WebApp)
    app.root = None
    app.epub = tmp_path / "book.epub"
    app._building = False
    app._preview_running = False
    app._last_dir = tmp_path
    app._output_parent = None
    app._book_title = ""
    app.output = tmp_path / "site"
    app.output_var = SimpleNamespace(set=lambda _value: pytest.fail("output should not change"))
    app._set_status = lambda *_args, **_kwargs: None
    app._append_log = lambda *_args, **_kwargs: None

    app._choose_output()

    assert app.output == tmp_path / "site"
    assert app._output_parent is None


def test_tk_app_output_picker_ignores_locked_build(monkeypatch, tmp_path: Path):
    tk_app = _import_tk_app()
    monkeypatch.setattr(
        tk_app.filedialog,
        "askdirectory",
        lambda **_kwargs: pytest.fail("folder picker should not open"),
    )
    app = object.__new__(tk_app.Epub2WebApp)
    app.epub = tmp_path / "book.epub"
    app._building = True
    app._preview_running = False
    app.output = tmp_path / "site"

    app._choose_output()

    assert app.output == tmp_path / "site"


def test_tk_app_metadata_keeps_custom_output_parent(tmp_path: Path):
    tk_app = _import_tk_app()
    parent = tmp_path / "library"
    app = object.__new__(tk_app.Epub2WebApp)
    app.epub = tmp_path / "book.epub"
    app.controller = None
    app._output_parent = parent
    app.output = parent / "book-site"
    app.output_var = SimpleNamespace(set=lambda _value: None)
    app.file_name_var = SimpleNamespace(set=lambda _value: None)
    app._set_status = lambda *_args, **_kwargs: None

    app._apply_book_info(app.epub, {"title": "Vol. 1"})

    assert app.output == parent / "Vol. 1-site"


def test_tk_app_display_path_handles_home(tmp_path: Path, monkeypatch):
    tk_app = _import_tk_app()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert tk_app.Epub2WebApp._display_path(tmp_path / "book-site") == (f"~{os.sep}book-site")


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

    progress = [event for event in events if event.kind == "progress"]
    assert progress
    assert progress[0].data["phase"] == "read"
    assert progress[-1].data["percent"] == 1.0
    percents = [event.data["percent"] for event in progress]
    assert percents == sorted(percents)

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


def test_controller_accepts_structured_preview_event():
    events: list[BuildEvent] = []
    controller = BuildController(events.append)

    controller._handle_line(
        EVENT_PREFIX + json.dumps({"kind": "preview", "url": "http://127.0.0.1:8123/"})
    )

    assert controller.preview_url == "http://127.0.0.1:8123/"
    assert controller.state is BuildState.SUCCEEDED
    assert [event.kind for event in events] == ["preview", "success"]
    assert events[0].data["url"] == "http://127.0.0.1:8123/"


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
