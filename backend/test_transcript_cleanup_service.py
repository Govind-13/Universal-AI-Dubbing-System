import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.transcript_cleanup_service import (
    is_audio_event_marker_text,
    is_removable_segment,
    clean_segments,
    strip_root_text_markers,
    clean_transcript_payload,
    parse_srt,
    build_srt,
    clean_srt_content,
)


def _speech_word(text):
    return {"text": text, "type": "word"}


def _spacing_word():
    return {"text": " ", "type": "spacing"}


def _event_word(text):
    return {"text": text, "type": "audio_event"}


class MarkerDetectionTests(unittest.TestCase):
    def test_marker_only_text_matches(self):
        self.assertTrue(is_audio_event_marker_text("[on-hold music]"))
        self.assertTrue(is_audio_event_marker_text("  [applause]  "))

    def test_real_speech_does_not_match(self):
        self.assertFalse(is_audio_event_marker_text("In this session we discuss eigenvalues."))
        self.assertFalse(is_audio_event_marker_text("[on-hold music] but then speech continues"))
        self.assertFalse(is_audio_event_marker_text("lambda [1, 2, 3] matrix"))

    def test_non_string_is_false(self):
        self.assertFalse(is_audio_event_marker_text(None))
        self.assertFalse(is_audio_event_marker_text(42))


class SegmentRemovabilityTests(unittest.TestCase):
    def test_raw_stt_shape_marker_segment_is_removable(self):
        segment = {"id": 1, "start": 0.0, "end": 1.0, "text": "[on-hold music]",
                   "words": [_event_word("[on-hold music]")]}
        self.assertTrue(is_removable_segment(segment))

    def test_raw_stt_shape_speech_segment_is_not_removable(self):
        segment = {"id": 2, "start": 1.0, "end": 3.0, "text": "In this session we discuss it.",
                   "words": [_spacing_word(), _speech_word("In"), _spacing_word(), _speech_word("this")]}
        self.assertFalse(is_removable_segment(segment))

    def test_original_transcript_shape(self):
        segment = {"id": 1, "start": 0.0, "end": 1.0, "original_text": "[on-hold music]",
                   "words": [_event_word("[on-hold music]")]}
        self.assertTrue(is_removable_segment(segment))

    def test_translated_transcript_shape_all_marker_fields(self):
        segment = {
            "id": 1, "start": 0.0, "end": 1.0,
            "original_text": "[on-hold music]",
            "translated_text": "[on-hold music]",
            "subtitle_text": "[on-hold music]",
            "text": "[on-hold music]",
            "source_words": [_event_word("[on-hold music]")],
        }
        self.assertTrue(is_removable_segment(segment))

    def test_translated_transcript_shape_mixed_fields_not_removable(self):
        # translated_text has real content even though original_text is a marker
        segment = {
            "id": 1, "start": 0.0, "end": 1.0,
            "original_text": "[on-hold music]",
            "translated_text": "music plays here",
            "subtitle_text": "music plays here",
            "text": "music plays here",
            "source_words": [_event_word("[on-hold music]")],
        }
        self.assertFalse(is_removable_segment(segment))

    def test_segment_with_no_text_fields_not_removable(self):
        self.assertFalse(is_removable_segment({"id": 1, "start": 0.0, "end": 1.0}))

    def test_segment_with_real_word_type_not_removable_even_if_text_matches(self):
        # defensive: word-level says real speech even if text field alone looks like a marker
        segment = {"id": 1, "start": 0.0, "end": 1.0, "text": "[on-hold music]",
                   "words": [_speech_word("[on-hold")]}
        self.assertFalse(is_removable_segment(segment))


