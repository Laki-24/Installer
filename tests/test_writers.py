import unittest

from metadata import Artwork, MediaMetadata, MusicMetadata
from mp3_writer import id3_values
from mp4_writer import mp4_values


class MetadataWriterMappingTests(unittest.TestCase):
    def setUp(self):
        self.metadata = MediaMetadata(
            title="Example", creator="Uploader", description="Description", upload_date="2026-09-12",
            genres=("Rock",), categories=("Music",), language="en", artwork=Artwork("https://example.test/cover.jpg"),
            source_url="https://example.test/watch", copyright="Copyright", license="CC BY",
            music=MusicMetadata(artist="Artist", album="Album", album_artist="Album Artist", track_number=2, disc_number=1, composer="Composer"),
        )

    def test_mp3_mapping_uses_standard_id3_fields(self):
        tags = id3_values(self.metadata)
        self.assertEqual(tags["TIT2"], "Example")
        self.assertEqual(tags["TPE1"], "Artist")
        self.assertEqual(tags["TRCK"], "2")
        self.assertEqual(tags["TCON"], "Rock")

    def test_mp4_mapping_keeps_general_fields_without_inventing_music_fields(self):
        tags = mp4_values(self.metadata)
        self.assertEqual(tags["©nam"], "Example")
        self.assertEqual(tags["©ART"], "Artist")
        self.assertEqual(tags["trkn"], [(2, 0)])
        video_tags = mp4_values(MediaMetadata(title="Video", creator="Uploader", categories=("Education",)))
        self.assertEqual(video_tags["©ART"], "Uploader")
        self.assertNotIn("©alb", video_tags)
        self.assertNotIn("trkn", video_tags)

