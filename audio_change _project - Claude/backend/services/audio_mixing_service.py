import logging
from pathlib import Path

from pydub import AudioSegment

logger = logging.getLogger(__name__)


def _merge_windows(windows: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(windows):
        if start >= end:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def mix_narration_with_bgm(
    bgm_path: str,
    tts_audio_path: str,
    narration_segments: list[dict],
    output_path: str,
    duck_db: float = -20.0,
    fade_ms: int = 250,
) -> str:
    """Overlay translated TTS narration on top of the original background music.

    BGM plays continuously through intro, pauses, and ending. Under each
    narration window it ducks down by `duck_db` with a `fade_ms` fade at
    the window's entry/exit; outside narration windows it stays at its
    original level. Narration timing comes from `narration_segments`
    (the already-synced `retimed_segments` timeline) — no new timing
    source is introduced.
    """
    bgm = AudioSegment.from_file(bgm_path)
    narration = AudioSegment.from_file(tts_audio_path)

    target_len_ms = len(narration)
    if len(bgm) < target_len_ms:
        bgm = bgm + AudioSegment.silent(duration=target_len_ms - len(bgm))
    elif len(bgm) > target_len_ms:
        bgm = bgm[:target_len_ms]

    windows = _merge_windows(
        [
            (
                max(0, round(float(seg["start"]) * 1000)),
                min(target_len_ms, round(float(seg["end"]) * 1000)),
            )
            for seg in narration_segments
            if seg.get("start") is not None and seg.get("end") is not None
        ]
    )

    pieces: list[AudioSegment] = []
    cursor = 0
    for start, end in windows:
        if start > cursor:
            pieces.append(bgm[cursor:start])

        window_dur = end - start
        fade = min(fade_ms, window_dur // 2)
        if fade > 0:
            fade_down = bgm[start:start + fade].fade(from_gain=0, to_gain=duck_db, start=0, end=fade)
            ducked_middle = bgm[start + fade:end - fade].apply_gain(duck_db)
            fade_up = bgm[end - fade:end].fade(from_gain=duck_db, to_gain=0, start=0, end=fade)
            pieces.extend([fade_down, ducked_middle, fade_up])
        else:
            pieces.append(bgm[start:end].apply_gain(duck_db))

        cursor = end

    if cursor < target_len_ms:
        pieces.append(bgm[cursor:target_len_ms])

    ducked_bgm = AudioSegment.silent(duration=0)
    for piece in pieces:
        ducked_bgm += piece

    mixed = ducked_bgm.overlay(narration, position=0)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mixed.export(str(output_path), format="wav")
    logger.info(f"BGM+narration mix exported: {output_path}")
    return str(output_path)
