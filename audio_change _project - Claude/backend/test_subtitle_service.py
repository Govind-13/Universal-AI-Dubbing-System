import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.subtitle_service import build_srt_content


class SubtitleServiceTests(unittest.TestCase):
    def test_build_srt_content_renders_segments_with_timestamps(self):
        content = build_srt_content(
            [
                {"start": 0.0, "end": 1.25, "text": "Vanakkam students."},
                {"start": 1.25, "end": 3.5, "text": "Inniki namma fractions paakalam."},
            ]
        )

        self.assertEqual(
            content,
            (
                "1\n"
                "00:00:00,000 --> 00:00:01,250\n"
                "Vanakkam students.\n\n"
                "2\n"
                "00:00:01,250 --> 00:00:03,500\n"
                "Inniki namma fractions paakalam.\n"
            ),
        )

    def test_build_srt_content_returns_empty_string_for_no_segments(self):
        self.assertEqual(build_srt_content([]), "")

    def test_build_srt_content_skips_empty_segments(self):
        content = build_srt_content(
            [
                {"start": 0.0, "end": 1.0, "text": ""},
                {"start": 1.0, "end": 2.0, "text": "Spoken text"},
            ]
        )

        self.assertEqual(
            content,
            "1\n00:00:01,000 --> 00:00:02,000\nSpoken text\n",
        )


if __name__ == "__main__":
    unittest.main()
