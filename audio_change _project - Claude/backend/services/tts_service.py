import os
import requests
import asyncio
import base64
import logging
import io
import subprocess
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from config import load_app_config

logger = logging.getLogger(__name__)
try:
    from gtts import gTTS
except ImportError:
    gTTS = None
from pathlib import Path
import edge_tts
import shutil
import tempfile
import imageio_ffmpeg
from pydub import AudioSegment
from tenacity import RetryError

# Configure Pydub to use the ffmpeg binary we have
AudioSegment.converter = imageio_ffmpeg.get_ffmpeg_exe()

# Add ffprobe location to PATH so pydub can read info
app_config = load_app_config()
ffprobe_dir = app_config.ffprobe_dir
if ffprobe_dir and os.path.exists(ffprobe_dir):
    if ffprobe_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = ffprobe_dir + os.pathsep + os.environ.get("PATH", "")
else:
    logger.info("FFPROBE_DIR is not set or invalid in config. Falling back to bundled FFmpeg for audio decoding.")


ELEVENLABS_VOICE_PRESETS = {
    "default": os.getenv("ELEVENLABS_DEFAULT_VOICE_ID", "pGYsZruQzo8cpdFVZyJc"),
    "rachel": "21m00Tcm4TlvDq8ikWAM",
    "domi": "AZnzlk1XvdvUeBnXmlld",
    "bella": "EXAVITQu4vr4xnSDxMaL",
    "antoni": "ErXwobaYiN019PkySvjV",
    "josh": "TxGEqnHWrfWFTfGW9XjX",
    "arnold": "VR6AewLTigWG4xSOukaG",
    "adam": "pNInz6obpgDQGcFmaJgB",
    "sam": "yoZ06aMxZJJ28mfd3POQ",
}

ELEVENLABS_VOICE_PRESET_LABELS = {
    "default": "Default Studio Voice",
    "rachel": "Rachel - Warm narration",
    "domi": "Domi - Bright female",
    "bella": "Bella - Soft female",
    "antoni": "Antoni - Natural male",
    "josh": "Josh - Deep male",
    "arnold": "Arnold - Strong male",
    "adam": "Adam - Crisp male",
    "sam": "Sam - Conversational male",
}

_ELEVENLABS_DISABLED_REASON: str | None = None
_ELEVENLABS_DISABLED_LOGGED = False


def is_tts_speakable_text(text: object) -> bool:
    """Return False for empty values and pipeline placeholders that must stay silent."""
    if text is None:
        return False

    normalized = str(text).strip().lower()
    if not normalized:
        return False

    unwrapped = normalized.strip("()[]{} \t\r\n")
    if unwrapped in {"empty", "none", "null", "n/a"}:
        return False

    return not any(
        marker in unwrapped
        for marker in (
            "empty source",
            "empty input",
            "nothing to translate",
        )
    )


def get_elevenlabs_runtime_status() -> dict:
    return {
        "configured": bool(os.getenv("ELEVENLABS_API_KEY")),
        "available": bool(os.getenv("ELEVENLABS_API_KEY")) and not _ELEVENLABS_DISABLED_REASON,
        "disabled_reason": _ELEVENLABS_DISABLED_REASON,
    }


def _format_exception(exc: Exception) -> str:
    if isinstance(exc, RetryError):
        last_exc = exc.last_attempt.exception()
        if last_exc:
            return str(last_exc)
    return str(exc)


def _should_disable_elevenlabs(reason: str) -> bool:
    normalized = reason.lower()
    return any(
        marker in normalized
        for marker in (
            "401",
            "403",
            "invalid_api_key",
            "invalid api key",
            "voice_not_found",
            "model_not_found",
        )
    )


def _load_audio_segment(audio_path: str | Path) -> AudioSegment:
    """Load audio even on systems where ffprobe is not installed on PATH."""
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # Decode explicitly with the bundled binary; pydub's implicit ffprobe
    # discovery can raise PermissionError as well as FileNotFoundError.
    result = subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error",
         "-nostdin", "-i", str(audio_path), "-f", "wav", "-acodec", "pcm_s16le", "-"],
        capture_output=True, timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError("FFmpeg audio decode failed: " + result.stderr.decode("utf8", errors="replace")[-1000:])
    return AudioSegment.from_file(io.BytesIO(result.stdout), format="wav")


