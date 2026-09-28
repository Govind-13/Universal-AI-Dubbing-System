import whisper
import os
import requests
import torch
from pathlib import Path
import imageio_ffmpeg
import shutil
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Auto-detect GPU; use medium model on GPU for better accuracy, base on CPU for speed
_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
_MODEL_SIZE = "medium" if _DEVICE == "cuda" else "base"

_whisper_model = None


def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        logger.info(f"Loading Whisper '{_MODEL_SIZE}' model on {_DEVICE.upper()}...")
        _whisper_model = whisper.load_model(_MODEL_SIZE, device=_DEVICE)
        logger.info(f"Whisper model loaded on {_DEVICE.upper()}.")
    return _whisper_model


# Configure FFmpeg for Whisper

ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
ffmpeg_dir = os.path.dirname(ffmpeg_exe)
target_ffmpeg = os.path.join(ffmpeg_dir, "ffmpeg.exe")

# Ensure 'ffmpeg.exe' exists by copying the versioned binary if needed
if not os.path.exists(target_ffmpeg):
    try:
        shutil.copy(ffmpeg_exe, target_ffmpeg)
        logger.info(f"Created shim: {target_ffmpeg}")
    except Exception as e:
        logger.error(f"Failed to create ffmpeg shim: {e}")

os.environ["PATH"] += os.pathsep + ffmpeg_dir
logger.info(f"Added FFmpeg to PATH: {ffmpeg_dir}")


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _normalize_language_code(value: object) -> str:
    language = str(value or "en").strip().lower()
    return {"eng": "en", "english": "en"}.get(language, language)


def _normalize_word(item: dict) -> dict:
    """Preserve STT word/event metadata while exposing stable timestamp names."""
    word = {
        "text": item.get("text", ""),
        "start_time": _float_or_none(item.get("start_time", item.get("start"))),
        "end_time": _float_or_none(item.get("end_time", item.get("end"))),
    }
    for key in ("type", "speaker_id", "logprob", "confidence"):
        if item.get(key) is not None:
            word[key] = item[key]
    return word


def _speaker_from_items(items: list[dict]) -> dict | None:
    speaker_id = next(
        (
            item.get("speaker_id")
            for item in items
            if item.get("speaker_id") is not None
        ),
        None,
    )
    if speaker_id is None:
        return None
    return {"id": str(speaker_id), "name": str(speaker_id).replace("_", " ").title()}


def _normalize_existing_segments(raw_segments: list[dict]) -> list[dict]:
    segments = []
    for index, raw_segment in enumerate(raw_segments):
        words = [_normalize_word(word) for word in raw_segment.get("words", [])]
        start = _float_or_none(
            raw_segment.get("start_time", raw_segment.get("start"))
        )
        end = _float_or_none(raw_segment.get("end_time", raw_segment.get("end")))
        if start is None and words:
            start = words[0].get("start_time")
        if end is None and words:
            end = words[-1].get("end_time")

        segment = {
            "id": raw_segment.get("id", index + 1),
            "start": start or 0.0,
            "end": end if end is not None else (start or 0.0),
            "text": str(raw_segment.get("text", "")).strip(),
            "words": words,
        }
        speaker = raw_segment.get("speaker") or _speaker_from_items(
            raw_segment.get("words", [])
        )
        if speaker:
            segment["speaker"] = speaker
        segments.append(segment)
    return segments


def _segments_from_words(words_list: list[dict]) -> list[dict]:
    """Group detailed ElevenLabs words/events into sentence-like segments."""
    segments = []
    current_items: list[dict] = []
    word_count = 0

    def finish_segment() -> None:
        nonlocal current_items, word_count
        if not current_items:
            return
        words = [_normalize_word(item) for item in current_items]
        text = "".join(str(item.get("text", "")) for item in current_items).strip()
        valid_starts = [
            word["start_time"] for word in words if word.get("start_time") is not None
        ]
        valid_ends = [
            word["end_time"] for word in words if word.get("end_time") is not None
        ]
        if text:
            segment = {
                "id": len(segments) + 1,
                "start": valid_starts[0] if valid_starts else 0.0,
                "end": valid_ends[-1] if valid_ends else (valid_starts[0] if valid_starts else 0.0),
                "text": text,
                "words": words,
            }
            speaker = _speaker_from_items(current_items)
            if speaker:
                segment["speaker"] = speaker
            segments.append(segment)
        current_items = []
        word_count = 0

    for item in words_list:
        current_items.append(item)
        item_type = item.get("type")
        text = str(item.get("text", ""))
        if item_type == "word" or (item_type is None and text.strip()):
            word_count += 1

        starts = [
            _float_or_none(word.get("start_time", word.get("start")))
            for word in current_items
        ]
        ends = [
            _float_or_none(word.get("end_time", word.get("end")))
            for word in current_items
        ]
        valid_starts = [value for value in starts if value is not None]
        valid_ends = [value for value in ends if value is not None]
        duration = (
            valid_ends[-1] - valid_starts[0]
            if valid_starts and valid_ends
            else 0.0
        )
        stripped = text.strip()
        has_punctuation = bool(stripped) and stripped[-1] in ".!?"
        is_audio_event = stripped.startswith("[") and stripped.endswith("]")
        if word_count >= 24 or duration >= 12.0 or has_punctuation or is_audio_event:
            finish_segment()

    finish_segment()
    return segments


