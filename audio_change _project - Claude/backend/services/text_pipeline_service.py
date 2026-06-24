import json
import logging
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from config import TextPipelineConfig, load_text_pipeline_config
from services.math_phonetic_service import convert_math_to_phonetic
from services.translation_service import (
    TextProcessingProvider,
    _normalize_text,
    _protect_text,
    _restore_text,
    adapt_text_for_target_language,
    create_text_processing_provider,
)


logger = logging.getLogger(__name__)


def _has_processable_text(value: object) -> bool:
    text = _normalize_text(str(value or "")).lower()
    if not text:
        return False

    unwrapped = text.strip("()[]{} \t\r\n")
    if unwrapped in {"empty", "none", "null", "n/a"}:
        return False

    return not any(
        marker in unwrapped
        for marker in ("empty source", "empty input", "nothing to translate")
    )


def _log_stage(stage: str, status: str, **details: object) -> None:
    payload = {"stage": stage, "status": status}
    payload.update(details)
    logger.info(json.dumps(payload, ensure_ascii=False))


class TextPipelineService:
    def __init__(
        self,
        config: Optional[TextPipelineConfig] = None,
        primary_provider: Optional[TextProcessingProvider] = None,
        fallback_provider: Optional[TextProcessingProvider] = None,
    ) -> None:
        self.config = config or load_text_pipeline_config()
        self.primary_provider = primary_provider or create_text_processing_provider(
            self.config.primary_llm_provider
        )
        self.fallback_provider = fallback_provider
        if (
            self.fallback_provider is None
            and self.config.fallback_llm_provider
            and self.config.fallback_llm_provider != self.config.primary_llm_provider
        ):
            try:
                self.fallback_provider = create_text_processing_provider(
                    self.config.fallback_llm_provider
                )
            except Exception as exc:
                logger.warning("Unable to initialize fallback text provider: %s", exc)

    async def process_segments(self, segments: List[dict], target_language: str) -> Dict[str, object]:
        cleaned_segments, cleanup_used_fallback = await self._run_single_input_stage(
            stage_name="transcript_cleanup",
            segments=segments,
            enabled=self.config.transcript_cleanup_enabled,
            handler=lambda text: self.primary_provider.cleanup_text(text, self.config.glossary_terms),
        )

        phonetic_segments = [
            {**seg, "text": convert_math_to_phonetic(seg["text"])}
            for seg in cleaned_segments
        ]

        translated_segments = await self._run_translation_stage(phonetic_segments, target_language)
        reviewed_segments, review_used_fallback = await self._run_dual_input_stage(
            stage_name="translation_review",
            source_segments=cleaned_segments,
            candidate_segments=translated_segments,
            enabled=self.config.translation_review_enabled,
            handler=lambda source_text, translated_text: self.primary_provider.review_translation(
                source_text,
                translated_text,
                target_language,
                self.config.translation_mode,
                self.config.glossary_terms,
            ),
            fallback_handler=(
                lambda source_text, translated_text: self.fallback_provider.review_translation(
                    source_text,
                    translated_text,
                    target_language,
                    self.config.translation_mode,
                    self.config.glossary_terms,
                )
                if self.fallback_provider
                else None
            ),
            target_language=target_language,
        )
        subtitle_segments, compression_used_fallback = await self._run_single_input_stage(
            stage_name="subtitle_compression",
            segments=reviewed_segments,
            enabled=self.config.subtitle_compression_enabled,
            handler=lambda text: self.primary_provider.compress_subtitle(
                text,
                target_language,
                self.config.glossary_terms,
                self.config.max_subtitle_chars,
                self.config.max_subtitle_words,
            ),
            fallback_handler=(
                lambda text: self.fallback_provider.compress_subtitle(
                    text,
                    target_language,
                    self.config.glossary_terms,
                    self.config.max_subtitle_chars,
                    self.config.max_subtitle_words,
                )
                if self.fallback_provider
                else None
            ),
            prefer_target_glossary=True,
            target_language=target_language,
        )

        transcript_text = _normalize_text(" ".join(seg.get("text", "") for seg in segments))
        cleaned_text = _normalize_text(" ".join(seg.get("text", "") for seg in phonetic_segments))
        translated_text = _normalize_text(" ".join(seg.get("text", "") for seg in reviewed_segments))
        subtitle_text = _normalize_text(" ".join(seg.get("text", "") for seg in subtitle_segments))

        return {
            "raw_segments": segments,
            "cleaned_segments": cleaned_segments,
            "translated_segments": translated_segments,
            "reviewed_segments": reviewed_segments,
            "subtitle_segments": subtitle_segments,
            "raw_text": transcript_text,
            "cleaned_text": cleaned_text,
            "translated_text": translated_text,
            "subtitle_text": subtitle_text,
            "stage_status": {
                "transcript_cleanup_enabled": self.config.transcript_cleanup_enabled,
                "translation_review_enabled": self.config.translation_review_enabled,
                "subtitle_compression_enabled": self.config.subtitle_compression_enabled,
                "transcript_cleanup_fallback_used": cleanup_used_fallback,
                "translation_review_fallback_used": review_used_fallback,
                "subtitle_compression_fallback_used": compression_used_fallback,
                "primary_llm_provider": self.primary_provider.provider_name,
                "fallback_llm_provider": (
                    self.fallback_provider.provider_name if self.fallback_provider else None
                ),
                "translation_mode": self.config.translation_mode,
            },
        }

    async def _run_translation_stage(self, segments: List[dict], target_language: str) -> List[dict]:
        stage_name = "translation"
        _log_stage(stage_name, "started", provider=self.primary_provider.provider_name, segments=len(segments))

        translated_segments: List[dict] = []
        use_fallback_for_remaining = False
        for segment in segments:
            source_text = segment.get("text", "")
            if not _has_processable_text(source_text):
                translated_segments.append(
                    {
                        "start": segment["start"],
                        "end": segment["end"],
                        "text": "",
                    }
                )
                continue

            protected_text, replacements = _protect_text(
                source_text,
                self.config.glossary_terms,
                prefer_target=True,
            )
            try:
                active_provider = (
                    self.fallback_provider
                    if use_fallback_for_remaining and self.fallback_provider
                    else self.primary_provider
                )
                provider_input = (
                    source_text
                    if active_provider.provider_name == "google"
                    else protected_text
                )
                result_replacements = (
                    {} if active_provider.provider_name == "google" else replacements
                )
                translated_text = await active_provider.translate_text(
                    provider_input,
                    target_language,
                    self.config.translation_mode,
                    self.config.glossary_terms,
                )
            except Exception as exc:
                if not self.fallback_provider:
                    _log_stage(stage_name, "failed", provider=self.primary_provider.provider_name, reason=str(exc))
                    raise

                _log_stage(
                    stage_name,
                    "fallback_used",
                    provider=self.primary_provider.provider_name,
                    fallback_provider=self.fallback_provider.provider_name,
                    reason=str(exc),
                )
                use_fallback_for_remaining = True
                fallback_input = (
                    source_text
                    if self.fallback_provider.provider_name == "google"
                    else protected_text
                )
                result_replacements = (
                    {}
                    if self.fallback_provider.provider_name == "google"
                    else replacements
                )
                translated_text = await self.fallback_provider.translate_text(
                    fallback_input,
                    target_language,
                    self.config.translation_mode,
                    self.config.glossary_terms,
                )

            if not _has_processable_text(translated_text):
                recovery_provider = self.fallback_provider or active_provider
                _log_stage(
                    stage_name,
                    "empty_result_retry",
                    provider=recovery_provider.provider_name,
                    segment_id=segment.get("id"),
                )
                translated_text = await recovery_provider.translate_text(
                    source_text,
                    target_language,
                    self.config.translation_mode,
                    self.config.glossary_terms,
                )
                # The recovery request used raw source text, so there are no
                # placeholders to restore in its result.
                result_replacements = {}

            if not _has_processable_text(translated_text):
                raise RuntimeError(
                    "Translation provider returned empty text after retry "
                    f"for segment {segment.get('id', len(translated_segments) + 1)}."
                )

            translated_segments.append(
                {
                    "start": segment["start"],
                    "end": segment["end"],
                    "text": adapt_text_for_target_language(
                        _restore_text(translated_text, result_replacements),
                        target_language,
                    ),
                }
            )

        _log_stage(stage_name, "completed", provider=self.primary_provider.provider_name, segments=len(translated_segments))
        return translated_segments

    async def _run_single_input_stage(
        self,
        stage_name: str,
        segments: List[dict],
        enabled: bool,
        handler: Callable[[str], object],
        fallback_handler: Optional[Callable[[str], object]] = None,
        prefer_target_glossary: bool = False,
        target_language: Optional[str] = None,
    ) -> Tuple[List[dict], bool]:
        if not enabled:
            return segments, False

        _log_stage(stage_name, "started", provider=self.primary_provider.provider_name, segments=len(segments))
        processed_segments: List[dict] = []
        fallback_used = False
        use_fallback_for_remaining = False

        for segment in segments:
            if not _has_processable_text(segment.get("text")):
                processed_segments.append(
                    {
                        "start": segment["start"],
                        "end": segment["end"],
                        "text": "",
                    }
                )
                continue

            protected_text, replacements = _protect_text(
                segment.get("text", ""),
                self.config.glossary_terms,
                prefer_target=prefer_target_glossary,
            )
            try:
                if use_fallback_for_remaining and fallback_handler:
                    stage_text = await fallback_handler(protected_text)
                else:
                    stage_text = await handler(protected_text)
            except Exception as exc:
                fallback_used = True
                _log_stage(
                    stage_name,
                    "fallback_used",
                    provider=self.primary_provider.provider_name,
                    reason=str(exc),
                )
                if fallback_handler:
                    use_fallback_for_remaining = True
                    stage_text = await fallback_handler(protected_text)
                else:
                    stage_text = segment.get("text", "")

            processed_segments.append(
                {
                    "start": segment["start"],
                    "end": segment["end"],
                    "text": adapt_text_for_target_language(
                        _restore_text(stage_text, replacements),
                        target_language or "",
                    ),
                }
            )

        _log_stage(stage_name, "completed", provider=self.primary_provider.provider_name, segments=len(processed_segments))
        return processed_segments, fallback_used

    async def _run_dual_input_stage(
        self,
        stage_name: str,
        source_segments: Sequence[dict],
        candidate_segments: List[dict],
        enabled: bool,
        handler: Callable[[str, str], object],
        fallback_handler: Optional[Callable[[str, str], object]] = None,
        target_language: Optional[str] = None,
    ) -> Tuple[List[dict], bool]:
        if not enabled:
            return candidate_segments, False

        _log_stage(stage_name, "started", provider=self.primary_provider.provider_name, segments=len(candidate_segments))
        reviewed_segments: List[dict] = []
        fallback_used = False
        use_fallback_for_remaining = False

        for source_segment, candidate_segment in zip(source_segments, candidate_segments):
            if not _has_processable_text(candidate_segment.get("text")):
                reviewed_segments.append(
                    {
                        "start": candidate_segment["start"],
                        "end": candidate_segment["end"],
                        "text": "",
                    }
                )
                continue

            protected_source, _ = _protect_text(
                source_segment.get("text", ""),
                self.config.glossary_terms,
                prefer_target=False,
            )
            protected_candidate, replacements = _protect_text(
                candidate_segment.get("text", ""),
                self.config.glossary_terms,
                prefer_target=True,
            )
            try:
                if use_fallback_for_remaining and fallback_handler:
                    reviewed_text = await fallback_handler(protected_source, protected_candidate)
                else:
                    reviewed_text = await handler(protected_source, protected_candidate)
            except Exception as exc:
                fallback_used = True
                _log_stage(
                    stage_name,
                    "fallback_used",
                    provider=self.primary_provider.provider_name,
                    reason=str(exc),
                )
                if fallback_handler:
                    use_fallback_for_remaining = True
                    reviewed_text = await fallback_handler(protected_source, protected_candidate)
                else:
                    reviewed_text = candidate_segment.get("text", "")

            reviewed_segments.append(
                {
                    "start": candidate_segment["start"],
                    "end": candidate_segment["end"],
                    "text": adapt_text_for_target_language(
                        _restore_text(reviewed_text, replacements),
                        target_language or "",
                    ),
                }
            )

        _log_stage(stage_name, "completed", provider=self.primary_provider.provider_name, segments=len(reviewed_segments))
        return reviewed_segments, fallback_used
