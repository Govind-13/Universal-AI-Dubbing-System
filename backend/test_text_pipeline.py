import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import GlossaryTerm, TextPipelineConfig
from services.text_pipeline_service import TextPipelineService
from services.translation_service import (
    TextProcessingProvider,
    _build_target_style_guidance,
    adapt_text_for_target_language,
    create_text_processing_provider,
    normalize_target_language,
)


class FakeProvider(TextProcessingProvider):
    provider_name = "fake"

    def __init__(
        self,
        cleanup_behavior=None,
        translate_behavior=None,
        review_behavior=None,
        compress_behavior=None,
    ) -> None:
        self.cleanup_behavior = cleanup_behavior or (lambda text, glossary: text)
        self.translate_behavior = translate_behavior or (
            lambda text, target_language, translation_mode, glossary: f"translated:{text}"
        )
        self.review_behavior = review_behavior or (
            lambda source_text, translated_text, target_language, translation_mode, glossary: translated_text
        )
        self.compress_behavior = compress_behavior or (
            lambda text, target_language, glossary, max_chars, max_words: text
        )
        self.calls = []

    async def cleanup_text(self, text, glossary_terms):
        self.calls.append(("cleanup", text))
        result = self.cleanup_behavior(text, glossary_terms)
        if isinstance(result, Exception):
            raise result
        return result

    async def translate_text(self, text, target_language, translation_mode, glossary_terms):
        self.calls.append(("translate", text, target_language, translation_mode))
        result = self.translate_behavior(text, target_language, translation_mode, glossary_terms)
        if isinstance(result, Exception):
            raise result
        return result

    async def review_translation(
        self,
        source_text,
        translated_text,
        target_language,
        translation_mode,
        glossary_terms,
    ):
        self.calls.append(("review", source_text, translated_text))
        result = self.review_behavior(
            source_text,
            translated_text,
            target_language,
            translation_mode,
            glossary_terms,
        )
        if isinstance(result, Exception):
            raise result
        return result

    async def compress_subtitle(
        self,
        text,
        target_language,
        glossary_terms,
        max_subtitle_chars,
        max_subtitle_words,
    ):
        self.calls.append(("compress", text, max_subtitle_chars, max_subtitle_words))
        result = self.compress_behavior(
            text,
            target_language,
            glossary_terms,
            max_subtitle_chars,
            max_subtitle_words,
        )
        if isinstance(result, Exception):
            raise result
        return result


