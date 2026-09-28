import json
import os
from dataclasses import dataclass, field
from typing import List, Optional


def _parse_bool(value: Optional[str], default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_int(value: Optional[str], default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class GlossaryTerm:
    source: str
    target: Optional[str] = None


@dataclass(frozen=True)
class TextPipelineConfig:
    transcript_cleanup_enabled: bool = True
    translation_review_enabled: bool = True
    subtitle_compression_enabled: bool = True
    translation_mode: str = "student_friendly"
    primary_llm_provider: str = "openai"
    fallback_llm_provider: str = "google"
    glossary_terms: List[GlossaryTerm] = field(default_factory=list)
    max_subtitle_chars: int = 42
    max_subtitle_words: int = 12


def _parse_glossary_env(value: Optional[str]) -> List[GlossaryTerm]:
    if not value:
        return []

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        parsed = None

    glossary_terms: List[GlossaryTerm] = []

    if isinstance(parsed, dict):
        for source, target in parsed.items():
            source_text = str(source).strip()
            target_text = str(target).strip()
            if source_text:
                glossary_terms.append(GlossaryTerm(source=source_text, target=target_text or None))
        return glossary_terms

    if isinstance(parsed, list):
        for item in parsed:
            if isinstance(item, str) and item.strip():
                glossary_terms.append(GlossaryTerm(source=item.strip()))
            elif isinstance(item, dict):
                source = str(item.get("source") or item.get("term") or "").strip()
                target = str(item.get("target") or item.get("translation") or "").strip()
                if source:
                    glossary_terms.append(GlossaryTerm(source=source, target=target or None))
        return glossary_terms

    for raw_entry in value.split(";"):
        entry = raw_entry.strip()
        if not entry:
            continue
        if "=>" in entry:
            source, target = entry.split("=>", 1)
        elif "=" in entry:
            source, target = entry.split("=", 1)
        else:
            source, target = entry, ""

        source = source.strip()
        target = target.strip()
        if source:
            glossary_terms.append(GlossaryTerm(source=source, target=target or None))

    return glossary_terms


def load_text_pipeline_config() -> TextPipelineConfig:
    glossary_env = os.getenv("GLOSSARY_TERMS")
    primary_provider = os.getenv("PRIMARY_LLM_PROVIDER")
    fallback_provider = os.getenv("FALLBACK_LLM_PROVIDER")

    if not primary_provider:
        primary_provider = "openai" if os.getenv("OPENAI_API_KEY") else "google"

    return TextPipelineConfig(
        transcript_cleanup_enabled=_parse_bool(os.getenv("TRANSCRIPT_CLEANUP_ENABLED"), True),
        translation_review_enabled=_parse_bool(os.getenv("TRANSLATION_REVIEW_ENABLED"), True),
        subtitle_compression_enabled=_parse_bool(os.getenv("SUBTITLE_COMPRESSION_ENABLED"), True),
        translation_mode=os.getenv("TRANSLATION_MODE", "student_friendly").strip() or "student_friendly",
        primary_llm_provider=primary_provider.strip().lower(),
        fallback_llm_provider=(fallback_provider or "google").strip().lower(),
        glossary_terms=_parse_glossary_env(glossary_env),
        max_subtitle_chars=_parse_int(os.getenv("MAX_SUBTITLE_CHARS"), 42),
        max_subtitle_words=_parse_int(os.getenv("MAX_SUBTITLE_WORDS"), 12),
    )


@dataclass(frozen=True)
class AppConfig:
    ffprobe_dir: Optional[str] = None
    report_fallbacks: bool = True


def load_app_config() -> AppConfig:
    return AppConfig(
        ffprobe_dir=os.getenv("FFPROBE_DIR"),
        report_fallbacks=_parse_bool(os.getenv("REPORT_FALLBACKS"), True),
    )
