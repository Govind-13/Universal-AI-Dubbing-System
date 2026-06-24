import json
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.translation_validation_service import (
    TranslationValidationError,
    validate_translation_json,
    validate_translation_payload,
)


class TranslationValidationServiceTests(unittest.TestCase):
    def setUp(self):
        self.source_segments = [
            {
                "id": 1,
                "start": 1.2,
                "end": 3.4,
                "text": "Euler theorem.",
                "speaker": {"id": "speaker_0", "name": "Speaker 0"},
                "words": [
                    {"text": "Euler", "start_time": 1.2, "end_time": 1.8}
                ],
            },
            {
                "id": 2,
                "start": 3.4,
                "end": 4.2,
                "text": "[outro jingle]",
                "words": [
                    {
                        "text": "[outro jingle]",
                        "start_time": 3.4,
                        "end_time": 4.2,
                    }
                ],
            },
        ]

    def valid_payload(self):
        return {
            "type": "translated_transcript",
            "target_language": "ta",
            "segments": [
                {
                    "id": 1,
                    "start": 1.2,
                    "end": 3.4,
                    "original_text": "Euler theorem.",
                    "translated_text": "Euler theorem பற்றி பார்க்கலாம்.",
                    "text": "Euler theorem பற்றி பார்க்கலாம்.",
                    "speaker": {"id": "speaker_0", "name": "Speaker 0"},
                    "source_words": [
                        {"text": "Euler", "start_time": 1.2, "end_time": 1.8}
                    ],
                },
                {
                    "id": 2,
                    "start": 3.4,
                    "end": 4.2,
                    "original_text": "[outro jingle]",
                    "translated_text": "",
                    "text": "",
                    "source_words": [
                        {
                            "text": "[outro jingle]",
                            "start_time": 3.4,
                            "end_time": 4.2,
                        }
                    ],
                },
            ],
        }

    def test_valid_translation_passes_before_audio(self):
        result = validate_translation_payload(
            self.valid_payload(), self.source_segments, "ta"
        )

        self.assertTrue(result["valid"])
        self.assertEqual(result["segment_count"], 2)

    def test_empty_spoken_translation_is_rejected(self):
        payload = self.valid_payload()
        payload["segments"][0]["translated_text"] = "(empty source — nothing to translate)"
        payload["segments"][0]["text"] = "(empty)"

        with self.assertRaisesRegex(
            TranslationValidationError, "translation is empty"
        ):
            validate_translation_payload(payload, self.source_segments, "ta")

    def test_changed_timeline_is_rejected(self):
        payload = self.valid_payload()
        payload["segments"][0]["end"] = 4.0

        with self.assertRaisesRegex(TranslationValidationError, "end timestamp changed"):
            validate_translation_payload(payload, self.source_segments, "ta")

    def test_changed_source_metadata_is_rejected(self):
        payload = self.valid_payload()
        payload["segments"][0]["original_text"] = "Modified source"

        with self.assertRaisesRegex(
            TranslationValidationError, "source text was modified"
        ):
            validate_translation_payload(payload, self.source_segments, "ta")

    def test_unresolved_placeholder_is_rejected(self):
        payload = self.valid_payload()
        payload["segments"][0]["translated_text"] = "AUTOTERM1TOKEN"
        payload["segments"][0]["text"] = "ஆட்டோடெர்ம்1டோக்கன்"

        with self.assertRaisesRegex(
            TranslationValidationError, "unresolved placeholder"
        ):
            validate_translation_payload(payload, self.source_segments, "ta")

    def test_json_file_is_parsed_and_verified(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "translated.json"
            path.write_text(
                json.dumps(self.valid_payload(), ensure_ascii=False),
                encoding="utf-8",
            )

            result = validate_translation_json(path, self.source_segments, "ta")

        self.assertTrue(result["valid"])


if __name__ == "__main__":
    unittest.main()
