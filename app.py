import sys
import os
import re
import urllib.request
import zipfile
import threading
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ----------------------------------------------------------------------
# PATH CONSTANTS (Resolves correctly whether running as .py or compiled .exe)
# ----------------------------------------------------------------------
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

DATA_DIR = BASE_DIR / "App_Data"
BIN_DIR = DATA_DIR / "bin"
URLS_FILE = DATA_DIR / "urls.txt"
ARCHIVE_FILE = DATA_DIR / "downloaded.txt"
DEFAULT_OUTPUT = BASE_DIR / "Downloads"

DATA_DIR.mkdir(parents=True, exist_ok=True)
BIN_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_OUTPUT.mkdir(parents=True, exist_ok=True)

YTDLP_EXE = BIN_DIR / "yt-dlp.exe"
FFMPEG_EXE = BIN_DIR / "ffmpeg.exe"

# Official static binaries
YTDLP_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
FFMPEG_ZIP_URL = "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"


# ----------------------------------------------------------------------
# GUI APPLICATION
# ----------------------------------------------------------------------
class AudioDownloaderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Audio Stream Archiver")
        self.geometry("760x460")
        self.minsize(680, 400)
        self.configure(bg="#1e1e1e")

        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self._configure_styles()

        self.is_busy = False
        self._build_interface()

        # Check dependencies on startup in background
        self.after(300, self._verify_and_bootstrap_binaries)

    def _configure_styles(self):
        self.style.configure("TFrame", background="#1e1e1e")
        self.style.configure("TLabelframe", background="#1e1e1e", foreground="#ffffff", relief="flat")
        self.style.configure("TLabelframe.Label", background="#1e1e1e", foreground="#38bdf8", font=("Segoe UI", 10, "bold"))
        self.style.configure("TLabel", background="#1e1e1e", foreground="#e2e8f0", font=("Segoe UI", 9))
        self.style.configure("TButton", font=("Segoe UI", 9, "bold"), background="#0284c7", foreground="#ffffff")
        self.style.map("TButton", background=[("active", "#0369a1"), ("disabled", "#334155")])
        self.style.configure("Horizontal.TProgressbar", troughcolor="#334155", background="#38bdf8")

    def _build_interface(self):
        container = ttk.Frame(self, padding=12)
        container.pack(fill="both", expand=True)

        # Left Column: Configuration Controls
        left_panel = ttk.Frame(container, width=340)
        left_panel.pack(side="left", fill="both", expand=False, padx=(0, 10))

        # URL Input
        lbl_url = ttk.Label(left_panel, text="YouTube Playlist / Track URL:")
        lbl_url.pack(anchor="w", pady=(0, 4))
        self.url_var = tk.StringVar()
        self.url_entry = tk.Entry(left_panel, textvariable=self.url_var, bg="#2d2d2d", fg="#ffffff",
                                  insertbackground="white", relief="flat", font=("Segoe UI", 10))
        self.url_entry.pack(fill="x", ipady=6, pady=(0, 12))

        # Folder Selector
        lbl_out = ttk.Label(left_panel, text="Download Folder:")
        lbl_out.pack(anchor="w", pady=(0, 4))

        f_row = ttk.Frame(left_panel)
        f_row.pack(fill="x", pady=(0, 16))
        self.folder_var = tk.StringVar(value=str(DEFAULT_OUTPUT.resolve()))
        self.folder_entry = tk.Entry(f_row, textvariable=self.folder_var, bg="#2d2d2d", fg="#ffffff",
                                     insertbackground="white", relief="flat", font=("Segoe UI", 9))
        self.folder_entry.pack(side="left", fill="x", expand=True, ipady=5, padx=(0, 6))
        btn_browse = ttk.Button(f_row, text="Browse", command=self._browse_folder, width=8)
        btn_browse.pack(side="right")

        # Action Buttons & Status
        self.btn_run = ttk.Button(left_panel, text="Sync & Download Audio", command=self._start_workflow)
        self.btn_run.pack(fill="x", ipady=6, pady=(0, 8))

        self.progress = ttk.Progressbar(left_panel, mode="indeterminate")
        self.progress.pack(fill="x", pady=(0, 8))

        self.lbl_status = ttk.Label(left_panel, text="Ready", foreground="#94a3b8")
        self.lbl_status.pack(anchor="w")

        # Right Column: Clean Status Output Box
        right_panel = ttk.LabelFrame(container, text=" Activity & Downloads ", padding=10)
        right_panel.pack(side="right", fill="both", expand=True)

        self.log_box = tk.Text(right_panel, bg="#121212", fg="#38bdf8", font=("Consolas", 9),
                               wrap="word", relief="flat", padx=8, pady=8)
        self.log_box.pack(side="left", fill="both", expand=True)

        scroll = ttk.Scrollbar(right_panel, orient="vertical", command=self.log_box.yview)
        scroll.pack(side="right", fill="y")
        self.log_box.config(yscrollcommand=scroll.set)

    def _browse_folder(self):
        dest = filedialog.askdirectory(initialdir=self.folder_var.get())
        if dest:
            self.folder_var.set(dest)

    def _log(self, text, color=None):
        self.log_box.insert(tk.END, text + "\n")
        self.log_box.see(tk.END)

    def _set_status(self, text):
        self.lbl_status.config(text=text)

    # ------------------------------------------------------------------
    # BOOTSTRAPPER: Auto-fetch dependencies on first run
    # ------------------------------------------------------------------
    def _verify_and_bootstrap_binaries(self):
        if YTDLP_EXE.exists() and FFMPEG_EXE.exists():
            self._log("✔ System tools (yt-dlp & FFmpeg) are ready.")
            return

        self.is_busy = True
        self.btn_run.config(state="disabled")
        self.progress.start(10)
        threading.Thread(target=self._download_prerequisites, daemon=True).start()

    def _download_prerequisites(self):
        try:
            if not YTDLP_EXE.exists():
                self._log("Installing downloader core (yt-dlp)...")
                self._set_status("Downloading yt-dlp...")
                urllib.request.urlretrieve(YTDLP_URL, YTDLP_EXE)
                self._log("✔ yt-dlp installed.")

            if not FFMPEG_EXE.exists():
                self._log("Fetching audio conversion engine (FFmpeg)...")
                self._set_status("Downloading FFmpeg (~70MB)...")
                zip_path = BIN_DIR / "ffmpeg.zip"
                urllib.request.urlretrieve(FFMPEG_ZIP_URL, zip_path)

                self._log("Unpacking FFmpeg...")
                with zipfile.ZipFile(zip_path, "r") as zip_ref:
                    for member in zip_ref.namelist():
                        if member.endswith("ffmpeg.exe"):
                            source = zip_ref.open(member)
                            target = open(FFMPEG_EXE, "wb")
                            with source, target:
                                target.write(source.read())
                            break

                if zip_path.exists():
                    zip_path.unlink()
                self._log("✔ FFmpeg installed.")

            self._log("✔ Environment initialized. Ready to download.")
            self._set_status("Ready")
        except Exception as err:
            self._log(f"Setup Error: {err}")
            self._set_status("Dependency Setup Failed")
        finally:
            self.is_busy = False
            self.progress.stop()
            self.btn_run.config(state="normal")

    # ------------------------------------------------------------------
    # PIPELINE EXECUTION
    # ------------------------------------------------------------------
    def _start_workflow(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Please enter a valid URL.")
            return

        if self.is_busy:
            return

        self.is_busy = True
        self.btn_run.config(state="disabled")
        self.progress.start(10)
        threading.Thread(target=self._process_download, args=(url, self.folder_var.get()), daemon=True).start()

    def _process_download(self, target_url, output_dir):
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        try:
            # 1. Sync playlist URLs to persistent file
            self._set_status("Reading playlist URLs...")
            self._log("\n--> Fetching playlist details...")

            fetch_cmd = [
                str(YTDLP_EXE),
                "--flat-playlist",
                "--print", "webpage_url",
                target_url
            ]

            startupinfo = None
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # Hide cmd window

            res = subprocess.run(fetch_cmd, capture_output=True, text=True, encoding="utf-8", startupinfo=startupinfo)

            existing_urls = set()
            if URLS_FILE.exists():
                for line in URLS_FILE.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        existing_urls.add(line.strip())

            fresh_urls = [u.strip() for u in res.stdout.splitlines() if u.strip()]
            new_urls = [u for u in fresh_urls if u not in existing_urls]

            if new_urls:
                with URLS_FILE.open("a", encoding="utf-8") as f:
                    for u in new_urls:
                        f.write(u + "\n")
                self._log(f"Added {len(new_urls)} new item(s) to download queue.")
            else:
                self._log("No new URLs found; continuing with un-downloaded items.")

            # 2. Download and parse clean terminal outputs
            self._set_status("Downloading & converting...")
            self._log("\n--> Processing queue...")

            run_cmd = [
                str(YTDLP_EXE),
                "--ffmpeg-location", str(BIN_DIR),
                "-x",
                "--audio-format", "mp3",
                "--audio-quality", "0",
                "-a", str(URLS_FILE),
                "--download-archive", str(ARCHIVE_FILE),
                "-o", str(out_path / "%(title)s.%(ext)s"),
                "--no-overwrites",
                "--ignore-errors",
                "--newline"
            ]

            proc = subprocess.Popen(
                run_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                startupinfo=startupinfo
            )

            # Extract clean track information rather than dumping raw logs
            title_pattern = re.compile(r"\[download\] Destination: (.+)")
            progress_pattern = re.compile(r"\[download\]\s+(\d+\.\d+)%\s+of\s+(~?\s*\d+\.\d+\w+)")

            current_song = ""
            for line in proc.stdout:
                line_str = line.strip()

                # Detect which title is downloading
                if "[download] Destination:" in line_str:
                    match = title_pattern.search(line_str)
                    if match:
                        full_name = Path(match.group(1)).name
                        current_song = full_name
                        self._log(f"\n[GETTING]: {full_name}")
                        self._set_status(f"Downloading: {full_name[:30]}...")

                # Parse percentage and file size
                elif "[download]" in line_str and "% of" in line_str:
                    prog_match = progress_pattern.search(line_str)
                    if prog_match:
                        pct, total_size = prog_match.groups()
                        self._set_status(f"{pct}% of {total_size} - {current_song[:25]}")

                # Audio conversion completion marker
                elif "[ExtractAudio] Destination:" in line_str:
                    mp3_name = Path(line_str.split("Destination: ")[-1]).name
                    self._log(f"✔ Completed: {mp3_name}")

                elif "has already been recorded in the archive" in line_str:
                    continue  # Ignore clutter

            proc.wait()
            self._log("\nAll pending tasks completed successfully!")
            self._set_status("Done")

        except Exception as e:
            self._log(f"Error: {e}")
            self._set_status("Encountered an error")
        finally:
            self.is_busy = False
            self.progress.stop()
            self.btn_run.config(state="normal")


if __name__ == "__main__":
    app = AudioDownloaderApp()
    app.mainloop()