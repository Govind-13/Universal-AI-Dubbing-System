import json
import math
import re
from pathlib import Path


PLACEHOLDER_MARKERS = (
    "empty source",
    "empty input",
    "nothing to translate",
)

MODEL_COMMENTARY_MARKERS = (
    "wait, i need to",
    "let me return",
    "please clarify",
    "the autoterm",
    "as an ai",
    "i cannot translate",
)

UNRESOLVED_PLACEHOLDER_MARKERS = (
    "autoterm",
    "glterm",
    "xtok",
    "ஆட்டோடெர்ம்",
    "டோக்கன்",
)


class TranslationValidationError(RuntimeError):
    pass


def _normalized_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _is_placeholder(value: object) -> bool:
    normalized = _normalized_text(value).lower().strip("()[]{} \t\r\n")
    if not normalized or normalized in {"empty", "none", "null", "n/a"}:
        return True
    return any(marker in normalized for marker in PLACEHOLDER_MARKERS)


def _source_requires_translation(value: object) -> bool:
    text = _normalized_text(value)
    if not text:
        return False

    without_events = re.sub(r"\[[^\]]+\]", " ", text)
    return bool(re.search(r"[A-Za-z\u0080-\uffff]", without_events))


def _number(value: object) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def validate_translation_payload(
    payload: dict,
    source_segments: list[dict],
    target_language: str | None = None,
) -> dict:
    errors: list[str] = []

    if payload.get("type") != "translated_transcript":
        errors.append("JSON type must be 'translated_transcript'.")

    if target_language and payload.get("target_language") != target_language:
        errors.append(
            f"Target language mismatch: expected {target_language!r}, "
            f"received {payload.get('target_language')!r}."
        )

    translated_segments = payload.get("segments")
    if not isinstance(translated_segments, list):
        raise TranslationValidationError("Translation JSON segments must be a list.")

    if len(translated_segments) != len(source_segments):
        errors.append(
            f"Segment count mismatch: source={len(source_segments)}, "
            f"translated={len(translated_segments)}."
        )

    seen_ids = set()
    previous_end = -1.0
    checked_count = min(len(source_segments), len(translated_segments))

    for index in range(checked_count):
        source = source_segments[index]
        translated = translated_segments[index]
        label = f"segment {index + 1}"

        if not isinstance(translated, dict):
            errors.append(f"{label}: segment must be an object.")
            continue

        expected_id = source.get("id", index + 1)
        actual_id = translated.get("id", index + 1)
        if actual_id != expected_id:
            errors.append(
                f"{label}: ID mismatch; expected {expected_id!r}, received {actual_id!r}."
            )
        if actual_id in seen_ids:
            errors.append(f"{label}: duplicate segment ID {actual_id!r}.")
        seen_ids.add(actual_id)

        source_start = _number(source.get("start"))
        source_end = _number(source.get("end"))
        translated_start = _number(
            translated.get("start", translated.get("start_time"))
        )
        translated_end = _number(translated.get("end", translated.get("end_time")))

        if translated_start is None or translated_end is None:
            errors.append(f"{label}: start/end timestamps must be valid numbers.")
        else:
            if translated_end < translated_start:
                errors.append(f"{label}: end timestamp is before start timestamp.")
            if translated_start < previous_end - 0.01:
                errors.append(f"{label}: timeline overlaps or moves backwards.")
            previous_end = max(previous_end, translated_end)

        if source_start is not None and translated_start is not None:
            if abs(source_start - translated_start) > 0.01:
                errors.append(
                    f"{label}: start timestamp changed "
                    f"({source_start} -> {translated_start})."
                )
        if source_end is not None and translated_end is not None:
            if abs(source_end - translated_end) > 0.01:
                errors.append(
                    f"{label}: end timestamp changed ({source_end} -> {translated_end})."
                )

        source_text = _normalized_text(source.get("text"))
        saved_source_text = _normalized_text(translated.get("original_text"))
        if saved_source_text != source_text:
            errors.append(f"{label}: original source text was modified.")

        if source.get("speaker") and translated.get("speaker") != source.get("speaker"):
            errors.append(f"{label}: speaker metadata was modified.")
        if source.get("words") and translated.get("source_words") != source.get("words"):
            errors.append(f"{label}: source word timestamps were modified.")

        translated_text = translated.get("translated_text")
        final_text = (
            translated.get("text")
            or translated.get("subtitle_text")
            or translated_text
        )
        if _source_requires_translation(source_text):
            if _is_placeholder(translated_text) or _is_placeholder(final_text):
                errors.append(f"{label}: translation is empty or a placeholder.")

        combined_output = (
            f"{_normalized_text(translated_text)} {_normalized_text(final_text)}"
        ).lower()
        if any(marker in combined_output for marker in MODEL_COMMENTARY_MARKERS):
            errors.append(f"{label}: output contains model commentary.")
        if any(
            marker in combined_output
            for marker in UNRESOLVED_PLACEHOLDER_MARKERS
        ):
            errors.append(f"{label}: output contains an unresolved placeholder.")

    if errors:
        preview = "; ".join(errors[:8])
        if len(errors) > 8:
            preview += f"; plus {len(errors) - 8} more error(s)"
        raise TranslationValidationError(
            f"Translation JSON verification failed: {preview}"
        )

    return {
        "valid": True,
        "segment_count": len(translated_segments),
        "verified_fields": [
            "type",
            "target_language",
            "segment_count",
            "segment_ids",
            "timestamps",
            "original_text",
            "speaker",
            "source_words",
            "translated_text",
        ],
    }


def validate_translation_json(
    json_path: str | Path,
    source_segments: list[dict],
    target_language: str | None = None,
) -> dict:
    path = Path(json_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TranslationValidationError(
            f"Translation JSON could not be read: {exc}"
        ) from exc

    return validate_translation_payload(payload, source_segments, target_language)
