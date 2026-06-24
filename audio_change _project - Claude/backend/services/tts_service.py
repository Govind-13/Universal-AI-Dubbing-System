import os
import requests
import asyncio
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

    try:
        return AudioSegment.from_file(audio_path)
    except FileNotFoundError as exc:
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [
            ffmpeg_exe,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(audio_path),
            "-f",
            "wav",
            "-",
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
        )
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"FFmpeg audio decode failed: {stderr}") from exc

        return AudioSegment.from_file(io.BytesIO(result.stdout), format="wav")


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

    # Final fallback: create silence if all TTS fail
    silent = AudioSegment.silent(duration=1000)
    silent.export(output_path, format="mp3")
    return str(output_path)


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
    Follows original video timeline exactly:
      - TTS shorter → pad with silence (video animation continues normally)
      - TTS longer → use full TTS, record freeze_region (video frame freezes)
    Original inter-segment gaps are preserved so video animation plays through.
    Video duration increases when TTS overflows.

    Returns (audio_path, retimed_segments, freeze_regions):
      - retimed_segments: segments with new start/end matching the output audio
      - freeze_regions: [{"video_time_sec", "duration_sec"}] for video merge
    """
    output_dir_path = Path(output_dir).resolve()
    temp_dir = output_dir_path / "temp_segments"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    final_audio = AudioSegment.empty()
    current_time_ms = 0
    time_shift_ms = 0  # accumulated overflow from longer TTS segments
    retimed_segments: list[dict] = []
    freeze_regions: list[dict] = []

    FADE_MS = 25

    logger.info(
        f"[SYNC] Generating audio for {len(segments)} segments in '{language}' (no-speedup, frame-freeze mode)..."
    )

    for i, seg in enumerate(segments):
        orig_start_ms = round(float(seg["start"]) * 1000)
        orig_end_ms = round(float(seg["end"]) * 1000)
        target_duration_ms = orig_end_ms - orig_start_ms
        text = seg.get("text", "")

        if target_duration_ms <= 0:
            logger.warning("[SYNC] Skipping segment %s with invalid duration: %sms", i, target_duration_ms)
            continue

        # Shifted start = original start + accumulated overflow
        shifted_start_ms = orig_start_ms + time_shift_ms

        # Preserve original inter-segment gap (silence where video animation plays)
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
        seg_path = await generate_tts_async(text, language, str(temp_dir), seg_filename, voice_id, elevenlabs_settings)

        try:
            audio_seg = _load_audio_segment(seg_path)

            if len(audio_seg) > FADE_MS * 2:
                audio_seg = audio_seg.fade_in(FADE_MS).fade_out(FADE_MS)

            actual_ms = len(audio_seg)
            overflow_ms = actual_ms - target_duration_ms

            new_start_sec = current_time_ms / 1000.0

            if overflow_ms > 50:
                # TTS longer → freeze video frame, use full audio
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
                # TTS shorter or equal → pad with silence, video animation continues
                if actual_ms < target_duration_ms:
                    audio_seg = audio_seg + AudioSegment.silent(duration=target_duration_ms - actual_ms)
                final_audio += audio_seg
                current_time_ms += len(audio_seg)

            retimed_segments.append({
                **seg,
                "start": new_start_sec,
                "end": current_time_ms / 1000.0,
            })

        except Exception as e:
            logger.error(f"Error processing segment {i}: {e}")
            new_start_sec = current_time_ms / 1000.0
            final_audio += AudioSegment.silent(duration=target_duration_ms)
            current_time_ms += target_duration_ms
            retimed_segments.append({**seg, "start": new_start_sec, "end": current_time_ms / 1000.0})

    if len(final_audio) > 500:
        final_audio = final_audio.fade_in(300)

    output_path = output_dir_path / f"{filename_prefix}_synced_{language}.wav"
    final_audio.export(output_path, format="wav")

    shutil.rmtree(temp_dir, ignore_errors=True)

    logger.info(
        f"[SUCCESS] Audio generated: {output_path} "
        f"(shift: {time_shift_ms}ms, freezes: {len(freeze_regions)}, segs: {len(retimed_segments)})"
    )
    return str(output_path), retimed_segments, freeze_regions


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