class CleanSegmentsTests(unittest.TestCase):
    def _marker_seg(self, seg_id, start, end):
        return {"id": seg_id, "start": start, "end": end, "text": "[on-hold music]",
                "words": [_event_word("[on-hold music]")]}

    def _speech_seg(self, seg_id, start, end, text="Real speech content here."):
        return {"id": seg_id, "start": start, "end": end, "text": text,
                "words": [_speech_word(text)]}

    def test_leading_only_removed(self):
        segments = [self._marker_seg(1, 0.0, 1.0), self._speech_seg(2, 1.0, 3.0), self._speech_seg(3, 3.0, 5.0)]
        result = clean_segments(segments)
        self.assertEqual(len(result), 2)
        self.assertEqual([s["id"] for s in result], [1, 2])
        self.assertEqual(result[0]["start"], 1.0)
        self.assertEqual(result[0]["end"], 3.0)
        self.assertEqual(result[1]["start"], 3.0)
        self.assertEqual(result[1]["end"], 5.0)

    def test_trailing_only_removed(self):
        segments = [self._speech_seg(1, 0.0, 2.0), self._speech_seg(2, 2.0, 4.0), self._marker_seg(3, 4.0, 5.0)]
        result = clean_segments(segments)
        self.assertEqual(len(result), 2)
        self.assertEqual([s["id"] for s in result], [1, 2])

    def test_both_leading_and_trailing_removed(self):
        segments = [
            self._marker_seg(1, 0.0, 1.0),
            self._marker_seg(2, 1.0, 2.0),
            self._speech_seg(3, 2.0, 4.0),
            self._speech_seg(4, 4.0, 6.0),
            self._marker_seg(5, 6.0, 7.0),
        ]
        result = clean_segments(segments)
        self.assertEqual(len(result), 2)
        self.assertEqual([s["id"] for s in result], [1, 2])
        self.assertEqual(result[0]["start"], 2.0)
        self.assertEqual(result[1]["end"], 6.0)

    def test_middle_marker_never_removed(self):
        segments = [
            self._speech_seg(1, 0.0, 2.0),
            self._marker_seg(2, 2.0, 3.0),
            self._speech_seg(3, 3.0, 5.0),
        ]
        result = clean_segments(segments)
        self.assertEqual(len(result), 3)
        self.assertEqual([s["id"] for s in result], [1, 2, 3])
        self.assertEqual(result[1]["text"], "[on-hold music]")

    def test_all_marker_segments_all_removed(self):
        segments = [self._marker_seg(1, 0.0, 1.0), self._marker_seg(2, 1.0, 2.0)]
        result = clean_segments(segments)
        self.assertEqual(result, [])

    def test_no_removable_segments_unchanged_content(self):
        segments = [self._speech_seg(1, 0.0, 2.0), self._speech_seg(2, 2.0, 4.0)]
        result = clean_segments(segments)
        self.assertEqual(len(result), 2)
        self.assertEqual([s["id"] for s in result], [1, 2])

    def test_empty_list(self):
        self.assertEqual(clean_segments([]), [])

    def test_timestamps_never_shifted(self):
        segments = [self._marker_seg(1, 0.0, 1.5), self._speech_seg(2, 1.5, 9.75)]
        result = clean_segments(segments)
        self.assertEqual(result[0]["start"], 1.5)
        self.assertEqual(result[0]["end"], 9.75)


class RootTextStripTests(unittest.TestCase):
    def test_leading_and_trailing_stripped(self):
        text = "[on-hold music] In this session we discuss eigenvalues. [on-hold music]"
        self.assertEqual(strip_root_text_markers(text), "In this session we discuss eigenvalues.")

    def test_multiple_contiguous_leading_markers(self):
        text = "[intro][on-hold music] Real content here."
        self.assertEqual(strip_root_text_markers(text), "Real content here.")

    def test_no_markers_unchanged(self):
        text = "Just plain speech content."
        self.assertEqual(strip_root_text_markers(text), "Just plain speech content.")

    def test_interior_bracket_content_preserved(self):
        text = "The matrix [1, 2, 3] is invertible."
        self.assertEqual(strip_root_text_markers(text), "The matrix [1, 2, 3] is invertible.")


