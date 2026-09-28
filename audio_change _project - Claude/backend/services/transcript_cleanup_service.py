"""
Generic transcript/subtitle cleanup: strips contiguous leading/trailing
non-speech "audio event" segments (e.g. "[on-hold music]") from transcript
JSON payloads and SRT content.

Detection is entirely field/schema-driven — no hardcoded filenames, and no
hardcoded marker vocabulary beyond "a single bracketed phrase with nothing
else in the text." This lets the same functions handle the raw STT segment
shape (text/words), the original-transcript JSON shape (original_text/words),
the translated-transcript JSON shape (original_text/translated_text/
subtitle_text/text/source_words), and any plain SRT file.

Only contiguous segments/blocks at the very start or end are ever removed;
anything in the middle is left untouched regardless of content. Timestamps
are never shifted — only list entries are deleted and id/cue numbers
renumbered.
"""

import re

_MARKER_RE = re.compile(r"^\[[^\[\]]+\]$")
_ROOT_LEADING_MARKER_RE = re.compile(r"^\s*\[[^\[\]]+\]\s*")
_ROOT_TRAILING_MARKER_RE = re.compile(r"\s*\[[^\[\]]+\]\s*$")

_TEXT_FIELD_CANDIDATES = ("text", "original_text", "translated_text", "subtitle_text")
_WORD_FIELD_CANDIDATES = ("words", "source_words")
_SPEECHLESS_WORD_TYPES = {"spacing", "audio_event"}

_SRT_BLOCK_RE = re.compile(
    r"(?P<index>\d+)\s*\n"
    r"(?P<start>\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(?P<end>\d{2}:\d{2}:\d{2},\d{3})\s*\n"
    r"(?P<text>.*?)"
    r"(?=\n\s*\n\d+\s*\n\d{2}:\d{2}:\d{2},\d{3}\s*-->|\Z)",
    re.DOTALL,
)


def is_audio_event_marker_text(text: str) -> bool:
    """True when text is exactly one bracketed phrase, e.g. "[on-hold music]",
    with nothing else present. Never matches real spoken/technical content
    since any additional word outside the brackets fails the match."""
    if not isinstance(text, str):
        return False
    return bool(_MARKER_RE.fullmatch(text.strip()))


def is_removable_segment(segment: dict) -> bool:
    """A segment is removable when every present text field is an
    audio-event marker (and only markers), and every present word-level
    item is tagged "spacing" or "audio_event" (never "word")."""
    if not isinstance(segment, dict):
        return False

    text_keys = [key for key in _TEXT_FIELD_CANDIDATES if key in segment]
    if not text_keys:
        return False
    for key in text_keys:
        value = segment.get(key)
        if not isinstance(value, str) or not value.strip():
            return False
        if not is_audio_event_marker_text(value):
            return False

    for words_key in _WORD_FIELD_CANDIDATES:
        words = segment.get(words_key)
        if isinstance(words, list) and words:
            for word in words:
                word_type = word.get("type") if isinstance(word, dict) else None
                if word_type not in _SPEECHLESS_WORD_TYPES:
                    return False

    return True


def clean_segments(segments: list) -> list:
    """Strip only contiguous leading/trailing removable segments, then
    renumber remaining segments' "id" starting at 1. start/end/start_time/
    end_time are never modified."""
    if not isinstance(segments, list) or not segments:
        return segments

    n = len(segments)
    start = 0
    while start < n and is_removable_segment(segments[start]):
        start += 1
    end = n
    while end > start and is_removable_segment(segments[end - 1]):
        end -= 1

    kept = [dict(segment) for segment in segments[start:end]]
    for index, segment in enumerate(kept, start=1):
        segment["id"] = index
    return kept


def strip_root_text_markers(text: str) -> str:
    """Loop-strip the same marker pattern from the start/end of a plain
    transcript string, e.g. "[on-hold music] Hello ... [on-hold music]" ->
    "Hello ...". Interior content is never touched."""
    if not isinstance(text, str):
        return text

    cleaned = text
    while True:
        updated = _ROOT_LEADING_MARKER_RE.sub("", cleaned, count=1)
        if updated == cleaned:
            break
        cleaned = updated
    while True:
        updated = _ROOT_TRAILING_MARKER_RE.sub("", cleaned, count=1)
        if updated == cleaned:
            break
        cleaned = updated
    return cleaned.strip()


def clean_transcript_payload(payload: dict) -> dict:
    """Generic entry point for a transcript JSON payload dict. Behavior
    derives entirely from which keys are present — no filename or
    "original vs translated" schema name is consulted."""
    if not isinstance(payload, dict):
        return payload

    if isinstance(payload.get("segments"), list):
        payload["segments"] = clean_segments(payload["segments"])

    if isinstance(payload.get("text"), str):
        payload["text"] = strip_root_text_markers(payload["text"])

    return payload


def parse_srt(content: str) -> list:
    """Structurally parse SRT content into [{index, start, end, text}, ...].
    Tolerant of \\r\\n line endings and multi-line caption text."""
    if not content or not content.strip():
        return []

    normalized = content.replace("\r\n", "\n").replace("\r", "\n").strip() + "\n\n"
    blocks = []
    for match in _SRT_BLOCK_RE.finditer(normalized):
        blocks.append({
            "index": int(match.group("index")),
            "start": match.group("start"),
            "end": match.group("end"),
            "text": match.group("text").strip(),
        })
    return blocks


def build_srt(blocks: list) -> str:
    """Reassemble SRT blocks, renumbering cues 1..N. Timestamps are
    copied through unchanged."""
    if not blocks:
        return ""
    parts = [
        f"{i}\n{block['start']} --> {block['end']}\n{block['text']}"
        for i, block in enumerate(blocks, start=1)
    ]
    return "\n\n".join(parts) + "\n"


def clean_srt_content(content: str) -> str:
    """Parse SRT content, strip contiguous leading/trailing marker-only
    cues, renumber, and rebuild. A marker cue anywhere in the middle is
    left untouched. Falls back to returning the original content unchanged
    if it doesn't parse as SRT (e.g. already empty)."""
    blocks = parse_srt(content)
    if not blocks:
        return content

    n = len(blocks)
    start = 0
    while start < n and is_audio_event_marker_text(blocks[start]["text"]):
        start += 1
    end = n
    while end > start and is_audio_event_marker_text(blocks[end - 1]["text"]):
        end -= 1

    return build_srt(blocks[start:end])