def _require_speech(audio: AudioSegment, segment_label: str) -> None:
    if len(audio) == 0 or audio.rms == 0:
        raise RuntimeError(f"{segment_label}: generated speech is empty or silent")


def _fit_audio_to_duration(audio_seg: AudioSegment, target_duration_ms: int) -> AudioSegment:
    """Return audio padded with silence if shorter. Never speeds up or trims speech."""
    if target_duration_ms <= 0:
        return AudioSegment.empty()

    current_duration_ms = len(audio_seg)
    if current_duration_ms == 0:
        return AudioSegment.silent(duration=target_duration_ms)

    if current_duration_ms < target_duration_ms:
        return audio_seg + AudioSegment.silent(duration=target_duration_ms - current_duration_ms)

    # Audio is longer — return it as-is (no speedup, no trim).
    # The caller handles the overflow by retiming subsequent segments.
    return audio_seg


def _float_setting(value: object, default: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _bool_setting(value: object, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _setting(settings: dict, key: str, env_var: str):
    val = settings.get(key)
    return val if val is not None else os.getenv(env_var)


def build_elevenlabs_settings(settings: dict | None = None) -> dict:
    settings = settings or {}
    return {
        "voice_id": _setting(settings, "voice_id", "ELEVENLABS_VOICE_ID") or "default",
        "model_id": _setting(settings, "model_id", "ELEVENLABS_TTS_MODEL_ID") or "eleven_v3",
        "speed": _float_setting(_setting(settings, "speed", "ELEVENLABS_TTS_SPEED"), 0.90, 0.70, 1.20),
        "stability": _float_setting(_setting(settings, "stability", "ELEVENLABS_TTS_STABILITY"), 0.75, 0.0, 1.0),
        "similarity_boost": _float_setting(
            _setting(settings, "similarity_boost", "ELEVENLABS_TTS_SIMILARITY_BOOST"),
            0.64,
            0.0,
            1.0,
        ),
        "style": _float_setting(_setting(settings, "style", "ELEVENLABS_TTS_STYLE"), 0.0, 0.0, 1.0),
        "use_speaker_boost": _bool_setting(
            settings.get("use_speaker_boost") if "use_speaker_boost" in settings else os.getenv("ELEVENLABS_TTS_SPEAKER_BOOST"),
            True,
        ),
    }


def resolve_elevenlabs_voice_id(voice_id: str | None = None) -> str:
    # Use provided voice_id if not empty, otherwise fallback to env, then "default"
    selected_voice = (voice_id or os.getenv("ELEVENLABS_VOICE_ID") or "default").strip()
    # If the resolved string is "default", use the preset mapping; otherwise return as is
    return ELEVENLABS_VOICE_PRESETS.get(selected_voice, selected_voice)


def list_elevenlabs_voices(api_key: str | None = None) -> list[dict]:
    voices = [
        {"voice_id": voice_id, "name": ELEVENLABS_VOICE_PRESET_LABELS.get(key, key)}
        for key, voice_id in ELEVENLABS_VOICE_PRESETS.items()
    ]
    if not api_key:
        return voices

    try:
        response = requests.get(
            "https://api.elevenlabs.io/v1/voices",
            headers={"xi-api-key": api_key},
            timeout=15,
        )
        response.raise_for_status()
        api_voices = response.json().get("voices", [])
        parsed_voices = [
            {"voice_id": item.get("voice_id"), "name": item.get("name") or item.get("voice_id")}
            for item in api_voices
            if item.get("voice_id")
        ]
        return parsed_voices or voices
    except Exception as exc:
        logger.error(f"ElevenLabs voice list failed: {exc}")
        return voices


def generate_tts(
    text: str,
    language: str,
    output_dir: str,
    filename_prefix: str,
    voice_id: str | None = None,
    elevenlabs_settings: dict | None = None,
) -> str:
    """Legacy function for single-block TTS (kept for backward compatibility or testing)."""
    return asyncio.run(generate_tts_async(text, language, output_dir, filename_prefix, voice_id, elevenlabs_settings))


async def generate_tts_async(
    text: str,
    language: str,
    output_dir: str,
    filename_prefix: str,
    voice_id: str | None = None,
    elevenlabs_settings: dict | None = None,
) -> str:
    """Async wrapper for generating a single audio file."""
    global _ELEVENLABS_DISABLED_REASON, _ELEVENLABS_DISABLED_LOGGED

    output_dir_path = Path(output_dir).resolve()
    output_dir_path.mkdir(parents=True, exist_ok=True)
    filename = f"{filename_prefix}_{language}.mp3"
    output_path = output_dir_path / filename

    if not is_tts_speakable_text(text):
        # Generate 1s of silence
        silent = AudioSegment.silent(duration=1000)
        silent.export(output_path, format="mp3")
        return str(output_path)

    # 1. ElevenLabs
    eleven_api_key = os.getenv("ELEVENLABS_API_KEY")
    if eleven_api_key and not _ELEVENLABS_DISABLED_REASON:
        try:
            _generate_with_elevenlabs(text, language, output_path, eleven_api_key, voice_id, elevenlabs_settings)
            return str(output_path)
        except Exception as e:
            reason = _format_exception(e)
            logger.error(f"ElevenLabs failed: {reason}")
            if _should_disable_elevenlabs(reason):
                _ELEVENLABS_DISABLED_REASON = reason
                logger.error(
                    "ElevenLabs disabled for this server run because the API key/voice/model is invalid. "
                    "Fix backend/.env and restart the backend to re-enable ElevenLabs."
                )
    elif eleven_api_key and _ELEVENLABS_DISABLED_REASON and not _ELEVENLABS_DISABLED_LOGGED:
        logger.warning(
            "Skipping ElevenLabs for remaining TTS segments because the previous request failed: %s",
            _ELEVENLABS_DISABLED_REASON,
        )
        _ELEVENLABS_DISABLED_LOGGED = True

    # 2. Edge TTS
    try:
        await _generate_with_edge(text, language, output_path)
        return str(output_path)
    except Exception as e:
        logger.error(f"Edge TTS failed: {e}")

    # 3. gTTS
    if gTTS:
        try:
            tts = gTTS(text=text, lang=language, slow=False)
            tts.save(str(output_path))
            return str(output_path)
        except Exception as e:
            logger.error(f"gTTS failed: {e}")

    raise RuntimeError("All TTS providers failed for non-empty speech. Check provider errors and retry.")


async def generate_tts_with_alignment_async(
    text: str,
    language: str,
    output_dir: str,
    filename_prefix: str,
    voice_id: str | None = None,
    elevenlabs_settings: dict | None = None,
) -> tuple:
    """Like generate_tts_async, but also returns real per-word timing
    (local, 0-based seconds) when ElevenLabs' /with-timestamps endpoint is
    used successfully. Falls back to the same edge-tts/gTTS chain as
    generate_tts_async when ElevenLabs is unavailable/fails — those
    providers return (path, None) since they don't offer alignment.
    generate_tts_async itself is left unchanged for other callers."""
    global _ELEVENLABS_DISABLED_REASON, _ELEVENLABS_DISABLED_LOGGED

    output_dir_path = Path(output_dir).resolve()
    output_dir_path.mkdir(parents=True, exist_ok=True)
    filename = f"{filename_prefix}_{language}.mp3"
    output_path = output_dir_path / filename

    if not is_tts_speakable_text(text):
        silent = AudioSegment.silent(duration=1000)
        silent.export(output_path, format="mp3")
        return str(output_path), None

    # 1. ElevenLabs (with real word-level alignment)
    eleven_api_key = os.getenv("ELEVENLABS_API_KEY")
    if eleven_api_key and not _ELEVENLABS_DISABLED_REASON:
        try:
            words = _generate_with_elevenlabs_timestamps(text, language, output_path, eleven_api_key, voice_id, elevenlabs_settings)
            return str(output_path), words
        except Exception as e:
            reason = _format_exception(e)
            logger.error(f"ElevenLabs (with-timestamps) failed: {reason}")
            if _should_disable_elevenlabs(reason):
                _ELEVENLABS_DISABLED_REASON = reason
                logger.error(
                    "ElevenLabs disabled for this server run because the API key/voice/model is invalid. "
                    "Fix backend/.env and restart the backend to re-enable ElevenLabs."
                )
    elif eleven_api_key and _ELEVENLABS_DISABLED_REASON and not _ELEVENLABS_DISABLED_LOGGED:
        logger.warning(
            "Skipping ElevenLabs for remaining TTS segments because the previous request failed: %s",
            _ELEVENLABS_DISABLED_REASON,
        )
        _ELEVENLABS_DISABLED_LOGGED = True

    # 2. Edge TTS — no alignment available
    try:
        await _generate_with_edge(text, language, output_path)
        return str(output_path), None
    except Exception as e:
        logger.error(f"Edge TTS failed: {e}")

    # 3. gTTS — no alignment available
    if gTTS:
        try:
            tts = gTTS(text=text, lang=language, slow=False)
            tts.save(str(output_path))
            return str(output_path), None
        except Exception as e:
            logger.error(f"gTTS failed: {e}")

    raise RuntimeError("All TTS providers failed for non-empty speech. Check provider errors and retry.")


async def generate_synced_audio(
    segments: list,
    language: str,
    output_dir: str,
    filename_prefix: str,
    voice_id: str | None = None,
    elevenlabs_settings: dict | None = None,
) -> tuple[str, list[dict], list[dict]]:
    """
    Generates TTS at natural speed — never speeds up audio.
    Audio stays synced with original video timeline so visual animation matches:
      - TTS shorter → pad with silence (visual animation continues in sync)
      - TTS longer → use full TTS, record freeze_region (video frame freezes)
    Original inter-segment gaps preserved exactly so visuals match audio.

    Returns (audio_path, retimed_segments, freeze_regions):
      - retimed_segments: segments with new start/end matching the output audio
      - freeze_regions: [{"video_time_sec", "duration_sec"}] for video merge
    """
    output_dir_path = Path(output_dir).resolve()
    output_dir_path.mkdir(parents=True, exist_ok=True)
    temp_context = tempfile.TemporaryDirectory(prefix="speech_", dir=output_dir_path)
    temp_dir = Path(temp_context.name)

    try:
        final_audio = AudioSegment.empty()
        current_time_ms = 0
        time_shift_ms = 0  # accumulated overflow from longer TTS segments
        retimed_segments: list[dict] = []
        freeze_regions: list[dict] = []

        FADE_MS = 25

        logger.info(
            f"[SYNC] Generating audio for {len(segments)} segments in '{language}' (visual-sync, frame-freeze mode)..."
        )

        for i, seg in enumerate(segments):
            orig_start_ms = round(float(seg["start"]) * 1000)
            orig_end_ms = round(float(seg["end"]) * 1000)
            target_duration_ms = orig_end_ms - orig_start_ms
            text = seg.get("text", "")

            if target_duration_ms <= 0:
                raise ValueError(f"Segment {i + 1} must have a positive duration")

            # Shifted start = original start + accumulated overflow from freeze regions
            shifted_start_ms = orig_start_ms + time_shift_ms

            # Preserve original inter-segment gap exactly (visual animation plays here)
            gap_duration = shifted_start_ms - current_time_ms
            if gap_duration > 0:
                final_audio += AudioSegment.silent(duration=gap_duration)
                current_time_ms += gap_duration
            elif gap_duration < 0:
                logger.warning("[SYNC] Segment %s overlaps by %sms after retime.", i, abs(gap_duration))
                current_time_ms = len(final_audio)

            if not is_tts_speakable_text(text):
                new_start = current_time_ms / 1000.0
                final_audio += AudioSegment.silent(duration=target_duration_ms)
                current_time_ms += target_duration_ms
                retimed_segments.append({**seg, "start": new_start, "end": current_time_ms / 1000.0})
                continue

            seg_filename = f"seg_{i}_{filename_prefix}"
            seg_path, word_timings_local = await generate_tts_with_alignment_async(
                text, language, str(temp_dir), seg_filename, voice_id, elevenlabs_settings
            )

            try:
                audio_seg = _load_audio_segment(seg_path)
                _require_speech(audio_seg, f"Segment {i + 1}")

                if len(audio_seg) > FADE_MS * 2:
                    audio_seg = audio_seg.fade_in(FADE_MS).fade_out(FADE_MS)

                actual_ms = len(audio_seg)
                overflow_ms = actual_ms - target_duration_ms

                new_start_sec = current_time_ms / 1000.0

                if overflow_ms > 0:
                    # TTS longer → freeze video frame at segment end, use full audio
                    freeze_regions.append({
                        "video_time_sec": orig_end_ms / 1000.0,
                        "duration_sec": overflow_ms / 1000.0,
                    })
                    time_shift_ms += overflow_ms
                    final_audio += audio_seg
                    current_time_ms += actual_ms
                    logger.info(
                        "[SYNC] Seg %d: TTS=%dms > orig=%dms (+%dms). "
                        "Freeze at %.2fs for %.2fs. Shift: %dms",
                        i, actual_ms, target_duration_ms, overflow_ms,
                        orig_end_ms / 1000.0, overflow_ms / 1000.0, time_shift_ms,
                    )
                else:
                    # TTS shorter or equal → pad with silence to match original duration
                    # This keeps audio synced with video animation
                    if actual_ms < target_duration_ms:
                        audio_seg = audio_seg + AudioSegment.silent(duration=target_duration_ms - actual_ms)
                    final_audio += audio_seg
                    current_time_ms += len(audio_seg)

                retimed_segment = {
                    **seg,
                    "start": new_start_sec,
                    "end": current_time_ms / 1000.0,
                }
                if word_timings_local:
                    retimed_segment["word_timings"] = [
                        {
                            "text": w["text"],
                            "start": new_start_sec + w["start"],
                            "end": new_start_sec + w["end"],
                        }
                        for w in word_timings_local
                    ]
                retimed_segments.append(retimed_segment)

            except Exception as e:
                raise RuntimeError(f"Speech processing failed for segment {i + 1}: {e}") from e

        if any(is_tts_speakable_text(seg.get("text")) for seg in segments):
            _require_speech(final_audio, "Final audio")

        if len(final_audio) > 500:
            final_audio = final_audio.fade_in(300)

        output_path = output_dir_path / f"{filename_prefix}_synced_{language}.wav"
        final_audio.export(output_path, format="wav")


        logger.info(
            f"[SUCCESS] Audio generated: {output_path} "
            f"(shift: {time_shift_ms}ms, freezes: {len(freeze_regions)}, segs: {len(retimed_segments)})"
        )
        return str(output_path), retimed_segments, freeze_regions

    finally:
        temp_context.cleanup()


async def _generate_with_edge(text: str, language: str, output_path: Path) -> None:
    """Generate audio using Edge TTS (free Azure Neural voices)."""
    VOICE_MAP = {
        "en": "en-US-ChristopherNeural",
        "hi": "hi-IN-SwaraNeural",
        "ta": "ta-IN-ValluvarNeural",
        "es": "es-ES-AlvaroNeural",
        "fr": "fr-FR-DeniseNeural",
        "de": "de-DE-KillianNeural",
        "te": "te-IN-MohanNeural",
        "ml": "ml-IN-MidhunNeural",
        "kn": "kn-IN-GaganNeural",
        "mr": "mr-IN-AarohiNeural",
        "bn": "bn-IN-BashkarNeural",
        "gu": "gu-IN-DhwaniNeural",
        "pa": "pa-IN-OjasNeural",
    }
    voice = VOICE_MAP.get(language, "en-US-ChristopherNeural")
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(output_path))


@retry(
    wait=wait_exponential(multiplier=2, min=3, max=30),
    stop=stop_after_attempt(4),
    retry=retry_if_exception_type((requests.exceptions.RequestException, RuntimeError))
)
def _generate_with_elevenlabs(
    text: str,
    language: str,
    output_path: Path,
    api_key: str,
    voice_id: str | None = None,
    elevenlabs_settings: dict | None = None,
) -> None:
    """Internal helper to call ElevenLabs API."""
    settings = build_elevenlabs_settings({**(elevenlabs_settings or {}), "voice_id": voice_id or (elevenlabs_settings or {}).get("voice_id")})
    voice_id = resolve_elevenlabs_voice_id(settings["voice_id"])

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": settings["model_id"],
        "voice_settings": {
            "stability": settings["stability"],
            "similarity_boost": settings["similarity_boost"],
            "speed": settings["speed"],
        },
    }
    if settings["model_id"] == "eleven_multilingual_v2":
        payload["voice_settings"]["style"] = settings["style"]
        payload["voice_settings"]["use_speaker_boost"] = settings["use_speaker_boost"]

    response = requests.post(url, headers=headers, json=payload, timeout=30)
    if response.status_code != 200:
        raise RuntimeError(
            f"ElevenLabs API error {response.status_code}: {response.text}"
        )

    with open(output_path, "wb") as f:
        f.write(response.content)


