"""ID3 mapping and writing for downloaded MP3 files."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from metadata import MediaMetadata


def id3_values(metadata: MediaMetadata) -> dict[str, str]:
    """Return the compatible ID3 text fields, useful for tests and diagnostics."""
    music = metadata.music
    return {
        "TIT2": metadata.title,
        "TPE1": music.artist if music else None,
        "TPE2": music.album_artist if music else None,
        "TALB": music.album if music else None,
        "TRCK": str(music.track_number) if music and music.track_number else None,
        "TPOS": str(music.disc_number) if music and music.disc_number else None,
        "TCOM": music.composer if music else None,
        "TCON": "; ".join(metadata.genres) or None,
        "TDRC": metadata.release_date or metadata.upload_date,
        "COMM": metadata.description,
        "USLT": music.lyrics if music else None,
    }


def embed_mp3(path: Path, metadata: MediaMetadata) -> None:
    """Write broadly compatible ID3v2.3 tags and optional front-cover artwork."""
    try:
        from mutagen.id3 import APIC, COMM, ID3, ID3NoHeaderError, TCOM, TCON, TDRC, TALB, TIT2, TPE1, TPE2, TPOS, TRCK, USLT
    except ImportError as error:
        raise RuntimeError("Metadata embedding requires mutagen; install requirements.txt") from error

    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        tags = ID3()
    frames: dict[str, Any] = {"TIT2": TIT2, "TPE1": TPE1, "TPE2": TPE2, "TALB": TALB, "TRCK": TRCK,
                              "TPOS": TPOS, "TCOM": TCOM, "TCON": TCON, "TDRC": TDRC}
    for key, value in id3_values(metadata).items():
        if value and key in frames:
            tags.delall(key)
            tags.add(frames[key](encoding=3, text=value))
    if metadata.description:
        tags.delall("COMM")
        tags.add(COMM(encoding=3, lang="eng", desc="", text=metadata.description))
    if metadata.music and metadata.music.lyrics:
        tags.delall("USLT")
        tags.add(USLT(encoding=3, lang="eng", desc="", text=metadata.music.lyrics))
    artwork = fetch_artwork(metadata)
    if artwork:
        mime, data = artwork
        tags.delall("APIC")
        tags.add(APIC(encoding=3, mime=mime, type=3, desc="Front cover", data=data))
    tags.save(path, v2_version=3)


def fetch_artwork(metadata: MediaMetadata) -> tuple[str, bytes] | None:
    if not metadata.artwork:
        return None
    request = Request(metadata.artwork.url, headers={"User-Agent": "AudioArchiver/1.0"})
    try:
        with urlopen(request, timeout=20) as response:
            data = response.read()
            content_type = response.headers.get_content_type()
    except OSError:
        return None
    if not data:
        return None
    if data.startswith(b"\x89PNG"):
        return "image/png", data
    if data.startswith(b"\xff\xd8"):
        return "image/jpeg", data
    return (content_type if content_type.startswith("image/") else "image/jpeg"), data
