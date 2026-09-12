"""Tkinter front end for authorized media downloads."""

from __future__ import annotations

from pathlib import Path
from queue import Empty, Queue
import sys
import threading
from threading import Event
import urllib.request
import zipfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from downloader import MediaDownloader, choose_work_items
from history import DownloadHistory

BASE_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
DATA_DIR = BASE_DIR / "App_Data"
BIN_DIR = DATA_DIR / "bin"
URLS_FILE = DATA_DIR / "urls.txt"
HISTORY_FILE = DATA_DIR / "download_history.json"
DEFAULT_OUTPUT = BASE_DIR / "Downloads"
YTDLP_EXE = BIN_DIR / "yt-dlp.exe"
FFMPEG_EXE = BIN_DIR / "ffmpeg.exe"
YTDLP_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
FFMPEG_ZIP_URL = "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"


class AudioDownloaderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        BIN_DIR.mkdir(parents=True, exist_ok=True)
        DEFAULT_OUTPUT.mkdir(parents=True, exist_ok=True)
        self.title("AudioArchiver")
        self.geometry("900x530")
        self.minsize(780, 480)
        self.configure(bg="#1e1e1e")
        self.ui_events: Queue[tuple[str, tuple]] = Queue()
        self.cancel_event = Event()
        self.active_downloader: MediaDownloader | None = None
        self.is_busy = False
        self.mode_var = tk.StringVar(value="playlist")
        self.format_var = tk.StringVar(value="mp3")
        self.url_var = tk.StringVar()
        self.folder_var = tk.StringVar(value=str(DEFAULT_OUTPUT.resolve()))
        self.status_var = tk.StringVar(value="Ready")
        self.current_var = tk.StringVar(value="—")
        self.progress_var = tk.StringVar(value="0 / 0")
        self.pending_var = tk.StringVar(value="0")
        self.completed_var = tk.StringVar(value="0")
        self.failed_var = tk.StringVar(value="0")
        self._configure_styles()
        self._build_interface()
        self.after(75, self._drain_ui_events)
        self.after(250, self._verify_and_bootstrap_binaries)

    def _configure_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#1e1e1e")
        style.configure("TLabelframe", background="#1e1e1e", foreground="#ffffff")
        style.configure("TLabelframe.Label", background="#1e1e1e", foreground="#38bdf8", font=("Segoe UI", 10, "bold"))
        style.configure("TLabel", background="#1e1e1e", foreground="#e2e8f0", font=("Segoe UI", 9))
        style.configure("TButton", font=("Segoe UI", 9, "bold"), background="#0284c7", foreground="#ffffff")
        style.configure("Horizontal.TProgressbar", troughcolor="#334155", background="#38bdf8")

    def _build_interface(self):
        container = ttk.Frame(self, padding=12)
        container.pack(fill="both", expand=True)
        left = ttk.Frame(container, width=410)
        left.pack(side="left", fill="both", expand=False, padx=(0, 10))
        ttk.Label(left, text="Media URL:").pack(anchor="w", pady=(0, 4))
        self.url_entry = tk.Entry(left, textvariable=self.url_var, bg="#2d2d2d", fg="#ffffff", insertbackground="white", relief="flat")
        self.url_entry.pack(fill="x", ipady=7, pady=(0, 12))
        self._toggle(left, "Input mode", self.mode_var, (("Playlist", "playlist"), ("Single Video", "single")))
        self._toggle(left, "Format", self.format_var, (("MP3", "mp3"), ("MP4", "mp4")))
        ttk.Label(left, text="Download folder:").pack(anchor="w", pady=(12, 4))
        folder_row = ttk.Frame(left)
        folder_row.pack(fill="x", pady=(0, 14))
        tk.Entry(folder_row, textvariable=self.folder_var, bg="#2d2d2d", fg="#ffffff", insertbackground="white", relief="flat").pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 6))
        ttk.Button(folder_row, text="Browse", command=self._browse_folder).pack(side="right")
        self.run_button = ttk.Button(left, text="Download", command=self._start_workflow)
        self.run_button.pack(fill="x", ipady=7, pady=(0, 7))
        self.cancel_button = ttk.Button(left, text="Cancel", command=self._cancel, state="disabled")
        self.cancel_button.pack(fill="x", ipady=7)
        ttk.Label(left, textvariable=self.status_var, foreground="#94a3b8", wraplength=385).pack(anchor="w", pady=(12, 0))
        panel = ttk.LabelFrame(container, text=" Downloads ", padding=12)
        panel.pack(side="right", fill="both", expand=True)
        for label, variable in (("Current", self.current_var), ("Progress", self.progress_var), ("Pending", self.pending_var), ("Completed", self.completed_var), ("Failed", self.failed_var), ("Status", self.status_var)):
            row = ttk.Frame(panel); row.pack(fill="x", pady=3)
            ttk.Label(row, text=f"{label}:", width=11).pack(side="left")
            ttk.Label(row, textvariable=variable, wraplength=350).pack(side="left", fill="x", expand=True)
        self.progress = ttk.Progressbar(panel, mode="determinate", maximum=1)
        self.progress.pack(fill="x", pady=(10, 10))
        self.log_box = tk.Text(panel, height=13, bg="#121212", fg="#38bdf8", font=("Consolas", 9), wrap="word", relief="flat", padx=8, pady=8)
        self.log_box.pack(fill="both", expand=True)

    def _toggle(self, parent, title, variable, choices):
        """Build a compact two-state control with explicit dark-theme hover colors."""
        ttk.Label(parent, text=title).pack(anchor="w", pady=(0, 4))
        box = tk.Frame(parent, bg="#334155", padx=2, pady=2, highlightthickness=1, highlightbackground="#475569")
        box.pack(fill="x", pady=(0, 10))
        buttons: dict[str, tk.Button] = {}
        active_bg, inactive_bg, hover_bg = "#0284c7", "#273549", "#3b4d63"

        def refresh(*_):
            selected = variable.get()
            for value, button in buttons.items():
                is_selected = value == selected
                background = active_bg if is_selected else inactive_bg
                button.configure(
                    bg=background,
                    fg="#ffffff" if is_selected else "#dbeafe",
                    activebackground=background,
                    activeforeground="#ffffff",
                    relief="sunken" if is_selected else "flat",
                )

        for label, value in choices:
            button = tk.Button(
                box,
                text=label,
                command=lambda choice=value: variable.set(choice),
                bg=inactive_bg,
                fg="#dbeafe",
                activebackground=hover_bg,
                activeforeground="#ffffff",
                bd=0,
                relief="flat",
                font=("Segoe UI", 9, "bold"),
                padx=12,
                pady=5,
                takefocus=True,
            )
            button.pack(side="left", fill="x", expand=True)
            button.bind("<Enter>", lambda event, choice=value: event.widget.configure(bg=active_bg if variable.get() == choice else hover_bg))
            button.bind("<Leave>", lambda event: refresh())
            buttons[value] = button

        variable.trace_add("write", refresh)
        refresh()

    def _browse_folder(self):
        destination = filedialog.askdirectory(initialdir=self.folder_var.get())
        if destination:
            self.folder_var.set(destination)

    def _verify_and_bootstrap_binaries(self):
        if YTDLP_EXE.exists() and FFMPEG_EXE.exists():
            self._log("System tools are ready."); return
        self.is_busy = True; self.run_button.config(state="disabled"); self._set_status("Installing required download tools...")
        threading.Thread(target=self._download_prerequisites, daemon=True).start()

    def _download_prerequisites(self):
        try:
            if not YTDLP_EXE.exists():
                self._post("status", "Downloading yt-dlp..."); urllib.request.urlretrieve(YTDLP_URL, YTDLP_EXE)
            if not FFMPEG_EXE.exists():
                self._post("status", "Downloading FFmpeg...")
                zip_path = BIN_DIR / "ffmpeg.zip"; urllib.request.urlretrieve(FFMPEG_ZIP_URL, zip_path)
                with zipfile.ZipFile(zip_path) as archive:
                    member = next((name for name in archive.namelist() if name.endswith("/ffmpeg.exe")), None)
                    if not member: raise RuntimeError("FFmpeg archive did not contain ffmpeg.exe")
                    with archive.open(member) as source, FFMPEG_EXE.open("wb") as target: target.write(source.read())
                zip_path.unlink(missing_ok=True)
            self._post("log", "System tools installed."); self._post("status", "Ready")
        except Exception as error:
            self._post("log", f"Setup error: {error}"); self._post("status", "Dependency setup failed")
        finally:
            self._post("ready")

    def _start_workflow(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Enter a playlist or single-video URL."); return
        output_dir = Path(self.folder_var.get()).expanduser()
        self.cancel_event.clear(); self.is_busy = True; self.run_button.config(state="disabled"); self.cancel_button.config(state="normal")
        self._reset_counts()
        threading.Thread(target=self._run_pipeline, args=(url, self.mode_var.get(), self.format_var.get(), output_dir), daemon=True).start()

    def _run_pipeline(self, url, mode, media_format, output_dir):
        downloader = MediaDownloader(YTDLP_EXE, BIN_DIR); self.active_downloader = downloader; history = DownloadHistory(HISTORY_FILE)
        try:
            self._post("status", "Resolving URLs...")
            if mode == "playlist":
                urls = downloader.resolve_playlist(url); self._record_discovered_urls(urls, history)
                work_items = choose_work_items(mode, url, urls, history, media_format)
            else: work_items = choose_work_items(mode, url, [], history, media_format)
            total = len(work_items); self._post("counts", 0, total, 0, total)
            if not work_items:
                self._post("log", "No new or missing playlist items need downloading."); self._post("status", "Nothing to download"); return
            completed = failed = 0
            for index, item_url in enumerate(work_items, start=1):
                if self.cancel_event.is_set(): break
                self._post("current", item_url)
                try:
                    result = downloader.download(item_url, media_format, output_dir, self.cancel_event, lambda status, current: self._post("status", status))
                    completed += 1
                    if mode == "playlist": history.mark_success(item_url, media_format, result.output_path)
                    self._post("log", f"✓ Completed: {result.output_path.name}")
                except InterruptedError:
                    self._post("log", "Cancellation requested; remaining items were not started."); break
                except Exception as error:
                    failed += 1
                    if mode == "playlist": history.mark_failed(item_url, media_format, str(error))
                    self._post("log", f"✗ Failed: {item_url} — {error}")
                self._post("counts", completed, total - index, failed, total)
            self._post("status", "Cancelled" if self.cancel_event.is_set() else "Done")
        except Exception as error:
            self._post("log", f"Error: {error}"); self._post("status", "Unable to start download")
        finally:
            self.active_downloader = None; self._post("finished")

    def _record_discovered_urls(self, urls, history):
        existing = set(URLS_FILE.read_text(encoding="utf-8").splitlines()) if URLS_FILE.exists() else set(); new_urls = []
        for item_url in urls:
            history.record_discovered(item_url)
            if item_url not in existing: new_urls.append(item_url); existing.add(item_url)
        if new_urls:
            with URLS_FILE.open("a", encoding="utf-8") as handle: handle.write("".join(f"{item_url}\n" for item_url in new_urls))
            self._post("log", f"Discovered {len(new_urls)} new playlist item(s).")

    def _cancel(self):
        self.cancel_event.set()
        if self.active_downloader: self.active_downloader.cancel_current()
        self._set_status("Cancelling after the current operation...")

    def _post(self, kind, *values): self.ui_events.put((kind, values))

    def _drain_ui_events(self):
        try:
            while True:
                kind, values = self.ui_events.get_nowait()
                if kind == "status": self._set_status(values[0])
                elif kind == "log": self._log(values[0])
                elif kind == "current": self.current_var.set(values[0])
                elif kind == "counts": self._set_counts(*values)
                elif kind in ("finished", "ready"):
                    self.is_busy = False; self.run_button.config(state="normal"); self.cancel_button.config(state="disabled")
        except Empty: pass
        self.after(75, self._drain_ui_events)

    def _reset_counts(self): self._set_counts(0, 0, 0, 0); self.current_var.set("—")
    def _set_counts(self, completed, pending, failed, total):
        self.completed_var.set(str(completed)); self.pending_var.set(str(pending)); self.failed_var.set(str(failed)); self.progress_var.set(f"{completed + failed} / {total}")
        self.progress.configure(maximum=max(total, 1), value=completed + failed)
    def _set_status(self, text): self.status_var.set(text)
    def _log(self, text): self.log_box.insert(tk.END, text + "\n"); self.log_box.see(tk.END)


if __name__ == "__main__":
    AudioDownloaderApp().mainloop()
