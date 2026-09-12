import unittest
from pathlib import Path

from downloader import _output_path, choose_work_items


class DownloaderHelpersTests(unittest.TestCase):
    def test_output_path_uses_printed_format_specific_path(self):
        expected = Path("Downloads/title.mp4")
        result = _output_path(f"log line\n{expected}\n", Path("Downloads"), "mp4")
        self.assertEqual(result, expected)

    def test_single_mode_bypasses_playlist_history(self):
        class NeverDownload:
            def should_download(self, url, media_format):
                raise AssertionError("single mode must not consult playlist history")

        self.assertEqual(
            choose_work_items("single", "https://example.test/video", [], NeverDownload(), "mp4"),
            ["https://example.test/video"],
        )

    def test_playlist_mode_uses_the_selected_format(self):
        class History:
            def __init__(self): self.calls = []
            def should_download(self, url, media_format): self.calls.append((url, media_format)); return media_format == "mp4"

        history = History()
        self.assertEqual(choose_work_items("playlist", "playlist", ["a", "b"], history, "mp4"), ["a", "b"])
        self.assertEqual(history.calls, [("a", "mp4"), ("b", "mp4")])
