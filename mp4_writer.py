"""MP4 container metadata mapping and writing."""

from __future__ import annotations

from pathlib import Path

from metadata import MediaMetadata
from mp3_writer import fetch_artwork


def mp4_values(metadata: MediaMetadata) -> dict[str, object]:
    music = metadata.music
    tags: dict[str, object] = {
        "\xa9nam": metadata.title,
        "\xa9ART": (music.artist if music and music.artist else metadata.creator),
        "aART": music.album_artist if music else None,
        "\xa9alb": music.album if music else None,
        "\xa9gen": "; ".join(metadata.genres) or None,
        "\xa9day": metadata.release_date or metadata.upload_date,
        "\xa9cmt": metadata.description,
        "cprt": metadata.copyright,
        "\xa9grp": "; ".join(metadata.categories) or None,
        "----:com.apple.iTunes:LANGUAGE": metadata.language,
        "----:com.apple.iTunes:LICENSE": metadata.license,
        "----:com.apple.iTunes:SOURCE_URL": metadata.source_url,
    }
    if music and music.track_number:
        tags["trkn"] = [(music.track_number, 0)]
    if music and music.disc_number:
        tags["disk"] = [(music.disc_number, 0)]
    if music and music.composer:
        tags["\xa9wrt"] = music.composer
    return {key: value for key, value in tags.items() if value not in (None, "")}


def embed_mp4(path: Path, metadata: MediaMetadata) -> None:
    try:
        from mutagen.mp4 import MP4, MP4Cover
    except ImportError as error:
        raise RuntimeError("Metadata embedding requires mutagen; install requirements.txt") from error

    media = MP4(path)
    if media.tags is None:
        media.add_tags()
    media.tags.update(mp4_values(metadata))
    artwork = fetch_artwork(metadata)
    if artwork:
        mime, data = artwork
        image_format = MP4Cover.FORMAT_PNG if mime == "image/png" else MP4Cover.FORMAT_JPEG
        media.tags["covr"] = [MP4Cover(data, imageformat=image_format)]
    media.save()
