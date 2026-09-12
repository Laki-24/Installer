"""Container-neutral metadata extracted from yt-dlp information dictionaries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class Artwork:
    """A remotely available image suitable for later container-specific embedding."""

    url: str
    width: int | None = None
    height: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"url": self.url, "width": self.width, "height": self.height}


@dataclass(frozen=True, slots=True)
class MusicMetadata:
    """Metadata meaningful for music releases, independent of an audio format."""

    artist: str | None = None
    album: str | None = None
    album_artist: str | None = None
    track_number: int | None = None
    disc_number: int | None = None
    composer: str | None = None
    lyrics: str | None = None

    def is_empty(self) -> bool:
        return all(value is None for value in self.to_dict().values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "artist": self.artist,
            "album": self.album,
            "album_artist": self.album_artist,
            "track_number": self.track_number,
            "disc_number": self.disc_number,
            "composer": self.composer,
            "lyrics": self.lyrics,
        }


@dataclass(frozen=True, slots=True)
class MediaMetadata:
    """Common metadata that can later be written to audio or video containers."""

    title: str | None = None
    creator: str | None = None
    description: str | None = None
    upload_date: str | None = None
    release_date: str | None = None
    genres: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    language: str | None = None
    artwork: Artwork | None = None
    source_url: str | None = None
    copyright: str | None = None
    license: str | None = None
    music: MusicMetadata | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "creator": self.creator,
            "description": self.description,
            "upload_date": self.upload_date,
            "release_date": self.release_date,
            "genres": list(self.genres),
            "categories": list(self.categories),
            "language": self.language,
            "artwork": self.artwork.to_dict() if self.artwork else None,
            "source_url": self.source_url,
            "copyright": self.copyright,
            "license": self.license,
            "music": self.music.to_dict() if self.music else None,
        }


def extract_metadata(info: Mapping[str, Any]) -> MediaMetadata:
    """Normalize one yt-dlp information dictionary into the shared model."""
    music = MusicMetadata(
        artist=_text(info.get("artist")),
        album=_text(info.get("album")),
        album_artist=_text(info.get("album_artist")),
        track_number=_positive_int(info.get("track_number")),
        disc_number=_positive_int(info.get("disc_number")),
        composer=_text(info.get("composer")),
        lyrics=_text(info.get("lyrics")),
    )

    return MediaMetadata(
        title=_text(info.get("title")),
        creator=_first_text(info, "creator", "uploader", "channel"),
        description=_text(info.get("description")),
        upload_date=_date_value(info.get("upload_date")),
        release_date=_date_value(info.get("release_date")),
        genres=_text_values(info.get("genres") or info.get("genre")),
        categories=_text_values(info.get("categories") or info.get("category")),
        language=_text(info.get("language")),
        artwork=_artwork(info),
        source_url=_first_text(info, "webpage_url", "original_url", "url"),
        copyright=_text(info.get("copyright")),
        license=_text(info.get("license")),
        music=None if music.is_empty() else music,
    )


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _first_text(info: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = _text(info.get(key))
        if value:
            return value
    return None


def _text_values(value: Any) -> tuple[str, ...]:
    values = value if isinstance(value, (list, tuple)) else (value,)
    unique: list[str] = []
    for item in values:
        cleaned = _text(item)
        if cleaned and cleaned not in unique:
            unique.append(cleaned)
    return tuple(unique)


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
        return parsed if parsed > 0 else None
    return None


def _date_value(value: Any) -> str | None:
    raw = _text(value)
    if not raw:
        return None
    compact = re.fullmatch(r"(\d{4})(\d{2})(\d{2})", raw)
    dashed = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if not (compact or dashed):
        return None
    parts = compact.groups() if compact else dashed.groups()
    try:
        return date(*map(int, parts)).isoformat()
    except ValueError:
        return None


def _artwork(info: Mapping[str, Any]) -> Artwork | None:
    candidates = info.get("thumbnails")
    if not isinstance(candidates, list):
        candidates = []
    candidates = [candidate for candidate in candidates if isinstance(candidate, Mapping)]
    if not candidates and _text(info.get("thumbnail")):
        candidates = [{"url": info["thumbnail"]}]

    usable: list[tuple[int, Artwork]] = []
    for index, candidate in enumerate(candidates):
        url = _text(candidate.get("url"))
        if not url:
            continue
        width = _positive_int(candidate.get("width"))
        height = _positive_int(candidate.get("height"))
        area = (width or 0) * (height or 0)
        usable.append((area * 10_000 + index, Artwork(url, width, height)))
    return max(usable, default=(0, None), key=lambda item: item[0])[1]