def _words_from_character_alignment(alignment: dict) -> list:
    """Group ElevenLabs' character-level alignment into word-level
    {text, start, end} entries (local, 0-based seconds) by splitting on
    whitespace characters."""
    characters = alignment.get("characters") or []
    starts = alignment.get("character_start_times_seconds") or []
    ends = alignment.get("character_end_times_seconds") or []
    if not characters or len(characters) != len(starts) or len(characters) != len(ends):
        return []

    words = []
    current_chars = []
    current_start = None
    for char, char_start, char_end in zip(characters, starts, ends):
        if char.isspace():
            if current_chars:
                words.append({
                    "text": "".join(current_chars),
                    "start": current_start,
                    "end": prev_end,
                })
                current_chars = []
                current_start = None
            continue
        if current_start is None:
            current_start = char_start
        current_chars.append(char)
        prev_end = char_end

    if current_chars:
        words.append({"text": "".join(current_chars), "start": current_start, "end": prev_end})

    return words


def _generate_with_elevenlabs_timestamps(
    text: str,
    language: str,
    output_path: Path,
    api_key: str,
    voice_id: str | None = None,
    elevenlabs_settings: dict | None = None,
) -> list | None:
    """Like _generate_with_elevenlabs, but calls the /with-timestamps
    endpoint to also return real word-level timing (local, 0-based seconds)
    derived from ElevenLabs' character-level alignment. Returns None if
    alignment data isn't present in the response (audio is still written)."""
    settings = build_elevenlabs_settings({**(elevenlabs_settings or {}), "voice_id": voice_id or (elevenlabs_settings or {}).get("voice_id")})
    voice_id = resolve_elevenlabs_voice_id(settings["voice_id"])

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": settings["model_id"],
        "voice_settings": {
            "stability": settings["stability"],
            "similarity_boost": settings["similarity_boost"],
            "speed": settings["speed"],
        },
    }
    if settings["model_id"] == "eleven_multilingual_v2":
        payload["voice_settings"]["style"] = settings["style"]
        payload["voice_settings"]["use_speaker_boost"] = settings["use_speaker_boost"]

    response = requests.post(url, headers=headers, json=payload, timeout=30)
    if response.status_code != 200:
        raise RuntimeError(
            f"ElevenLabs API error {response.status_code}: {response.text}"
        )

    body = response.json()
    audio_bytes = base64.b64decode(body["audio_base64"])
    with open(output_path, "wb") as f:
        f.write(audio_bytes)

    alignment = body.get("alignment")
    if not alignment:
        return None
    words = _words_from_character_alignment(alignment)
    return words or None