def _segments_from_full_stops(words: list[dict]) -> list[dict]:
    """Regroup a flat, chronologically-ordered list of normalized words into
    sentence segments split ONLY at a literal sentence-ending full stop ('.').
    Never splits on '!', '?', word count, or duration. Contiguous leading/
    trailing audio-event-tagged words are stripped first (before grouping),
    so a marker like "[on-hold music]" never gets glued onto the first or
    last real sentence. Any trailing words with no closing '.' are still
    flushed as a final segment so content is never silently dropped."""
    if not words:
        return []

    start_index = 0
    end_index = len(words)
    while start_index < end_index and words[start_index].get("type") == "audio_event":
        start_index += 1
    while end_index > start_index and words[end_index - 1].get("type") == "audio_event":
        end_index -= 1
    speech_words = words[start_index:end_index]
    if not speech_words:
        return []

    segments = []
    current: list[dict] = []

    def flush() -> None:
        if not current:
            return
        text = "".join(str(w.get("text", "")) for w in current).strip()
        if not text:
            current.clear()
            return
        starts = [w.get("start_time") for w in current if w.get("start_time") is not None]
        ends = [w.get("end_time") for w in current if w.get("end_time") is not None]
        segment = {
            "id": len(segments) + 1,
            "start": starts[0] if starts else 0.0,
            "end": ends[-1] if ends else (starts[0] if starts else 0.0),
            "text": text,
            "words": list(current),
        }
        speaker = _speaker_from_items(current)
        if speaker:
            segment["speaker"] = speaker
        segments.append(segment)
        current.clear()

    for word in speech_words:
        current.append(word)
        stripped_text = str(word.get("text", "")).strip()
        if stripped_text.endswith("."):
            flush()

    flush()  # any trailing words with no closing '.' are still preserved
    return segments


def normalize_stt_result(raw_result: dict, provider: str) -> dict:
    """Return one lossless, provider-independent STT result schema.

    Segmentation is always finalized by regrouping every word across
    whichever upstream segments were built (regardless of provider/path)
    at literal sentence-ending full stops only — the single segmentation
    source of truth for the whole pipeline. See _segments_from_full_stops.
    """
    raw_segments = raw_result.get("segments") or []
    if raw_segments:
        segments = _normalize_existing_segments(raw_segments)
    else:
        segments = _segments_from_words(raw_result.get("words") or [])

    all_words = []
    for segment in segments:
        segment_speaker_id = (segment.get("speaker") or {}).get("id")
        for word in segment.get("words", []):
            if segment_speaker_id and not word.get("speaker_id"):
                word = {**word, "speaker_id": segment_speaker_id}
            all_words.append(word)
    if all_words:
        segments = _segments_from_full_stops(all_words)

    text = str(raw_result.get("text") or "").strip()
    if not text:
        text = " ".join(segment.get("text", "") for segment in segments).strip()

    raw_language_code = str(
        raw_result.get("language_code", raw_result.get("language", "en"))
    ).strip()
    result = {
        "provider": provider,
        "text": text,
        "language": _normalize_language_code(raw_language_code),
        "language_code": raw_language_code or "en",
        "segments": segments,
    }
    if raw_result.get("language_probability") is not None:
        result["language_probability"] = raw_result["language_probability"]
    return result


def _transcribe_with_elevenlabs(audio_path: str, api_key: str) -> dict:
    url = "https://api.elevenlabs.io/v1/speech-to-text"
    headers = {"xi-api-key": api_key}
    data = {
        "model_id": os.getenv("ELEVENLABS_STT_MODEL_ID", "scribe_v1"),
        "tag_audio_events": os.getenv("ELEVENLABS_STT_TAG_AUDIO_EVENTS", "true"),
        "diarize": os.getenv("ELEVENLABS_STT_DIARIZE", "true"),
    }
    language_code = os.getenv("ELEVENLABS_STT_LANGUAGE_CODE", "").strip()
    if language_code:
        data["language_code"] = language_code

    logger.info(f"Calling ElevenLabs STT API for: {audio_path}")
    with open(audio_path, "rb") as f:
        files = {"file": (os.path.basename(audio_path), f, "audio/mpeg")}
        res = requests.post(url, headers=headers, data=data, files=files, timeout=120)

    if res.status_code != 200:
        raise RuntimeError(f"ElevenLabs STT error {res.status_code}: {res.text}")

    return normalize_stt_result(res.json(), provider="elevenlabs")


def transcribe_audio(audio_path: str) -> dict:
    """
    Transcribes audio file to text using ElevenLabs or OpenAI Whisper.
    Returns dictionary with text and segments.
    """
    try:
        audio_path = str(Path(audio_path).resolve())

        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info(f"Starting transcription for: {audio_path}")

        eleven_api_key = os.getenv("ELEVENLABS_API_KEY")
        if eleven_api_key:
            try:
                result = _transcribe_with_elevenlabs(audio_path, eleven_api_key)
                logger.info("ElevenLabs Transcription complete.")
                return result
            except Exception as e:
                logger.warning(f"ElevenLabs failed: {e}. Falling back to Whisper...")

        # Fallback to Whisper
        model = get_whisper_model()
        result = model.transcribe(audio_path, fp16=(_DEVICE == "cuda"), word_timestamps=True)

        logger.info("Whisper Transcription complete.")
        return normalize_stt_result(result, provider="whisper")

    except Exception as e:
        logger.error(f"Error during transcription: {e}")
        raise RuntimeError(f"Transcription failed: {str(e)}")
