import unittest
from pathlib import Path
from unittest.mock import patch

from history import DownloadHistory


class DownloadHistoryTests(unittest.TestCase):
    def test_success_is_skipped_only_when_its_output_still_exists(self):
        history = DownloadHistory(Path("tests/history-test-does-not-exist.json"))
        with patch.object(history, "_save"):
            history.record_discovered("https://example.test/a")
            history.mark_success("https://example.test/a", "mp3", Path("Downloads/song.mp3"))
        with patch("history.Path.is_file", return_value=True):
            self.assertFalse(history.should_download("https://example.test/a", "mp3"))
        with patch("history.Path.is_file", return_value=False):
            self.assertTrue(history.should_download("https://example.test/a", "mp3"))
        self.assertTrue(history.should_download("https://example.test/a", "mp4"))

    def test_failed_items_are_retried(self):
        history = DownloadHistory(Path("tests/history-test-does-not-exist.json"))
        with patch.object(history, "_save"):
            history.mark_failed("https://example.test/fail", "mp3", "network error")
            self.assertTrue(history.should_download("https://example.test/fail", "mp3"))
