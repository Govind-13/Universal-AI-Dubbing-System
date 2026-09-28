import json
import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.transcription_service import normalize_stt_result, _segments_from_full_stops


def _word(text, start, end, word_type="word"):
    return {"text": text, "start_time": start, "end_time": end, "type": word_type}


def _sentence_words(sentence, start=0.0, per_char=0.05):
    """Build a flat word+spacing list (matching the real STT word convention)
    for a plain sentence, ending the last token exactly as given."""
    tokens = sentence.split(" ")
    words = []
    t = start
    for index, tok in enumerate(tokens):
        dur = 0.2 + per_char * len(tok)
        words.append(_word(tok, t, t + dur))
        t += dur
        if index < len(tokens) - 1:
            words.append(_word(" ", t, t + 0.05, word_type="spacing"))
            t += 0.05
    return words


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
        # Final segmentation is always derived from the word-level array
        # (dot-based regrouping), so the words array must be complete/
        # consistent with the segment's text for this test to reflect
        # real usage.
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
                            {"text": "Euler", "start_time": 1.2, "end_time": 1.8, "type": "word"},
                            {"text": " ", "start_time": 1.8, "end_time": 1.9, "type": "spacing"},
                            {"text": "theorem.", "start_time": 1.9, "end_time": 2.7, "type": "word"},
                        ],
                    }
                ],
            },
            provider="elevenlabs",
        )

        segment = result["segments"][0]
        self.assertEqual(segment["start"], 1.2)
        self.assertEqual(segment["end"], 2.7)
        self.assertEqual(segment["text"], "Euler theorem.")
        self.assertEqual(segment["speaker"]["id"], "speaker_0")
        self.assertEqual(segment["words"][0]["start_time"], 1.2)


class DotBasedSegmentationTests(unittest.TestCase):
    def test_splits_only_at_literal_full_stop(self):
        words = _sentence_words("Hello there. How are you.")
        segments = _segments_from_full_stops(words)
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0]["text"], "Hello there.")
        self.assertEqual(segments[1]["text"], "How are you.")
        self.assertEqual(segments[0]["id"], 1)
        self.assertEqual(segments[1]["id"], 2)

    def test_never_splits_on_exclamation_or_question_mark(self):
        words = _sentence_words("Wait! Is this correct? Yes it is.")
        segments = _segments_from_full_stops(words)
        # only one real '.' in the whole sentence -> exactly one segment
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0]["text"], "Wait! Is this correct? Yes it is.")

    def test_long_sentence_that_used_to_force_split_stays_one_segment(self):
        # 26 words, no internal '.' until the very end -- previously this
        # would have force-split at word_count>=24 in _segments_from_words.
        long_sentence = " ".join(["word"] * 26) + "."
        words = _sentence_words(long_sentence)
        segments = _segments_from_full_stops(words)
        self.assertEqual(len(segments), 1)
        self.assertTrue(segments[0]["text"].endswith("."))

    def test_long_duration_that_used_to_force_split_stays_one_segment(self):
        # Force each word to take a long time (duration >= 12.0s old threshold)
        # but with no internal '.' -- must still remain one segment.
        words = _sentence_words("This is a long slow sentence today.", per_char=3.0)
        self.assertGreaterEqual(words[-1]["end_time"] - words[0]["start_time"], 12.0)
        segments = _segments_from_full_stops(words)
        self.assertEqual(len(segments), 1)

    def test_reproduces_the_original_reported_example(self):
        sentence = ("The problem given here is find the characteristic equation "
                    "of A is equal to one, two, minus three, four.")
        words = _sentence_words(sentence)
        segments = _segments_from_full_stops(words)
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0]["text"], sentence)

    def test_start_end_come_from_real_word_timestamps(self):
        words = _sentence_words("Timing check here.", start=5.5)
        segments = _segments_from_full_stops(words)
        self.assertEqual(segments[0]["start"], words[0]["start_time"])
        self.assertEqual(segments[0]["end"], words[-1]["end_time"])

    def test_leading_and_trailing_audio_event_words_stripped_before_grouping(self):
        marker_start = [_word("[on-hold music]", 0.0, 1.0, word_type="audio_event")]
        marker_end = [_word("[on-hold music]", 20.0, 21.0, word_type="audio_event")]
        speech = _sentence_words("Real speech content here.", start=1.5)
        words = marker_start + speech + marker_end

        segments = _segments_from_full_stops(words)
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0]["text"], "Real speech content here.")
        self.assertNotIn("[on-hold music]", segments[0]["text"])

    def test_trailing_words_with_no_closing_period_still_flushed(self):
        words = _sentence_words("First sentence.") + _sentence_words("no closing punctuation here", start=10.0)
        segments = _segments_from_full_stops(words)
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[1]["text"], "no closing punctuation here")

    def test_empty_word_list(self):
        self.assertEqual(_segments_from_full_stops([]), [])

    def test_all_audio_event_words_produces_no_segments(self):
        words = [_word("[on-hold music]", 0.0, 1.0, word_type="audio_event")]
        self.assertEqual(_segments_from_full_stops(words), [])

    def test_ids_are_sequential_from_one(self):
        words = _sentence_words("One. Two. Three.")
        segments = _segments_from_full_stops(words)
        self.assertEqual([s["id"] for s in segments], list(range(1, len(segments) + 1)))


if __name__ == "__main__":
    unittest.main()
