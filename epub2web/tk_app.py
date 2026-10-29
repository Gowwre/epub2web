"""Tkinter desktop interface for epub2web.

The view only talks to :class:`epub2web.controller.BuildController`. All
toolkit-specific code lives here so another toolkit can replace this module
without touching the worker or process lifecycle.
"""

from __future__ import annotations

import contextlib
import os
import queue
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
import webbrowser
from pathlib import Path
from tkinter import filedialog, ttk

from . import __version__
from .controller import (
    BuildController,
    BuildEvent,
    default_log_dir,
    default_output_dir,
    default_report_dir,
)
from .updates import (
    DOWNLOAD_URL,
    GITHUB_URL,
    ReleaseInfo,
    fetch_latest_release,
    is_newer,
)

APP_TITLE = "epub2web"
WEBSITE_URL = "https://gowwre.github.io/epub2web/"
LOG_LINE_LIMIT = 2000

# The desktop palette mirrors the reader theme in theme/assets/styles.css.
BG = "#f5f0e6"
SURFACE = "#fbf8f1"
SURFACE_ALT = "#eee7da"
INK = "#1f1b16"
INK_2 = "#4c4439"
MUTED = "#6e6354"
RULE = "#ded6c8"
RULE_STRONG = "#c9bfae"
ACCENT = "#b23a1b"
ACCENT_2 = "#8d2c12"
ACCENT_HOVER = "#c64a28"
ACCENT_SOFT = "#f5e1d7"
ACCENT_INK = "#fff8ef"
SUCCESS = "#2f6b4f"
DANGER = "#a52f22"
LOG_BG = "#191714"
LOG_FG = "#e8e0d2"
LOG_MUTED = "#9a9184"
LOG_ERROR = "#ff9e8d"
LOG_SUCCESS = "#8fd6a8"
LOG_ACCENT = "#f2b38a"


def _font_candidates() -> tuple[list[str], list[str], list[str]]:
    if sys.platform == "win32":
        ui = ["Segoe UI", "Inter", "Noto Sans"]
        display = ["Georgia", "Cambria", "Noto Serif", "DejaVu Serif"]
        mono = ["Cascadia Mono", "Consolas", "Courier New"]
    elif sys.platform == "darwin":
        ui = ["SF Pro Display", "Helvetica Neue", "Inter", "Noto Sans"]
        display = ["Georgia", "Iowan Old Style", "Palatino", "Noto Serif"]
        mono = ["SF Mono", "Menlo", "Monaco"]
    else:
        ui = ["Inter", "Noto Sans", "Cantarell", "DejaVu Sans"]
        display = ["Fraunces", "Literata", "Noto Serif", "DejaVu Serif"]
        mono = ["JetBrains Mono", "Cascadia Mono", "Noto Sans Mono", "DejaVu Sans Mono"]
    return ui, display, mono


def _pick_font(root: tk.Misc, candidates: list[str]) -> str:
    available = set(tkfont.families(root))
    for name in candidates:
        if name in available:
            return name
    return tkfont.nametofont("TkDefaultFont").actual("family")


