"""Persistent per-URL, per-format download state."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path


class DownloadHistory:
    def __init__(self, path: Path):
        self.path = path
        self.entries = self._load()

    def should_download(self, url: str, media_format: str) -> bool:
        record = self.entries.get(url, {}).get("formats", {}).get(media_format, {})
        output = record.get("output_path")
        return not (record.get("status") == "succeeded" and output and Path(output).is_file())

    def record_discovered(self, url: str) -> None:
        self.entries.setdefault(url, {"formats": {}, "discovered_at": _now()})
        self._save()

    def mark_success(self, url: str, media_format: str, output_path: Path) -> None:
        entry = self.entries.setdefault(url, {"formats": {}, "discovered_at": _now()})
        entry["formats"][media_format] = {
            "status": "succeeded", "output_path": str(output_path), "error": None, "updated_at": _now(),
        }
        self._save()

    def mark_failed(self, url: str, media_format: str, error: str) -> None:
        entry = self.entries.setdefault(url, {"formats": {}, "discovered_at": _now()})
        entry["formats"][media_format] = {
            "status": "failed", "output_path": None, "error": error[:500], "updated_at": _now(),
        }
        self._save()

    def _load(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.entries, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