class CleanTranscriptPayloadTests(unittest.TestCase):
    def test_original_transcript_payload(self):
        payload = {
            "type": "original_transcript",
            "text": "[on-hold music] Hello world. [on-hold music]",
            "segments": [
                {"id": 1, "start": 0.0, "end": 1.0, "original_text": "[on-hold music]",
                 "words": [_event_word("[on-hold music]")]},
                {"id": 2, "start": 1.0, "end": 3.0, "original_text": "Hello world.",
                 "words": [_speech_word("Hello world.")]},
            ],
        }
        result = clean_transcript_payload(payload)
        self.assertEqual(result["text"], "Hello world.")
        self.assertEqual(len(result["segments"]), 1)
        self.assertEqual(result["segments"][0]["id"], 1)
        self.assertEqual(result["segments"][0]["original_text"], "Hello world.")

    def test_translated_transcript_payload_has_no_root_text_untouched(self):
        # translated payloads have no root "text" key in this codebase's schema;
        # cleaner must not error or add one
        payload = {
            "type": "translated_transcript",
            "segments": [
                {"id": 1, "start": 0.0, "end": 1.0, "original_text": "[on-hold music]",
                 "translated_text": "[on-hold music]", "subtitle_text": "[on-hold music]",
                 "text": "[on-hold music]", "source_words": [_event_word("[on-hold music]")]},
                {"id": 2, "start": 1.0, "end": 3.0, "original_text": "Hello", "translated_text": "Vanakkam",
                 "subtitle_text": "Vanakkam", "text": "Vanakkam", "source_words": [_speech_word("Hello")]},
            ],
        }
        result = clean_transcript_payload(payload)
        self.assertNotIn("text", result)
        self.assertEqual(len(result["segments"]), 1)
        self.assertEqual(result["segments"][0]["translated_text"], "Vanakkam")


class SrtParseAndCleanTests(unittest.TestCase):
    def test_parse_basic_srt(self):
        content = (
            "1\n00:00:00,000 --> 00:00:01,000\n[on-hold music]\n\n"
            "2\n00:00:01,000 --> 00:00:03,000\nHello world.\n"
        )
        blocks = parse_srt(content)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0]["text"], "[on-hold music]")
        self.assertEqual(blocks[1]["text"], "Hello world.")
        self.assertEqual(blocks[1]["start"], "00:00:01,000")

    def test_parse_handles_crlf(self):
        content = "1\r\n00:00:00,000 --> 00:00:01,000\r\nHello\r\n"
        blocks = parse_srt(content)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["text"], "Hello")

    def test_parse_multiline_caption(self):
        content = "1\n00:00:00,000 --> 00:00:02,000\nLine one\nLine two\n"
        blocks = parse_srt(content)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["text"], "Line one\nLine two")

    def test_build_srt_renumbers(self):
        blocks = [
            {"index": 5, "start": "00:00:00,000", "end": "00:00:01,000", "text": "Hi"},
            {"index": 9, "start": "00:00:01,000", "end": "00:00:02,000", "text": "There"},
        ]
        rebuilt = build_srt(blocks)
        self.assertTrue(rebuilt.startswith("1\n"))
        self.assertIn("\n2\n", rebuilt)

    def test_clean_srt_content_strips_leading_and_trailing(self):
        content = (
            "1\n00:00:00,000 --> 00:00:01,000\n[on-hold music]\n\n"
            "2\n00:00:01,000 --> 00:00:03,000\nHello world.\n\n"
            "3\n00:00:03,000 --> 00:00:05,000\nMore speech.\n\n"
            "4\n00:00:05,000 --> 00:00:06,000\n[on-hold music]\n"
        )
        cleaned = clean_srt_content(content)
        blocks = parse_srt(cleaned)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0]["index"], 1)
        self.assertEqual(blocks[0]["text"], "Hello world.")
        self.assertEqual(blocks[1]["index"], 2)
        self.assertEqual(blocks[1]["text"], "More speech.")
        # timestamps preserved exactly
        self.assertEqual(blocks[0]["start"], "00:00:01,000")
        self.assertEqual(blocks[1]["end"], "00:00:05,000")

    def test_clean_srt_content_middle_marker_preserved(self):
        content = (
            "1\n00:00:00,000 --> 00:00:01,000\nHello world.\n\n"
            "2\n00:00:01,000 --> 00:00:02,000\n[on-hold music]\n\n"
            "3\n00:00:02,000 --> 00:00:03,000\nMore speech.\n"
        )
        cleaned = clean_srt_content(content)
        blocks = parse_srt(cleaned)
        self.assertEqual(len(blocks), 3)
        self.assertEqual(blocks[1]["text"], "[on-hold music]")

    def test_clean_srt_content_empty_input(self):
        self.assertEqual(clean_srt_content(""), "")

    def test_clean_srt_content_all_markers(self):
        content = (
            "1\n00:00:00,000 --> 00:00:01,000\n[on-hold music]\n\n"
            "2\n00:00:01,000 --> 00:00:02,000\n[on-hold music]\n"
        )
        cleaned = clean_srt_content(content)
        self.assertEqual(parse_srt(cleaned), [])


if __name__ == "__main__":
    unittest.main()
