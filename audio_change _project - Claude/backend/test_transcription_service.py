import json
import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.transcription_service import normalize_stt_result


class TranscriptionServiceTests(unittest.TestCase):
    def test_elevenlabs_words_are_preserved_in_detailed_segments(self):
        fixture = json.loads(
            (BACKEND_DIR / "test_elevenlabs_stt_response.json").read_text(
                encoding="utf-8"
            )
        )

        result = normalize_stt_result(fixture, provider="elevenlabs")

        self.assertEqual(result["provider"], "elevenlabs")
        self.assertEqual(result["language"], "en")
        self.assertEqual(result["language_code"], "eng")
        self.assertTrue(result["segments"])
        self.assertTrue(result["segments"][0]["words"])
        self.assertIn("start_time", result["segments"][0]["words"][0])
        self.assertIn("end_time", result["segments"][0]["words"][0])

    def test_existing_detailed_segments_keep_speaker_and_timestamps(self):
        result = normalize_stt_result(
            {
                "language_code": "eng",
                "segments": [
                    {
                        "text": "Euler theorem.",
                        "start_time": 1.2,
                        "end_time": 2.7,
                        "speaker": {"id": "speaker_0", "name": "Speaker 0"},
                        "words": [
                            {
                                "text": "Euler",
                                "start_time": 1.2,
                                "end_time": 1.8,
                            }
                        ],
                    }
                ],
            },
            provider="elevenlabs",
        )

        segment = result["segments"][0]
        self.assertEqual(segment["start"], 1.2)
        self.assertEqual(segment["end"], 2.7)
        self.assertEqual(segment["speaker"]["id"], "speaker_0")
        self.assertEqual(segment["words"][0]["start_time"], 1.2)


if __name__ == "__main__":
    unittest.main()