class TextPipelineServiceTests(unittest.IsolatedAsyncioTestCase):
    def test_tanglish_helper_transliterates_tamil_script(self):
        self.assertEqual(adapt_text_for_target_language("வணக்கம்", "tanglish"), "vanakkam")
        self.assertEqual(adapt_text_for_target_language("hello", "tanglish"), "hello")

    def test_tanglish_guidance_uses_classroom_style(self):
        guidance = _build_target_style_guidance("tanglish", "subtitle")

        self.assertIn("classroom-style Tanglish", guidance)
        self.assertIn("English/Latin letters", guidance)
        self.assertIn("SRT format", guidance)

    def test_language_aliases_normalize_skill_style_names(self):
        self.assertEqual(normalize_target_language("hinglish"), "hi")
        self.assertEqual(normalize_target_language("hindi+english"), "hi")
        self.assertEqual(normalize_target_language("thanglish"), "tanglish")
        self.assertEqual(normalize_target_language("tenglish"), "te")
        self.assertEqual(normalize_target_language("telugu english"), "te")

    def test_claude_provider_alias_uses_anthropic_provider(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}), patch(
            "services.translation_service.AnthropicTextProcessingProvider.__init__",
            return_value=None,
        ) as init_mock:
            provider = create_text_processing_provider("claude")

        init_mock.assert_called_once_with("test-key")
        self.assertEqual(provider.provider_name, "anthropic")

    async def test_transcript_cleanup_fallback_uses_raw_segments(self):
        config = TextPipelineConfig(
            transcript_cleanup_enabled=True,
            translation_review_enabled=False,
            subtitle_compression_enabled=False,
        )
        provider = FakeProvider(cleanup_behavior=lambda text, glossary: RuntimeError("cleanup failed"))
        service = TextPipelineService(config=config, primary_provider=provider)

        result = await service.process_segments(
            [{"start": 0.0, "end": 1.0, "text": "um hello world"}],
            "hi",
        )

        self.assertEqual(result["cleaned_segments"][0]["text"], "um hello world")
        self.assertEqual(result["translated_segments"][0]["text"], "translated:um hello world")
        self.assertTrue(result["stage_status"]["transcript_cleanup_fallback_used"])

    async def test_translation_review_fallback_uses_translated_text(self):
        config = TextPipelineConfig(
            transcript_cleanup_enabled=False,
            translation_review_enabled=True,
            subtitle_compression_enabled=False,
        )
        provider = FakeProvider(
            translate_behavior=lambda text, target_language, translation_mode, glossary: "hola mundo",
            review_behavior=lambda source, translated, target_language, translation_mode, glossary: RuntimeError(
                "review failed"
            ),
        )
        service = TextPipelineService(config=config, primary_provider=provider)

        result = await service.process_segments(
            [{"start": 0.0, "end": 1.0, "text": "hello world"}],
            "es",
        )

        self.assertEqual(result["reviewed_segments"][0]["text"], "hola mundo")
        self.assertTrue(result["stage_status"]["translation_review_fallback_used"])

    async def test_translation_fallback_is_reused_after_primary_failure(self):
        config = TextPipelineConfig(
            transcript_cleanup_enabled=False,
            translation_review_enabled=False,
            subtitle_compression_enabled=False,
        )
        primary = FakeProvider(
            translate_behavior=lambda text, target_language, translation_mode, glossary: RuntimeError(
                "quota failed"
            )
        )
        fallback = FakeProvider(
            translate_behavior=lambda text, target_language, translation_mode, glossary: f"fallback:{text}"
        )
        service = TextPipelineService(
            config=config,
            primary_provider=primary,
            fallback_provider=fallback,
        )

        result = await service.process_segments(
            [
                {"start": 0.0, "end": 1.0, "text": "find the characteristic equation of A"},
                {"start": 1.0, "end": 2.0, "text": "lambda square minus five lambda plus two"},
            ],
            "hi",
        )

        self.assertEqual(result["translated_segments"][0]["text"], "fallback:find the characteristic equation of A")
        self.assertEqual(result["translated_segments"][1]["text"], "fallback:lambda square minus five lambda plus two")
        self.assertEqual([call[0] for call in primary.calls], ["translate"])
        self.assertEqual([call[0] for call in fallback.calls], ["translate", "translate"])

    async def test_empty_segments_do_not_call_text_providers(self):
        config = TextPipelineConfig(
            transcript_cleanup_enabled=True,
            translation_review_enabled=True,
            subtitle_compression_enabled=True,
        )
        provider = FakeProvider()
        service = TextPipelineService(config=config, primary_provider=provider)

        result = await service.process_segments(
            [
                {"start": 0.0, "end": 1.0, "text": ""},
                {"start": 1.0, "end": 2.0, "text": "(empty source — nothing to translate)"},
            ],
            "ta",
        )

        self.assertEqual(provider.calls, [])
        self.assertEqual([segment["text"] for segment in result["subtitle_segments"]], ["", ""])

    async def test_empty_protected_fallback_retries_unprotected_source(self):
        config = TextPipelineConfig(
            transcript_cleanup_enabled=False,
            translation_review_enabled=False,
            subtitle_compression_enabled=False,
        )
        primary = FakeProvider(
            translate_behavior=lambda text, target_language, translation_mode, glossary: RuntimeError(
                "rate limited"
            )
        )
        fallback = FakeProvider(
            translate_behavior=lambda text, target_language, translation_mode, glossary: (
                "" if "AUTOTERM" in text else "தமிழ் மொழிபெயர்ப்பு"
            )
        )
        service = TextPipelineService(
            config=config,
            primary_provider=primary,
            fallback_provider=fallback,
        )

        result = await service.process_segments(
            [
                {
                    "id": 2,
                    "start": 0.0,
                    "end": 2.0,
                    "text": "x cube plus y cube divided by 3 x plus 4 y",
                }
            ],
            "ta",
        )

        self.assertEqual(
            result["translated_segments"][0]["text"], "தமிழ் மொழிபெயர்ப்பு"
        )
        self.assertEqual(
            [call[0] for call in fallback.calls], ["translate", "translate"]
        )

    async def test_google_fallback_receives_raw_source_without_placeholders(self):
        config = TextPipelineConfig(
            transcript_cleanup_enabled=False,
            translation_review_enabled=False,
            subtitle_compression_enabled=False,
        )
        primary = FakeProvider(
            translate_behavior=lambda text, target_language, translation_mode, glossary: RuntimeError(
                "rate limited"
            )
        )
        fallback = FakeProvider(
            translate_behavior=lambda text, target_language, translation_mode, glossary: "தமிழ்"
        )
        fallback.provider_name = "google"
        service = TextPipelineService(
            config=config,
            primary_provider=primary,
            fallback_provider=fallback,
        )

        await service.process_segments(
            [
                {
                    "id": 1,
                    "start": 0.0,
                    "end": 2.0,
                    "text": "x cube plus y cube divided by 3 x plus 4 y",
                }
            ],
            "ta",
        )

        self.assertNotIn("AUTOTERM", fallback.calls[0][1])

    async def test_glossary_terms_are_preserved_or_mapped(self):
        config = TextPipelineConfig(
            transcript_cleanup_enabled=False,
            translation_review_enabled=False,
            subtitle_compression_enabled=False,
            glossary_terms=[GlossaryTerm(source="Newton's law", target="Ley de Newton")],
        )
        provider = FakeProvider(
            translate_behavior=lambda text, target_language, translation_mode, glossary: text
        )
        service = TextPipelineService(config=config, primary_provider=provider)

        result = await service.process_segments(
            [{"start": 0.0, "end": 2.0, "text": "Newton's law explains motion."}],
            "es",
        )

        self.assertIn("Ley de Newton", result["translated_segments"][0]["text"])

    async def test_subtitle_compression_applies_compact_text(self):
        config = TextPipelineConfig(
            transcript_cleanup_enabled=False,
            translation_review_enabled=False,
            subtitle_compression_enabled=True,
            glossary_terms=[GlossaryTerm(source="DNA")],
            max_subtitle_chars=20,
            max_subtitle_words=4,
        )
        provider = FakeProvider(
            translate_behavior=lambda text, target_language, translation_mode, glossary: "This is a very long DNA explanation for subtitles",
            compress_behavior=lambda text, target_language, glossary, max_chars, max_words: "Short DNA line",
        )
        service = TextPipelineService(config=config, primary_provider=provider)

        result = await service.process_segments(
            [{"start": 0.0, "end": 2.0, "text": "Long explanation"}],
            "en",
        )

        self.assertEqual(result["subtitle_segments"][0]["text"], "Short DNA line")

    async def test_pipeline_runs_in_expected_sequence(self):
        config = TextPipelineConfig(
            transcript_cleanup_enabled=True,
            translation_review_enabled=True,
            subtitle_compression_enabled=True,
        )
        provider = FakeProvider(
            cleanup_behavior=lambda text, glossary: f"clean:{text}",
            translate_behavior=lambda text, target_language, translation_mode, glossary: f"tr:{text}",
            review_behavior=lambda source, translated, target_language, translation_mode, glossary: f"rv:{translated}",
            compress_behavior=lambda text, target_language, glossary, max_chars, max_words: f"cp:{text}",
        )
        service = TextPipelineService(config=config, primary_provider=provider)

        result = await service.process_segments(
            [{"start": 0.0, "end": 1.0, "text": "segment one"}],
            "hi",
        )

        self.assertEqual([call[0] for call in provider.calls], ["cleanup", "translate", "review", "compress"])
        self.assertEqual(result["subtitle_segments"][0]["text"], "cp:rv:tr:clean:segment one")

    async def test_tanglish_pipeline_outputs_latin_script_segments(self):
        config = TextPipelineConfig(
            transcript_cleanup_enabled=False,
            translation_review_enabled=True,
            subtitle_compression_enabled=True,
        )
        provider = FakeProvider(
            translate_behavior=lambda text, target_language, translation_mode, glossary: "வணக்கம்",
            review_behavior=lambda source, translated, target_language, translation_mode, glossary: "வணக்கம்",
            compress_behavior=lambda text, target_language, glossary, max_chars, max_words: "வணக்கம்",
        )
        service = TextPipelineService(config=config, primary_provider=provider)

        result = await service.process_segments(
            [{"start": 0.0, "end": 1.0, "text": "hello"}],
            "tanglish",
        )

        self.assertEqual(result["translated_segments"][0]["text"], "vanakkam")
        self.assertEqual(result["reviewed_segments"][0]["text"], "vanakkam")
        self.assertEqual(result["subtitle_segments"][0]["text"], "vanakkam")


if __name__ == "__main__":
    unittest.main()
