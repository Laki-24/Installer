import unittest

from metadata import extract_metadata


class MetadataExtractionTests(unittest.TestCase):
    def test_normalizes_yt_dlp_fields_into_common_and_music_metadata(self):
        metadata = extract_metadata({
            "title": "  Example Song  ",
            "uploader": "Example Channel",
            "description": "  A description. ",
            "upload_date": "20260912",
            "release_date": "2026-09-01",
            "genres": ["Rock", "", "Rock"],
            "categories": ["Music"],
            "language": "en",
            "webpage_url": "https://example.test/watch?v=1",
            "thumbnails": [
                {"url": "https://example.test/small.jpg", "width": 120, "height": 90},
                {"url": "https://example.test/large.jpg", "width": 1280, "height": 720},
            ],
            "artist": "Example Artist",
            "album": "Example Album",
            "track_number": "2",
            "disc_number": 1,
        })

        self.assertEqual(metadata.title, "Example Song")
        self.assertEqual(metadata.creator, "Example Channel")
        self.assertEqual(metadata.upload_date, "2026-09-12")
        self.assertEqual(metadata.genres, ("Rock",))
        self.assertEqual(metadata.artwork.url, "https://example.test/large.jpg")
        self.assertEqual(metadata.music.artist, "Example Artist")
        self.assertEqual(metadata.music.track_number, 2)

    def test_missing_and_invalid_values_are_safe(self):
        metadata = extract_metadata({
            "title": "   ",
            "upload_date": "not-a-date",
            "track_number": 0,
            "thumbnails": [{"url": " "}],
        })

        self.assertIsNone(metadata.title)
        self.assertIsNone(metadata.upload_date)
        self.assertIsNone(metadata.artwork)
        self.assertIsNone(metadata.music)


if __name__ == "__main__":
    unittest.main()