class Epub2WebApp:
    """Main application window. All Tk calls stay on the Tk main thread."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.minsize(720, 600)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._center_window()
        self._set_icon()

        self.epub: Path | None = None
        self.output: Path | None = None
        self.preview_url: str | None = None
        self.controller: BuildController | None = None
        self.events: queue.Queue[BuildEvent] = queue.Queue()
        self.book_info_queue: queue.Queue[tuple[Path, dict]] = queue.Queue()
        self.update_queue: queue.Queue[ReleaseInfo | None] = queue.Queue()
        self.update_info: ReleaseInfo | None = None
        self._building = False
        self._preview_running = False
        self._auto_open_preview = False
        self._progress_determinate = False
        self._last_progress_key: tuple[str, int] | None = None
        self._poll_id: str | None = None
        self._last_dir = self._default_open_dir()
        self._log_scroll_first = 0.0
        self._log_scroll_last = 1.0
        self._log_thumb_top = 0.0
        self._log_thumb_bottom = 0.0
        self._log_drag_start = 0
        self._log_drag_first = 0.0
        self._log_dragging = False

        self._configure_fonts()
        self._configure_styles()
        self._build_ui()
        self._refresh_controls()
        self._set_status("Choose an EPUB to begin.", "muted")
        self._set_log_hint("Fidelity and link checks appear here.")
        self._append_log("Choose an EPUB to begin.", tag="muted")
        self._poll()
        self._check_for_updates()

    @staticmethod
    def _default_open_dir() -> Path:
        downloads = Path.home() / "Downloads"
        return downloads if downloads.is_dir() else Path.home()

    def _center_window(self) -> None:
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        width = min(860, max(720, screen_w - 80))
        height = min(740, max(600, screen_h - 80))
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    @staticmethod
    def _load_image(name: str) -> tk.PhotoImage | None:
        path = Path(__file__).resolve().parent / "theme" / name
        try:
            return tk.PhotoImage(file=str(path))
        except (OSError, tk.TclError):
            return None

    def _set_icon(self) -> None:
        self._icon_image = self._load_image("gui-icon.png")
        if self._icon_image is not None:
            with contextlib.suppress(tk.TclError):
                self.root.iconphoto(True, self._icon_image)

    def _is_high_density(self) -> bool:
        try:
            dpi = float(self.root.winfo_fpixels("1i")) / 96.0
        except (tk.TclError, ValueError):
            dpi = 1.0
        try:
            scaling = float(self.root.tk.call("tk", "scaling")) / (96.0 / 72.0)
        except (tk.TclError, ValueError):
            scaling = 1.0
        return max(dpi, scaling) >= 1.5

    # -- typography and widgets -------------------------------------------
    def _configure_fonts(self) -> None:
        ui_candidates, display_candidates, mono_candidates = _font_candidates()
        self.ui_family = _pick_font(self.root, ui_candidates)
        self.display_family = _pick_font(self.root, display_candidates)
        self.mono_family = _pick_font(self.root, mono_candidates)

        self.font_brand = tkfont.Font(family=self.ui_family, size=8, weight="bold")
        self.font_body = tkfont.Font(family=self.ui_family, size=10)
        self.font_small = tkfont.Font(family=self.ui_family, size=9)
        self.font_filename = tkfont.Font(family=self.ui_family, size=12, weight="bold")
        self.font_display = tkfont.Font(family=self.display_family, size=25, weight="bold")
        self.font_dialog = tkfont.Font(family=self.display_family, size=18, weight="bold")
        self.font_mono = tkfont.Font(family=self.mono_family, size=9)

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        with contextlib.suppress(tk.TclError):
            style.theme_use("clam")
        self.style = style

        style.configure(
            "Primary.TButton",
            background=ACCENT,
            foreground=ACCENT_INK,
            bordercolor=ACCENT,
            lightcolor=ACCENT,
            darkcolor=ACCENT,
            relief="flat",
            padding=(22, 11),
            font=(self.ui_family, 10, "bold"),
            focuscolor=ACCENT_2,
        )
        style.map(
            "Primary.TButton",
            background=[
                ("disabled", "#e3d7c8"),
                ("pressed", ACCENT_2),
                ("active", ACCENT_HOVER),
            ],
            foreground=[
                ("disabled", "#8f7f6d"),
                ("pressed", ACCENT_INK),
                ("active", ACCENT_INK),
            ],
            bordercolor=[
                ("disabled", "#e3d7c8"),
                ("pressed", ACCENT_2),
                ("active", ACCENT_HOVER),
            ],
            lightcolor=[
                ("disabled", "#e3d7c8"),
                ("pressed", ACCENT_2),
                ("active", ACCENT_HOVER),
            ],
            darkcolor=[
                ("disabled", "#e3d7c8"),
                ("pressed", ACCENT_2),
                ("active", ACCENT_HOVER),
            ],
        )

        style.configure(
            "Secondary.TButton",
            background=SURFACE,
            foreground=INK_2,
            bordercolor=RULE_STRONG,
            lightcolor=SURFACE,
            darkcolor=SURFACE,
            relief="flat",
            padding=(16, 10),
            font=(self.ui_family, 9, "bold"),
            focuscolor=ACCENT,
        )
        style.map(
            "Secondary.TButton",
            background=[
                ("disabled", "#f7f2e9"),
                ("pressed", SURFACE_ALT),
                ("active", SURFACE_ALT),
            ],
            foreground=[
                ("disabled", "#b4a795"),
                ("pressed", INK),
                ("active", INK),
            ],
            bordercolor=[
                ("disabled", "#e5dccd"),
                ("pressed", ACCENT),
                ("active", ACCENT),
            ],
            lightcolor=[("pressed", SURFACE_ALT), ("active", SURFACE_ALT)],
            darkcolor=[("pressed", SURFACE_ALT), ("active", SURFACE_ALT)],
        )

        style.configure(
            "Ghost.TButton",
            background=SURFACE,
            foreground=ACCENT,
            bordercolor=ACCENT,
            lightcolor=SURFACE,
            darkcolor=SURFACE,
            relief="flat",
            padding=(16, 10),
            font=(self.ui_family, 9, "bold"),
            focuscolor=ACCENT,
        )
        style.map(
            "Ghost.TButton",
            background=[
                ("disabled", SURFACE),
                ("pressed", ACCENT_SOFT),
                ("active", ACCENT_SOFT),
            ],
            foreground=[
                ("disabled", MUTED),
                ("pressed", ACCENT_2),
                ("active", ACCENT_2),
            ],
            bordercolor=[
                ("disabled", RULE),
                ("pressed", ACCENT_2),
                ("active", ACCENT_2),
            ],
            lightcolor=[("pressed", ACCENT_SOFT), ("active", ACCENT_SOFT)],
            darkcolor=[("pressed", ACCENT_SOFT), ("active", ACCENT_SOFT)],
        )

        style.configure(
            "Icon.TButton",
            background=BG,
            foreground=INK_2,
            bordercolor=BG,
            lightcolor=BG,
            darkcolor=BG,
            relief="flat",
            padding=(8, 8),
            focuscolor=ACCENT,
        )
        style.map(
            "Icon.TButton",
            background=[
                ("pressed", SURFACE_ALT),
                ("active", SURFACE_ALT),
            ],
            bordercolor=[
                ("pressed", SURFACE_ALT),
                ("active", SURFACE_ALT),
            ],
            lightcolor=[
                ("pressed", SURFACE_ALT),
                ("active", SURFACE_ALT),
            ],
            darkcolor=[
                ("pressed", SURFACE_ALT),
                ("active", SURFACE_ALT),
            ],
        )

        style.configure(
            "Accent.Horizontal.TProgressbar",
            troughcolor=SURFACE_ALT,
            background=ACCENT,
            bordercolor=SURFACE_ALT,
            lightcolor=ACCENT,
            darkcolor=ACCENT,
            thickness=4,
        )

    def _build_ui(self) -> None:
        tk.Frame(self.root, bg=ACCENT, height=4).pack(fill="x")

        outer = tk.Frame(self.root, bg=BG, padx=28, pady=24)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(7, weight=1)

        self._build_header(outer)
        self._build_source_card(outer)
        self._build_output_row(outer)
        self._build_actions(outer)
        self._build_progress(outer)
        self._build_status(outer)
        self._build_log(outer)

    def _build_header(self, outer: tk.Frame) -> None:
        header = tk.Frame(outer, bg=BG)
        header.grid(row=0, column=0, sticky="ew")

        brand = tk.Frame(header, bg=BG)
        brand.pack(fill="x")

        brand_mark = tk.Frame(brand, bg=BG)
        brand_mark.pack(side="left")
        mark = tk.Canvas(brand_mark, width=10, height=10, bg=BG, highlightthickness=0)
        mark.create_oval(1, 1, 9, 9, fill=ACCENT, outline="")
        mark.pack(side="left", pady=(1, 0))
        tk.Label(
            brand_mark,
            text="epub2web",
            bg=BG,
            fg=ACCENT,
            font=self.font_brand,
        ).pack(side="left", padx=(8, 0))

        brand_actions = tk.Frame(brand, bg=BG)
        brand_actions.pack(side="right")
        self.update_button = ttk.Button(
            brand_actions,
            text="Update",
            style="Primary.TButton",
            command=self._show_update_dialog,
        )
        self.website_button = ttk.Button(
            brand_actions,
            text="Website",
            style="Ghost.TButton",
            command=self._open_website,
        )
        self.website_button.pack(side="right")

        self._github_icon = self._load_image(
            "gui-github-2x.png" if self._is_high_density() else "gui-github.png"
        )
        self.github_button = ttk.Button(
            brand_actions,
            text="GitHub",
            style="Icon.TButton",
            command=self._open_github,
            takefocus=True,
        )
        if self._github_icon is not None:
            self.github_button.configure(image=self._github_icon, compound="none")
        self.github_button.pack(side="right", padx=(0, 8))

        tk.Label(
            header,
            text="Turn an EPUB into a website",
            bg=BG,
            fg=INK,
            font=self.font_display,
            anchor="w",
        ).pack(fill="x", pady=(14, 0))
        tk.Label(
            header,
            text="A readable web edition, verified against the source.",
            bg=BG,
            fg=MUTED,
            font=self.font_body,
            anchor="w",
        ).pack(fill="x", pady=(6, 0))

    def _build_source_card(self, outer: tk.Frame) -> None:
        card = tk.Frame(outer, bg=SURFACE, highlightbackground=RULE, highlightthickness=1)
        card.grid(row=1, column=0, sticky="ew", pady=(26, 10))
        card.columnconfigure(0, weight=1)

        inner = tk.Frame(card, bg=SURFACE, padx=20, pady=16)
        inner.grid(row=0, column=0, sticky="ew")
        inner.columnconfigure(1, weight=1)

        eyebrow = tk.Frame(inner, bg=SURFACE)
        eyebrow.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 12))
        tk.Label(
            eyebrow,
            text="SOURCE",
            bg=SURFACE,
            fg=MUTED,
            font=self.font_brand,
        ).pack(side="left")
        tk.Label(
            eyebrow,
            text="EPUB 2 / 3",
            bg=ACCENT_SOFT,
            fg=ACCENT,
            font=self.font_brand,
            padx=8,
            pady=3,
        ).pack(side="right")

        icon = tk.Canvas(inner, width=44, height=44, bg=SURFACE, highlightthickness=0)
        icon.grid(row=1, column=0, rowspan=2, sticky="nw", padx=(0, 14))
        self._draw_book_icon(icon)

        self.file_name_var = tk.StringVar(value="No EPUB selected")
        self.file_path_var = tk.StringVar(value="Choose a reflowable EPUB 2/3 file to begin.")
        tk.Label(
            inner,
            textvariable=self.file_name_var,
            bg=SURFACE,
            fg=INK,
            font=self.font_filename,
            anchor="w",
            justify="left",
            wraplength=420,
        ).grid(row=1, column=1, sticky="ew")
        self.file_path_label = tk.Label(
            inner,
            textvariable=self.file_path_var,
            bg=SURFACE,
            fg=MUTED,
            font=self.font_small,
            anchor="w",
            justify="left",
            wraplength=420,
        )
        self.file_path_label.grid(row=2, column=1, sticky="ew", pady=(3, 0))

        self.choose_button = ttk.Button(
            inner,
            text="Choose EPUB…",
            style="Ghost.TButton",
            command=self._choose_epub,
        )
        self.choose_button.grid(row=1, column=2, rowspan=2, sticky="e", padx=(16, 0))

    @staticmethod
    def _draw_book_icon(canvas: tk.Canvas) -> None:
        canvas.create_polygon(
            8,
            13,
            21,
            10,
            21,
            36,
            8,
            39,
            fill=SURFACE,
            outline=ACCENT,
            width=2,
        )
        canvas.create_polygon(
            21,
            10,
            34,
            13,
            34,
            39,
            21,
            36,
            fill=SURFACE,
            outline=ACCENT,
            width=2,
        )
        canvas.create_line(21, 10, 21, 36, fill=ACCENT, width=2)

    def _build_output_row(self, outer: tk.Frame) -> None:
        output = tk.Frame(outer, bg=BG)
        output.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        output.columnconfigure(1, weight=1)
        tk.Label(
            output,
            text="OUTPUT",
            bg=BG,
            fg=MUTED,
            font=self.font_brand,
        ).grid(row=0, column=0, sticky="nw", padx=(2, 12), pady=(2, 0))
        self.output_var = tk.StringVar(value="The generated site will appear here.")
        tk.Label(
            output,
            textvariable=self.output_var,
            bg=BG,
            fg=INK_2,
            font=self.font_small,
            anchor="w",
            justify="left",
            wraplength=600,
        ).grid(row=0, column=1, sticky="w")

    def _build_actions(self, outer: tk.Frame) -> None:
        actions = tk.Frame(outer, bg=BG)
        actions.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        self.convert_button = ttk.Button(
            actions,
            text="Convert",
            style="Primary.TButton",
            command=self._convert,
        )
        self.convert_button.pack(side="left")
        self.stop_button = ttk.Button(
            actions,
            text="Stop",
            style="Secondary.TButton",
            command=self._stop,
        )
        self.stop_button.pack(side="left", padx=(8, 0))
        self.open_button = ttk.Button(
            actions,
            text="Open preview",
            style="Secondary.TButton",
            command=self._open_preview,
        )
        self.open_button.pack(side="left", padx=(8, 0))

    def _build_progress(self, outer: tk.Frame) -> None:
        self.progress = ttk.Progressbar(
            outer,
            style="Accent.Horizontal.TProgressbar",
            mode="indeterminate",
        )
        self.progress.grid(row=4, column=0, sticky="ew", pady=(14, 0))
        self.progress.grid_remove()

    def _build_status(self, outer: tk.Frame) -> None:
        status = tk.Frame(outer, bg=BG)
        status.grid(row=5, column=0, sticky="ew", pady=(12, 0))
        status.columnconfigure(1, weight=1)
        self.status_dot = tk.Canvas(status, width=10, height=10, bg=BG, highlightthickness=0)
        self.status_dot.grid(row=0, column=0, sticky="w", pady=(2, 0))
        self._status_dot_id = self.status_dot.create_oval(1, 1, 9, 9, fill=MUTED, outline="")
        self.status_var = tk.StringVar(value="Choose an EPUB to begin.")
        self.status_label = tk.Label(
            status,
            textvariable=self.status_var,
            bg=BG,
            fg=INK_2,
            font=self.font_small,
            anchor="w",
            justify="left",
            wraplength=640,
        )
        self.status_label.grid(row=0, column=1, sticky="w", padx=(8, 0))

    def _build_log(self, outer: tk.Frame) -> None:
        log_header = tk.Frame(outer, bg=BG)
        log_header.grid(row=6, column=0, sticky="ew", pady=(22, 8))
        tk.Label(
            log_header,
            text="BUILD LOG",
            bg=BG,
            fg=MUTED,
            font=self.font_brand,
        ).pack(side="left")
        self.log_hint_var = tk.StringVar(value="Fidelity and link checks appear here.")
        tk.Label(
            log_header,
            textvariable=self.log_hint_var,
            bg=BG,
            fg=MUTED,
            font=self.font_small,
        ).pack(side="right")

        log_card = tk.Frame(
            outer,
            bg=LOG_BG,
            highlightbackground="#2c2822",
            highlightthickness=1,
        )
        log_card.grid(row=7, column=0, sticky="nsew")
        log_card.columnconfigure(0, weight=1)
        log_card.rowconfigure(0, weight=1)

        self.log = tk.Text(
            log_card,
            height=10,
            wrap="word",
            state="disabled",
            font=self.font_mono,
            bg=LOG_BG,
            fg=LOG_FG,
            insertbackground=LOG_FG,
            selectbackground=ACCENT,
            selectforeground=ACCENT_INK,
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=16,
            pady=14,
            spacing1=2,
            spacing3=2,
        )
        self.log.grid(row=0, column=0, sticky="nsew")
        self.log.bind("<MouseWheel>", self._on_log_mousewheel)
        self.log.bind("<Button-4>", lambda _event: self.log.yview_scroll(-3, "units"))
        self.log.bind("<Button-5>", lambda _event: self.log.yview_scroll(3, "units"))

        self.log_scroll = tk.Canvas(
            log_card,
            width=12,
            bg=LOG_BG,
            highlightthickness=0,
            cursor="hand2",
        )
        self.log_scroll.grid(row=0, column=1, sticky="ns")
        self.log_scroll.bind(
            "<Configure>",
            lambda _event: self._update_log_scrollbar(
                self._log_scroll_first, self._log_scroll_last
            ),
        )
        self.log_scroll.bind("<Button-1>", self._scrollbar_press)
        self.log_scroll.bind("<B1-Motion>", self._scrollbar_drag)
        self.log_scroll.bind("<ButtonRelease-1>", self._scrollbar_release)
        self.log_scroll.bind("<MouseWheel>", self._on_log_mousewheel)
        self.log_scroll.bind("<Button-4>", lambda _event: self.log.yview_scroll(-3, "units"))
        self.log_scroll.bind("<Button-5>", lambda _event: self.log.yview_scroll(3, "units"))
        self.log.configure(yscrollcommand=self._update_log_scrollbar)

        self.log.tag_configure("error", foreground=LOG_ERROR)
        self.log.tag_configure("success", foreground=LOG_SUCCESS)
        self.log.tag_configure("preview", foreground=LOG_ACCENT)
        self.log.tag_configure("muted", foreground=LOG_MUTED)

    # -- user actions -----------------------------------------------------
    def _choose_epub(self) -> None:
        filename = filedialog.askopenfilename(
            parent=self.root,
            title="Choose an EPUB",
            initialdir=str(self._last_dir),
            filetypes=(("EPUB books", "*.epub"), ("All files", "*.*")),
        )
        if not filename:
            return
        path = Path(filename)
        if not path.is_file():
            self._show_error(
                "File not found",
                "The selected EPUB is no longer available.",
                str(path),
            )
            return

        self.epub = path
        self._last_dir = path.parent
        self.controller = None
        self.preview_url = None
        self.output = default_output_dir(path)
        self.file_name_var.set(self._friendly_filename(path))
        self.file_path_var.set(self._display_path(path))
        self.output_var.set(self._display_path(self.output))
        self._reset_log()
        self._append_log(f"Selected {self._friendly_filename(path)}", tag="muted")
        self._set_status("Ready to convert.", "ready")
        self._set_log_hint("Fidelity and link checks appear here.")
        self._refresh_controls()
        threading.Thread(
            target=self._load_book_info,
            args=(path,),
            daemon=True,
            name="epub2web-metadata",
        ).start()

    @staticmethod
    def _friendly_filename(path: Path) -> str:
        name = path.stem.strip()
        if " -- " in name:
            name = name.split(" -- ", 1)[0]
        name = name.replace("_", " ").strip()
        return name or path.name

    @staticmethod
    def _display_path(path: Path, name_limit: int = 44) -> str:
        try:
            parent = "~" + os.sep + str(path.parent.relative_to(Path.home()))
        except ValueError:
            parent = str(path.parent)
        name = path.name
        if len(name) > name_limit:
            name = name[: name_limit - 1].rstrip() + "…"
        return f"{parent.rstrip(os.sep + '/')}{os.sep}{name}"

    def _load_book_info(self, path: Path) -> None:
        try:
            from .cli import detect

            info = detect(path)
        except Exception:
            return
        self.book_info_queue.put((path, info))

    def _apply_book_info(self, path: Path, info: dict) -> None:
        if self.epub != path or self.controller is not None:
            return
        title = str(info.get("title") or "").strip()
        if not title:
            return
        self.file_name_var.set(title)
        self.output = default_output_dir(path, title=title)
        self.output_var.set(self._display_path(self.output))
        self._set_status("Ready to convert.", "ready")

    def _convert(self) -> None:
        if self.epub is None or self.output is None or self._building:
            return
        if self.controller is not None and self.controller.is_running:
            return

        try:
            self.output.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._show_error("Could not create the output folder", str(exc))
            return

        self.preview_url = None
        self._building = True
        self._preview_running = False
        self._auto_open_preview = False
        self._progress_determinate = False
        self._last_progress_key = None
        self.progress.configure(mode="indeterminate", value=0)
        self._refresh_controls()
        self._set_status("Converting…", "accent")
        self._set_log_hint("Running fidelity and link checks…")
        self._reset_log()
        self._append_log(f"Converting {self.file_name_var.get()} …")

        try:
            controller = BuildController(
                on_event=self.events.put,
                # Keep the preview origin stable between runs so the browser
                # can restore the reader's saved position.
                port=8000,
                open_browser=False,
                log_dir=default_log_dir(),
                report_dir=default_report_dir(),
            )
            self.controller = controller
            controller.start(self.epub, self.output)
        except Exception as exc:
            self._building = False
            self._refresh_controls()
            self._set_status("Could not start conversion.", "error")
            self._set_log_hint("Build failed. See the error below.")
            self._append_log(f"error: {exc}", tag="error")
            self._show_error("Could not start conversion", str(exc))

    def _stop(self) -> None:
        if self.controller is None:
            return
        self._set_status("Stopping…", "accent")
        self._set_log_hint("Stopping the preview server…")
        self.stop_button.configure(state="disabled")
        self.controller.stop(timeout=5.0)
        # The controller emits a "stopped" event from its reader thread; the
        # poll loop above applies it on the Tk main thread.

    def _open_preview(self) -> None:
        if not self.preview_url or not self._preview_running:
            return
        self._open_external_url(
            self.preview_url,
            "Open preview",
            detail_label="PREVIEW ADDRESS",
        )

    def _open_github(self) -> None:
        self._open_external_url(GITHUB_URL, "Open GitHub")

    def _open_website(self) -> None:
        self._open_external_url(WEBSITE_URL, "Open website")

    def _open_download_page(self) -> None:
        self._open_external_url(DOWNLOAD_URL, "Open download page")

    def _open_external_url(
        self,
        url: str,
        title: str,
        *,
        detail_label: str = "ADDRESS",
    ) -> None:
        try:
            opened = webbrowser.open(url)
        except Exception as exc:
            self._show_error("Could not open the browser", str(exc))
            return
        if not opened:
            self._show_info(
                title,
                "Open this address in your browser:",
                url,
                detail_label,
            )

    def _open_preview_async(self) -> None:
        """Open the browser without blocking Tk while the OS dispatches it."""
        if not self.preview_url or not self._preview_running:
            return
        threading.Thread(
            target=webbrowser.open,
            args=(self.preview_url,),
            daemon=True,
            name="epub2web-browser",
        ).start()

    # -- update checks ----------------------------------------------------
    def _check_for_updates(self) -> None:
        if os.environ.get("EPUB2WEB_NO_UPDATE_CHECK"):
            return
        threading.Thread(
            target=self._fetch_update,
            daemon=True,
            name="epub2web-update",
        ).start()

    def _fetch_update(self) -> None:
        try:
            release = fetch_latest_release()
        except Exception:
            release = None
        self.update_queue.put(release)

    def _apply_update(self, release: ReleaseInfo | None) -> None:
        if release is None or self.update_info is not None:
            return
        if not is_newer(release.version):
            return
        self.update_info = release
        self.update_button.pack(side="right", padx=(0, 8))

    # -- event handling ---------------------------------------------------
    def _poll(self) -> None:
        try:
            while True:
                path, info = self.book_info_queue.get_nowait()
                self._apply_book_info(path, info)
        except queue.Empty:
            pass
        try:
            while True:
                self._apply_update(self.update_queue.get_nowait())
        except queue.Empty:
            pass
        try:
            while True:
                self._handle_event(self.events.get_nowait())
        except queue.Empty:
            pass
        finally:
            self._poll_id = self.root.after(100, self._poll)

    def _handle_event(self, event: BuildEvent) -> None:
        if event.kind == "log":
            self._append_log(event.message, tag=self._log_tag(event.message))
            return

        if event.kind == "progress":
            self._handle_progress(event.data)
            return

        if event.kind == "site":
            self._set_status("Site built. Starting preview…", "accent")
            self._set_log_hint("Starting the local preview server…")
            return

        if event.kind == "preview":
            self.preview_url = str(event.data.get("url") or "")
            self._building = False
            self._preview_running = bool(self.preview_url)
            self._refresh_controls()
            if self.preview_url:
                self._set_status(f"Preview running at {self.preview_url}", "success")
                self._set_log_hint("Preview running. Use Stop to close the local server.")
                self._append_log("Preview server started.", tag="preview")
                if not self._auto_open_preview:
                    self._auto_open_preview = True
                    self.root.after(100, self._open_preview_async)
            else:
                self._set_status("Preview unavailable.", "error")
            return

        if event.kind == "success":
            url = str(event.data.get("url") or "")
            if url:
                self.preview_url = url
            self._building = False
            self._preview_running = bool(self.preview_url) and (
                self.controller is None or self.controller.is_running
            )
            self._refresh_controls()
            if self.preview_url:
                self._set_status(f"Preview running at {self.preview_url}", "success")
                self._set_log_hint("Preview running. Use Stop to close the local server.")
            else:
                site = str(event.data.get("site") or "")
                self._set_status("Conversion complete.", "success")
                self._set_log_hint("All checks passed.")
                self._append_log(
                    "Conversion complete." + (f" Site: {site}" if site else ""),
                    tag="success",
                )
            return

        if event.kind == "failure":
            self._building = False
            self._preview_running = False
            self.preview_url = None
            self._refresh_controls()
            message = event.message or "Conversion failed."
            self._set_status(message, "error")
            self._set_log_hint("Build failed. The support report is ready.")
            self._append_log(message, tag="error")
            report = str(event.data.get("report") or "")
            self._show_error(
                "Build failed",
                message,
                f"Support report:\n{report}" if report else "",
                "SUPPORT REPORT" if report else "DETAILS",
            )
            return

        if event.kind == "stopped":
            self._building = False
            self._preview_running = False
            self.preview_url = None
            self._refresh_controls()
            self._set_status("Stopped.", "muted")
            self._set_log_hint("Fidelity and link checks appear here.")

    def _handle_progress(self, data: dict) -> None:
        if not self._building:
            return
        try:
            percent = float(data.get("percent") or 0.0)
            current = int(data.get("current") or 0)
            total = int(data.get("total") or 0)
        except (TypeError, ValueError):
            return
        if not 0.0 <= percent <= 1.0:
            percent = max(0.0, min(1.0, percent))
        label = str(data.get("label") or "Working")
        phase = str(data.get("phase") or "")

        if not self._progress_determinate:
            self.progress.stop()
            self.progress.configure(mode="determinate", maximum=100, value=0)
            self._progress_determinate = True
            self.progress.grid()
        self.progress["value"] = percent * 100

        if total > 1:
            self._set_status(
                f"{label} — {current:,} of {total:,} · {percent * 100:.0f}%",
                "accent",
            )
        else:
            self._set_status(f"{label}… {percent * 100:.0f}%", "accent")
        self._set_log_hint(f"{label} · {percent * 100:.0f}% complete")
        self._log_progress_milestone(phase, label, current, total)

    def _log_progress_milestone(
        self,
        phase: str,
        label: str,
        current: int,
        total: int,
    ) -> None:
        if total <= 0:
            return
        if total == 1 and current < 1:
            return
        bucket = min(10, int(current * 10 / total))
        key = (phase, bucket)
        if key == self._last_progress_key:
            return
        self._last_progress_key = key
        if total > 1 and current == 0:
            line = f"{label}…"
        elif total > 1:
            line = f"{label}: {current:,} of {total:,}"
        else:
            line = f"{label}: done"
        self._append_log(line, tag="muted")

    def _log_tag(self, message: str) -> str | None:
        if message.startswith(("Report:", "Log:")):
            return "muted"
        if message.startswith("error:") or "FAIL" in message:
            return "error"
        if "PASS" in message:
            return "success"
        return None

    def _refresh_controls(self) -> None:
        locked = self._building or self._preview_running
        self.choose_button.configure(state="disabled" if locked else "normal")
        self.convert_button.configure(
            state="normal" if (self.epub is not None and not locked) else "disabled"
        )
        self.stop_button.configure(
            state="normal" if (self._building or self._preview_running) else "disabled"
        )
        self.open_button.configure(
            state="normal" if (self._preview_running and self.preview_url) else "disabled"
        )
        if self._building:
            self.progress.grid()
            if self._progress_determinate:
                self.progress.stop()
            else:
                self.progress.configure(mode="indeterminate")
                self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.grid_remove()

    # -- log --------------------------------------------------------------
    def _reset_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self._update_log_scrollbar("0.0", "1.0")

    def _update_log_scrollbar(self, first: str | float, last: str | float) -> None:
        self._log_scroll_first = float(first)
        self._log_scroll_last = float(last)
        self.log_scroll.delete("scrollbar")

        if self._log_scroll_first <= 0.0 and self._log_scroll_last >= 1.0:
            self._log_thumb_top = 0.0
            self._log_thumb_bottom = 0.0
            return
        height = self.log_scroll.winfo_height()
        if height <= 1:
            return

        pad = 4.0
        usable = max(1.0, height - 2 * pad)
        top = pad + self._log_scroll_first * usable
        bottom = pad + self._log_scroll_last * usable
        if bottom - top < 26:
            bottom = min(height - pad, top + 26)
            top = max(pad, bottom - 26)
        self._log_thumb_top = top
        self._log_thumb_bottom = bottom
        self.log_scroll.create_line(
            6,
            pad,
            6,
            height - pad,
            width=6,
            fill="#2a2620",
            capstyle="round",
            tags="scrollbar",
        )
        self.log_scroll.create_line(
            6,
            top,
            6,
            bottom,
            width=6,
            fill="#5f5548",
            activefill="#8a7d6b",
            capstyle="round",
            tags="scrollbar",
        )

    def _scrollbar_press(self, event: tk.Event) -> None:
        if self._log_thumb_top <= 0.0:
            return
        if self._log_thumb_top <= event.y <= self._log_thumb_bottom:
            self._log_dragging = True
            self._log_drag_start = event.y
            self._log_drag_first = self.log.yview()[0]
        elif event.y < self._log_thumb_top:
            self.log.yview_scroll(-1, "pages")
        else:
            self.log.yview_scroll(1, "pages")

    def _scrollbar_drag(self, event: tk.Event) -> None:
        if not self._log_dragging:
            return
        usable = max(1, self.log_scroll.winfo_height() - 8)
        target = self._log_drag_first + (event.y - self._log_drag_start) / usable
        self.log.yview_moveto(max(0.0, min(1.0, target)))

    def _scrollbar_release(self, _event: tk.Event) -> None:
        self._log_dragging = False

    def _on_log_mousewheel(self, event: tk.Event) -> str:
        if event.delta:
            steps = int(-event.delta / 120)
            if steps == 0:
                steps = -1 if event.delta > 0 else 1
            self.log.yview_scroll(steps, "units")
        return "break"

    def _append_log(self, text: str, *, tag: str | None = None) -> None:
        self.log.configure(state="normal")
        if self.log.index("end-1c") != "1.0":
            self.log.insert("end", "\n")
        if tag:
            self.log.insert("end", text, tag)
        else:
            self.log.insert("end", text)
        self.log.configure(state="disabled")
        self.log.see("end")

        line_count = int(self.log.index("end-1c").split(".", 1)[0])
        if line_count > LOG_LINE_LIMIT:
            self.log.configure(state="normal")
            self.log.delete("1.0", f"{line_count - LOG_LINE_LIMIT}.0")
            self.log.configure(state="disabled")

    def _set_status(self, text: str, tone: str = "muted") -> None:
        dot, foreground = {
            "muted": (MUTED, INK_2),
            "ready": (SUCCESS, INK_2),
            "accent": (ACCENT, INK_2),
            "success": (SUCCESS, SUCCESS),
            "error": (DANGER, DANGER),
        }.get(tone, (MUTED, INK_2))
        self.status_var.set(text)
        self.status_dot.itemconfigure(self._status_dot_id, fill=dot)
        self.status_label.configure(fg=foreground)

    def _set_log_hint(self, text: str) -> None:
        self.log_hint_var.set(text)

    def _show_update_dialog(self) -> None:
        release = self.update_info
        if release is None:
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"{APP_TITLE} — Update available")
        dialog.transient(self.root)
        dialog.configure(bg=BG)
        dialog.minsize(520, 420)
        if self._icon_image is not None:
            with contextlib.suppress(tk.TclError):
                dialog.iconphoto(True, self._icon_image)

        def close() -> None:
            with contextlib.suppress(tk.TclError):
                dialog.grab_release()
            with contextlib.suppress(tk.TclError):
                dialog.destroy()

        def download() -> None:
            close()
            self.root.after(0, self._open_download_page)

        tk.Frame(dialog, bg=ACCENT, height=4).pack(fill="x")
        outer = tk.Frame(dialog, bg=BG, padx=18, pady=18)
        outer.pack(fill="both", expand=True)
        card = tk.Frame(
            outer,
            bg=SURFACE,
            highlightbackground=RULE,
            highlightthickness=1,
        )
        card.pack(fill="both", expand=True)
        inner = tk.Frame(card, bg=SURFACE, padx=22, pady=20)
        inner.pack(fill="both", expand=True)

        tk.Label(
            inner,
            text="Update available",
            bg=SURFACE,
            fg=INK,
            font=self.font_dialog,
            anchor="w",
            justify="left",
        ).pack(fill="x")
        tk.Label(
            inner,
            text=f"epub2web {release.version} is available. You are running {__version__}.",
            bg=SURFACE,
            fg=INK_2,
            font=self.font_body,
            anchor="w",
            justify="left",
            wraplength=500,
        ).pack(fill="x", pady=(8, 0))

        tk.Label(
            inner,
            text="WHAT'S NEW",
            bg=SURFACE,
            fg=MUTED,
            font=self.font_brand,
            anchor="w",
        ).pack(fill="x", pady=(18, 6))

        notes_frame = tk.Frame(
            inner,
            bg=SURFACE_ALT,
            highlightbackground=RULE,
            highlightthickness=1,
        )
        notes_frame.pack(fill="both", expand=True)
        notes_frame.columnconfigure(0, weight=1)
        notes_frame.rowconfigure(0, weight=1)
        notes = tk.Text(
            notes_frame,
            height=12,
            width=58,
            wrap="word",
            bg=SURFACE_ALT,
            fg=INK_2,
            font=self.font_body,
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=12,
            pady=10,
        )
        notes.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(notes_frame, orient="vertical", command=notes.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        notes.configure(yscrollcommand=scroll.set)
        notes.insert("1.0", release.notes.strip() or "See the download page for details.")
        notes.configure(state="disabled")

        actions = tk.Frame(inner, bg=SURFACE)
        actions.pack(fill="x", pady=(18, 0))
        download_button = ttk.Button(
            actions,
            text="Open download page",
            style="Primary.TButton",
            command=download,
        )
        download_button.pack(side="right")
        later = ttk.Button(
            actions,
            text="Later",
            style="Secondary.TButton",
            command=close,
        )
        later.pack(side="right", padx=(0, 8))

        dialog.bind("<Escape>", lambda _event: close())
        dialog.protocol("WM_DELETE_WINDOW", close)
        dialog.update_idletasks()
        width = max(540, dialog.winfo_reqwidth())
        height = max(460, dialog.winfo_reqheight())
        x = self.root.winfo_rootx() + max(0, (self.root.winfo_width() - width) // 2)
        y = self.root.winfo_rooty() + max(0, (self.root.winfo_height() - height) // 3)
        dialog.geometry(f"{width}x{height}+{x}+{y}")
        dialog.grab_set()
        download_button.focus_set()
        self.root.wait_window(dialog)

    def _show_error(
        self,
        title: str,
        message: str,
        detail: str = "",
        detail_label: str = "DETAILS",
    ) -> None:
        self._show_dialog(
            title,
            message,
            detail,
            detail_label,
            bar_color=DANGER,
        )

    def _show_info(
        self,
        title: str,
        message: str,
        detail: str = "",
        detail_label: str = "DETAILS",
    ) -> None:
        self._show_dialog(
            title,
            message,
            detail,
            detail_label,
            bar_color=SUCCESS,
        )

    def _show_dialog(
        self,
        title: str,
        message: str,
        detail: str = "",
        detail_label: str = "DETAILS",
        *,
        bar_color: str = DANGER,
    ) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title(f"{APP_TITLE} — {title}")
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.configure(bg=BG)
        if self._icon_image is not None:
            with contextlib.suppress(tk.TclError):
                dialog.iconphoto(True, self._icon_image)

        def close() -> None:
            with contextlib.suppress(tk.TclError):
                dialog.grab_release()
            with contextlib.suppress(tk.TclError):
                dialog.destroy()

        tk.Frame(dialog, bg=bar_color, height=4).pack(fill="x")
        outer = tk.Frame(dialog, bg=BG, padx=18, pady=18)
        outer.pack(fill="both", expand=True)
        card = tk.Frame(
            outer,
            bg=SURFACE,
            highlightbackground=RULE,
            highlightthickness=1,
        )
        card.pack(fill="both", expand=True)
        inner = tk.Frame(card, bg=SURFACE, padx=22, pady=20)
        inner.pack(fill="both", expand=True)

        tk.Label(
            inner,
            text=title,
            bg=SURFACE,
            fg=INK,
            font=self.font_dialog,
            anchor="w",
            justify="left",
            wraplength=430,
        ).pack(fill="x")
        tk.Label(
            inner,
            text=message,
            bg=SURFACE,
            fg=INK_2,
            font=self.font_body,
            anchor="w",
            justify="left",
            wraplength=430,
        ).pack(fill="x", pady=(8, 0))

        if detail:
            tk.Label(
                inner,
                text=detail_label,
                bg=SURFACE,
                fg=MUTED,
                font=self.font_brand,
                anchor="w",
            ).pack(fill="x", pady=(16, 6))
            box = tk.Text(
                inner,
                height=3,
                wrap="word",
                bg=SURFACE_ALT,
                fg=INK_2,
                font=self.font_mono,
                relief="flat",
                borderwidth=0,
                highlightthickness=1,
                highlightbackground=RULE,
                padx=10,
                pady=8,
            )
            box.insert("1.0", detail)
            box.configure(state="disabled")
            box.pack(fill="x")

        actions = tk.Frame(inner, bg=SURFACE)
        actions.pack(fill="x", pady=(18, 0))
        ok = ttk.Button(actions, text="OK", style="Primary.TButton", command=close)
        ok.pack(side="right")

        dialog.bind("<Escape>", lambda _event: close())
        dialog.protocol("WM_DELETE_WINDOW", close)
        dialog.update_idletasks()
        width = dialog.winfo_reqwidth()
        height = dialog.winfo_reqheight()
        x = self.root.winfo_rootx() + max(0, (self.root.winfo_width() - width) // 2)
        y = self.root.winfo_rooty() + max(0, (self.root.winfo_height() - height) // 3)
        dialog.geometry(f"+{x}+{y}")
        dialog.grab_set()
        ok.focus_set()
        self.root.wait_window(dialog)

    # -- shutdown ---------------------------------------------------------
    def _on_close(self) -> None:
        if self._poll_id is not None:
            self.root.after_cancel(self._poll_id)
            self._poll_id = None
        self._building = False
        self._preview_running = False
        if self.controller is not None and self.controller.is_running:
            with contextlib.suppress(Exception):
                self.controller.stop(timeout=5.0)
        self.root.destroy()


def _enable_windows_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            import ctypes

            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _print_error(text: str) -> None:
    stream = sys.stderr or sys.__stderr__
    if stream is not None:
        print(text, file=stream)


def run() -> int:
    """Create the window and run the Tk event loop."""
    _enable_windows_dpi_awareness()
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        _print_error(f"error: could not start the desktop GUI: {exc}")
        _print_error("This machine may not have a graphical display.")
        return 2

    try:
        Epub2WebApp(root)
        root.mainloop()
    except tk.TclError as exc:
        _print_error(f"error: could not start the desktop GUI: {exc}")
        return 2
    finally:
        with contextlib.suppress(tk.TclError):
            root.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
