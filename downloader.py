"""Per-item yt-dlp download pipeline shared by MP3 and MP4 workflows."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
from threading import Event
from typing import Callable

from metadata import MediaMetadata, extract_metadata
from mp3_writer import embed_mp3
from mp4_writer import embed_mp4


ProgressCallback = Callable[[str, str], None]


@dataclass(frozen=True, slots=True)
class DownloadResult:
    output_path: Path
    metadata: MediaMetadata


def choose_work_items(mode: str, input_url: str, playlist_urls: list[str], history, media_format: str) -> list[str]:
    """Apply mode-specific queue rules without coupling single URLs to playlist history."""
    if mode == "single":
        return [input_url]
    if mode != "playlist":
        raise ValueError(f"Unsupported input mode: {mode}")
    return [url for url in playlist_urls if history.should_download(url, media_format)]


class MediaDownloader:
    def __init__(self, ytdlp: Path, ffmpeg_dir: Path):
        self.ytdlp = ytdlp
        self.ffmpeg_dir = ffmpeg_dir
        self.current_process: subprocess.Popen | None = None

    def resolve_playlist(self, url: str) -> list[str]:
        result = self._run([str(self.ytdlp), "--flat-playlist", "--print", "webpage_url", url])
        if result.returncode:
            raise RuntimeError(_error_text(result.stderr, "Unable to read playlist"))
        return list(dict.fromkeys(line.strip() for line in result.stdout.splitlines() if line.strip()))

    def download(self, url: str, media_format: str, output_dir: Path, cancel: Event, progress: ProgressCallback) -> DownloadResult:
        progress("Inspecting media information...", url)
        metadata = self._metadata_for(url)
        if cancel.is_set():
            raise InterruptedError("Download cancelled")
        output_dir.mkdir(parents=True, exist_ok=True)
        template = str(output_dir / "%(title)s.%(ext)s")
        command = [str(self.ytdlp), "--no-playlist", "--ffmpeg-location", str(self.ffmpeg_dir), "--no-overwrites",
                   "--newline", "--print", "after_move:filepath", "-o", template]
        if media_format == "mp3":
            command += ["-x", "--audio-format", "mp3", "--audio-quality", "0"]
        elif media_format == "mp4":
            command += ["-f", "bv*+ba/b", "--merge-output-format", "mp4"]
        else:
            raise ValueError(f"Unsupported format: {media_format}")
        command.append(url)

        progress("Downloading media...", url)
        output = self._stream(command, cancel, progress)
        if cancel.is_set():
            raise InterruptedError("Download cancelled")
        output_path = _output_path(output, output_dir, media_format)
        if not output_path.is_file():
            raise RuntimeError("yt-dlp did not produce an output file")
        progress("Embedding metadata and artwork...", str(output_path.name))
        if media_format == "mp3":
            embed_mp3(output_path, metadata)
        else:
            embed_mp4(output_path, metadata)
        return DownloadResult(output_path, metadata)

    def cancel_current(self) -> None:
        if self.current_process and self.current_process.poll() is None:
            self.current_process.terminate()

    def _metadata_for(self, url: str) -> MediaMetadata:
        result = self._run([str(self.ytdlp), "--no-playlist", "--dump-single-json", url])
        if result.returncode:
            raise RuntimeError(_error_text(result.stderr, "Unable to read media metadata"))
        try:
            info = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise RuntimeError("yt-dlp returned invalid metadata") from error
        if not isinstance(info, dict):
            raise RuntimeError("yt-dlp returned metadata in an unexpected format")
        return extract_metadata(info)

    def _stream(self, command: list[str], cancel: Event, progress: ProgressCallback) -> str:
        startupinfo = _startupinfo()
        self.current_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                                encoding="utf-8", errors="replace", startupinfo=startupinfo)
        lines: list[str] = []
        assert self.current_process.stdout is not None
        for line in self.current_process.stdout:
            lines.append(line.rstrip())
            if "% of" in line:
                progress(line.strip(), "")
            if cancel.is_set():
                self.cancel_current()
        return_code = self.current_process.wait()
        self.current_process = None
        if cancel.is_set():
            raise InterruptedError("Download cancelled")
        if return_code:
            raise RuntimeError(_error_text("\n".join(lines), "yt-dlp download failed"))
        return "\n".join(lines)

    def _run(self, command: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", startupinfo=_startupinfo())


def _output_path(output: str, output_dir: Path, media_format: str) -> Path:
    paths = [Path(line.strip()) for line in output.splitlines() if line.strip().lower().endswith(f".{media_format}")]
    if paths:
        return paths[-1]
    # Never guess an existing filename: a skipped --no-overwrites item must not be retagged.
    return output_dir / f"unknown.{media_format}"


def _error_text(text: str, fallback: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1][:500] if lines else fallback


def _startupinfo():
    if os.name != "nt":
        return None
    info = subprocess.STARTUPINFO()
    info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return info
