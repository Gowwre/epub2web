"""Tkinter desktop interface for epub2web.

The view only talks to :class:`epub2web.controller.BuildController`. All
toolkit-specific code lives here so another toolkit can replace this module
without touching the worker or process lifecycle.
"""

from __future__ import annotations

import contextlib
import queue
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .controller import (
    BuildController,
    BuildEvent,
    default_log_dir,
    default_output_dir,
    default_report_dir,
)

APP_TITLE = "epub2web"
LOG_LINE_LIMIT = 2000


class Epub2WebApp:
    """Main application window. All Tk calls stay on the Tk main thread."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.minsize(640, 520)
        self.root.geometry("760x640")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.epub: Path | None = None
        self.output: Path | None = None
        self.preview_url: str | None = None
        self.controller: BuildController | None = None
        self.events: queue.Queue[BuildEvent] = queue.Queue()
        self._building = False
        self._preview_running = False
        self._auto_open_preview = False
        self._poll_id: str | None = None
        self._last_dir = self._default_open_dir()

        self._build_ui()
        self._refresh_controls()
        self._poll()

    @staticmethod
    def _default_open_dir() -> Path:
        downloads = Path.home() / "Downloads"
        return downloads if downloads.is_dir() else Path.home()

    # -- construction -----------------------------------------------------
    def _build_ui(self) -> None:
        # Keep references to every font object: Tkinter deletes a Font when its
        # Python wrapper is garbage-collected, and widgets only store the name.
        self.base_font = tkfont.nametofont("TkDefaultFont")
        self.heading_font = self.base_font.copy()
        self.heading_font.configure(size=18, weight="bold")
        self.subtitle_font = self.base_font.copy()
        self.subtitle_font.configure(size=10)
        self.log_font = tkfont.nametofont("TkFixedFont").copy()
        self.log_font.configure(size=9)

        root = self.root
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

        outer = ttk.Frame(root, padding=(20, 18))
        outer.grid(row=0, column=0, sticky="nsew")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(7, weight=1)

        ttk.Label(outer, text="Turn an EPUB into a website", font=self.heading_font).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            outer,
            text="Choose a reflowable EPUB 2/3 book, then convert it to a static site.",
            font=self.subtitle_font,
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        file_frame = ttk.LabelFrame(outer, text="EPUB file", padding=(12, 8))
        file_frame.grid(row=2, column=0, sticky="ew", pady=(16, 8))
        file_frame.columnconfigure(0, weight=1)

        self.file_var = tk.StringVar(value="No file selected")
        self.file_entry = ttk.Entry(file_frame, textvariable=self.file_var, state="readonly")
        self.file_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.choose_button = ttk.Button(
            file_frame,
            text="Choose EPUB…",
            command=self._choose_epub,
        )
        self.choose_button.grid(row=0, column=1)

        self.output_var = tk.StringVar(value="Output: choose an EPUB to see the destination.")
        ttk.Label(
            outer,
            textvariable=self.output_var,
            wraplength=680,
            justify="left",
        ).grid(row=3, column=0, sticky="w")

        actions = ttk.Frame(outer)
        actions.grid(row=4, column=0, sticky="ew", pady=(14, 6))
        self.convert_button = ttk.Button(actions, text="Convert", command=self._convert)
        self.convert_button.pack(side="left")
        self.stop_button = ttk.Button(actions, text="Stop", command=self._stop)
        self.stop_button.pack(side="left", padx=(8, 0))
        self.open_button = ttk.Button(
            actions,
            text="Open preview",
            command=self._open_preview,
        )
        self.open_button.pack(side="left", padx=(8, 0))

        self.progress = ttk.Progressbar(outer, mode="indeterminate")
        self.progress.grid(row=5, column=0, sticky="ew", pady=(4, 4))
        self.progress.grid_remove()

        self.status_var = tk.StringVar(value="Choose an EPUB to begin.")
        ttk.Label(
            outer,
            textvariable=self.status_var,
            wraplength=680,
            justify="left",
        ).grid(row=6, column=0, sticky="w")

        log_frame = ttk.LabelFrame(outer, text="Build log", padding=(8, 6))
        log_frame.grid(row=7, column=0, sticky="nsew", pady=(12, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log = tk.Text(
            log_frame,
            height=12,
            wrap="word",
            state="disabled",
            font=self.log_font,
            borderwidth=0,
            highlightthickness=1,
            highlightbackground="#d0d0d0",
        )
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scrollbar.set)
        self.log.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log.tag_configure("error", foreground="#b3261e")
        self.log.tag_configure("success", foreground="#1b5e20")
        self.log.tag_configure("preview", foreground="#0b5cad")

        self.choose_button.focus_set()

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
            messagebox.showerror(APP_TITLE, f"File not found:\n{path}")
            return

        self.epub = path
        self._last_dir = path.parent
        self.output = default_output_dir(path)
        self.file_var.set(str(path))
        self.output_var.set(f"Output: {self.output}")
        self._reset_log()
        self._append_log(f"Selected {path}")
        self._set_status("Ready to convert.")
        self._refresh_controls()

    def _convert(self) -> None:
        if self.epub is None or self.output is None or self._building:
            return
        if self.controller is not None and self.controller.is_running:
            return

        try:
            self.output.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            messagebox.showerror(APP_TITLE, f"Could not create the output folder:\n{exc}")
            return

        self.preview_url = None
        self._building = True
        self._preview_running = False
        self._auto_open_preview = False
        self._refresh_controls()
        self._set_status("Converting…")
        self._reset_log()
        self._append_log(f"Converting {self.epub.name} …")

        try:
            controller = BuildController(
                on_event=self.events.put,
                open_browser=False,
                log_dir=default_log_dir(),
                report_dir=default_report_dir(),
            )
            self.controller = controller
            controller.start(self.epub, self.output)
        except Exception as exc:
            self._building = False
            self._refresh_controls()
            self._set_status("Could not start conversion.")
            self._append_log(f"error: {exc}", tag="error")
            messagebox.showerror(APP_TITLE, f"Could not start conversion:\n{exc}")

    def _stop(self) -> None:
        if self.controller is None:
            return
        self._set_status("Stopping…")
        self.stop_button.configure(state="disabled")
        self.controller.stop(timeout=5.0)
        # The controller emits a "stopped" event from its reader thread; the
        # poll loop above applies it on the Tk main thread.

    def _open_preview(self) -> None:
        if not self.preview_url or not self._preview_running:
            return
        try:
            opened = webbrowser.open(self.preview_url)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Could not open the browser:\n{exc}")
            return
        if not opened:
            messagebox.showinfo(
                APP_TITLE,
                f"Open this address in your browser:\n\n{self.preview_url}",
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

    # -- event handling ---------------------------------------------------
    def _poll(self) -> None:
        try:
            while True:
                self._handle_event(self.events.get_nowait())
        except queue.Empty:
            pass
        finally:
            self._poll_id = self.root.after(100, self._poll)

    def _handle_event(self, event: BuildEvent) -> None:
        if event.kind == "log":
            tag = None
            if event.message.startswith("error:") or "FAIL" in event.message:
                tag = "error"
            elif "PASS" in event.message:
                tag = "success"
            self._append_log(event.message, tag=tag)
            return

        if event.kind == "site":
            self._set_status("Site built. Starting preview…")
            return

        if event.kind == "preview":
            self.preview_url = str(event.data.get("url") or "")
            self._building = False
            self._preview_running = bool(self.preview_url)
            self._refresh_controls()
            if self.preview_url:
                self._set_status(f"Preview running at {self.preview_url}")
                self._append_log("Preview server started.", tag="preview")
                if not self._auto_open_preview:
                    self._auto_open_preview = True
                    self.root.after(100, self._open_preview_async)
            else:
                self._set_status("Preview unavailable.")
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
                self._set_status(f"Preview running at {self.preview_url}")
            else:
                site = str(event.data.get("site") or "")
                self._set_status("Conversion complete." + (f" Site: {site}" if site else ""))
                self._append_log("Conversion complete.", tag="success")
            return

        if event.kind == "failure":
            self._building = False
            self._preview_running = False
            self.preview_url = None
            self._refresh_controls()
            message = event.message or "Conversion failed."
            self._set_status(message)
            self._append_log(message, tag="error")
            report = str(event.data.get("report") or "")
            detail = message
            if report:
                detail += f"\n\nSupport report:\n{report}"
            messagebox.showerror(APP_TITLE, detail)
            return

        if event.kind == "stopped":
            self._building = False
            self._preview_running = False
            self.preview_url = None
            self._refresh_controls()
            self._set_status("Stopped.")
            self._append_log(event.message or "Stopped.")

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
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.grid_remove()

    # -- log --------------------------------------------------------------
    def _reset_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

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

    def _set_status(self, text: str) -> None:
        self.status_var.set(text)

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
