import sys

# ── audioop compatibility for Python 3.13+ ─────────────────────────────────
# Python 3.13 removed the built-in `audioop` module. The `audioop-lts` package
# re-provides it as `audioop`. However, pydub's fallback import path tries
# `import pyaudioop as audioop`, so we must register the module under both names
# in sys.modules BEFORE any pydub import happens.
try:
    import audioop
except ImportError:
    try:
        import pyaudioop as audioop          # just in case pyaudioop exists
    except ImportError:
        audioop = None

if audioop is not None:
    sys.modules["audioop"] = audioop
    sys.modules["pyaudioop"] = audioop
# ───────────────────────────────────────────────────────────────────────────

# Force UTF-8 encoding for stdout/stderr on Windows to avoid charmap errors
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
import asyncio
import uuid
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import uvicorn
import os
import shutil
import logging
import logging.handlers
import threading
import webbrowser
from dotenv import load_dotenv
from pathlib import Path
import json
from datetime import datetime, timezone

# ── Path detection: frozen .exe vs normal dev run ──────────────────────────
if getattr(sys, 'frozen', False):
    _BUNDLE_DIR = Path(sys._MEIPASS)                       # bundled read-only files
    _APP_DIR    = Path(sys.executable).resolve().parent    # writable dir next to .exe
else:
    _BUNDLE_DIR = Path(__file__).resolve().parent
    _APP_DIR    = _BUNDLE_DIR
# ───────────────────────────────────────────────────────────────────────────

# Load .env from app dir (next to .exe or in backend/)
load_dotenv(_APP_DIR / ".env")

# ── Structured logging to logs/ folder ─────────────────────────────────────
_LOGS_DIR = _APP_DIR / "logs"
_LOGS_DIR.mkdir(exist_ok=True)

_log_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s — %(message)s")

_app_handler = logging.handlers.RotatingFileHandler(
    _LOGS_DIR / "app.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
)
_app_handler.setFormatter(_fmt)

_err_handler = logging.handlers.RotatingFileHandler(
    _LOGS_DIR / "error.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
)
_err_handler.setLevel(logging.ERROR)
_err_handler.setFormatter(_fmt)

_console_handler = logging.StreamHandler(sys.stdout)
_console_handler.setFormatter(_fmt)

logging.basicConfig(level=_log_level, handlers=[_console_handler, _app_handler, _err_handler])
# ───────────────────────────────────────────────────────────────────────────

app = FastAPI(title="AI Video Localization API")

@app.get("/api/health")
def health():
    return {"status": "ok"}


# CORS Setup - Allow Frontend to communicate
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Writable directories (next to .exe when frozen, or in backend/ during dev)
BASE_DIR      = _APP_DIR
UPLOAD_DIR    = BASE_DIR / "media" / "uploads"
AUDIO_DIR     = BASE_DIR / "media" / "audio"
PROCESSED_DIR = BASE_DIR / "media" / "processed"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def _segment_for_json(segment: dict, index: int, text_key: str = "text") -> dict:
    payload = {
        "id": segment.get("id", index + 1),
        "start": float(segment.get("start", 0)),
        "end": float(segment.get("end", 0)),
        "start_time": float(segment.get("start", 0)),
        "end_time": float(segment.get("end", 0)),
        text_key: segment.get("text", ""),
    }
    if segment.get("speaker"):
        payload["speaker"] = segment["speaker"]
    if segment.get("words"):
        payload["words"] = segment["words"]
    return payload


def _write_pipeline_json(filename_prefix: str, suffix: str, payload: dict) -> tuple[Path, str]:
    if isinstance(payload.get("segments"), list):
        payload = clean_transcript_payload(payload)
    payload = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    output_path = PROCESSED_DIR / f"{filename_prefix}_{suffix}.json"
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    return output_path, f"/media/processed/{output_path.name}"


def _load_timeline_segments_from_json(json_path: Path) -> list[dict]:
    with open(json_path, "r", encoding="utf-8") as file:
        payload = json.load(file)

    segments = []
    for index, segment in enumerate(payload.get("segments", [])):
        text = segment.get("translated_text") or segment.get("text") or segment.get("subtitle_text") or ""
        if not is_tts_speakable_text(text):
            text = ""
        segments.append(
            {
                "id": segment.get("id", index + 1),
                "start": float(segment.get("start", 0)),
                "end": float(segment.get("end", 0)),
                "text": text,
            }
        )
    return segments

from services.audio_processor import extract_audio, merge_audio_video
from services.transcription_service import transcribe_audio
from services.tts_service import (
    build_elevenlabs_settings,
    generate_tts,
    generate_synced_audio,
    get_elevenlabs_runtime_status,
    is_tts_speakable_text,
)
from services.subtitle_service import build_srt_content, generate_subtitles
from services.text_pipeline_service import TextPipelineService
from services.lip_sync_service import run_wav2lip, LIP_SYNC_DISABLED_MESSAGE


async def _run_lip_sync_step(enable_lip_sync: bool, video_path: str, audio_path: str) -> dict:
    """Run Wav2Lip over the merged video in place, or skip it when the job disabled it."""
    if not enable_lip_sync:
        logging.info(f"Lip-sync disabled for this job; skipping Wav2Lip for {video_path}")
        return {"state": "skipped", "reason": LIP_SYNC_DISABLED_MESSAGE}
    status = {}
    await asyncio.to_thread(
        run_wav2lip, status=status, video_path=video_path,
        audio_path=audio_path, output_path=video_path,
    )
    return status
from services.translation_validation_service import validate_translation_json, TranslationValidationError
from services.decision_service import create_decision_provider, NoopDecisionProvider
from services.translation_service import LANGUAGE_ALIASES, LANGUAGE_PROFILES, _normalize_text
from services.transcript_cleanup_service import clean_transcript_payload, clean_segments, strip_root_text_markers
from services.bgm_separation_service import separate_vocals_and_bgm
from services.audio_mixing_service import mix_narration_with_bgm


def _is_recognized_language(target_language: str) -> bool:
    normalized = _normalize_text(target_language).lower().replace("_", " ")
    return normalized in LANGUAGE_ALIASES or normalized in LANGUAGE_PROFILES


async def _resolve_language_if_unrecognized(target_language: str, decision_provider) -> str:
    """Narrow TypeSafe hook: only fires for genuinely unrecognized language
    codes. Recognized codes (the overwhelming majority) are returned
    unchanged, and translation_service.py's own dictionary-driven routing
    is left completely untouched."""
    if isinstance(decision_provider, NoopDecisionProvider) or _is_recognized_language(target_language):
        return target_language
    resolved = await decision_provider.resolve_language(target_language)
    if resolved:
        logging.info(f"TypeSafe resolved unrecognized language '{target_language}' -> '{resolved}'")
        return resolved
    return target_language

from fastapi.staticfiles import StaticFiles

# Mount media directory for static access
app.mount("/media", StaticFiles(directory=BASE_DIR / "media"), name="media")

jobs = {}

async def process_video_job(
    job_id: str,
    file_location_str: str,
    file_filename: str,
    target_language: str,
    tts_voice_id: str,
    tts_model_id: str,
    tts_speed: float,
    tts_stability: float,
    tts_similarity_boost: float,
    tts_style: float,
    tts_speaker_boost: bool,
    enable_lip_sync: bool = True,
):
    decision_provider = create_decision_provider()
    try:
        file_location = Path(file_location_str)
        file_stem = file_location.stem
        target_language = await _resolve_language_if_unrecognized(target_language, decision_provider)

        # 1. Extract source audio from the uploaded video
        jobs[job_id]["status"] = "Extracting source audio"
        audio_path = extract_audio(str(file_location), str(AUDIO_DIR))

        # 1b. Separate background music from narration (best-effort; None if
        # Demucs is unavailable/fails, in which case BGM preservation is
        # simply skipped and today's TTS-only audio behavior is unchanged)
        jobs[job_id]["status"] = "Separating background music"
        bgm_path = await asyncio.to_thread(separate_vocals_and_bgm, audio_path, str(AUDIO_DIR))

        # 2. Convert source audio to same-language transcript text
        jobs[job_id]["status"] = "Creating same-language transcript"
        transcription_result = transcribe_audio(audio_path)
        transcription_result["segments"] = clean_segments(transcription_result.get("segments", []))
        if isinstance(transcription_result.get("text"), str):
            transcription_result["text"] = strip_root_text_markers(transcription_result["text"])
        transcript_json_path, transcript_json_url = _write_pipeline_json(
            file_stem,
            "original_transcript",
            {
                "type": "original_transcript",
                "source_video": file_filename,
                "source_audio": Path(audio_path).name,
                "stt_provider": transcription_result.get("provider"),
                "language": transcription_result.get("language"),
                "language_code": transcription_result.get(
                    "language_code", transcription_result.get("language")
                ),
                "language_probability": transcription_result.get("language_probability"),
                "text": transcription_result.get("text", ""),
                "segments": [
                    _segment_for_json(segment, index, "original_text")
                    for index, segment in enumerate(transcription_result.get("segments", []))
                ],
            },
        )

        # 3. Translate transcript text into the selected classroom code-mix style
        async def _translate_and_write_json():
            jobs[job_id]["status"] = "Translating transcript"
            text_pipeline_service = TextPipelineService()
            text_pipeline_result = await text_pipeline_service.process_segments(
                transcription_result["segments"],
                target_language,
            )
            final_text_segments = text_pipeline_result["subtitle_segments"]
            translated_transcript_segments = text_pipeline_result["reviewed_segments"]
            translated_json_path, translated_json_url = _write_pipeline_json(
                file_stem,
                f"{target_language}_translated_transcript",
                {
                    "type": "translated_transcript",
                    "source_video": file_filename,
                    "source_transcript_json": transcript_json_path.name,
                    "source_language": transcription_result.get("language"),
                    "target_language": target_language,
                    "translation_mode": text_pipeline_result["stage_status"].get("translation_mode"),
                    "segments": [
                        {
                            "id": source_segment.get("id", index + 1),
                            "start": float(translated_segment.get("start", 0)),
                            "end": float(translated_segment.get("end", 0)),
                            "start_time": float(translated_segment.get("start", 0)),
                            "end_time": float(translated_segment.get("end", 0)),
                            "original_text": source_segment.get("text", ""),
                            "translated_text": translated_segment.get("text", ""),
                            "subtitle_text": (
                                final_text_segments[index].get("text", "")
                                if index < len(final_text_segments)
                                else translated_segment.get("text", "")
                            ),
                            "text": (
                                final_text_segments[index].get("text", "")
                                if index < len(final_text_segments)
                                else translated_segment.get("text", "")
                            ),
                            **(
                                {"speaker": source_segment["speaker"]}
                                if source_segment.get("speaker")
                                else {}
                            ),
                            **(
                                {"source_words": source_segment["words"]}
                                if source_segment.get("words")
                                else {}
                            ),
                        }
                        for index, (source_segment, translated_segment) in enumerate(
                            zip(
                                transcription_result.get("segments", []),
                                translated_transcript_segments,
                            )
                        )
                    ],
                },
            )
            return text_pipeline_result, translated_transcript_segments, translated_json_path, translated_json_url

        (
            text_pipeline_result,
            translated_transcript_segments,
            translated_json_path,
            translated_json_url,
        ) = await _translate_and_write_json()

        jobs[job_id]["status"] = "Verifying translated transcript"
        try:
            translation_validation = validate_translation_json(
                translated_json_path,
                transcription_result.get("segments", []),
                target_language,
            )
        except TranslationValidationError as validation_error:
            if isinstance(decision_provider, NoopDecisionProvider):
                # Feature disabled/unconfigured: reproduce today's exact
                # hard-fail behavior, no override.
                raise
            decision = await decision_provider.evaluate_translation_quality({
                "errors": str(validation_error),
                "target_language": target_language,
            })
            if decision == "RETRY":
                (
                    text_pipeline_result,
                    translated_transcript_segments,
                    translated_json_path,
                    translated_json_url,
                ) = await _translate_and_write_json()
                try:
                    translation_validation = validate_translation_json(
                        translated_json_path,
                        transcription_result.get("segments", []),
                        target_language,
                    )
                except TranslationValidationError as retry_error:
                    translation_validation = {
                        "valid": False,
                        "overridden_by": "typesafe_human_review_after_retry",
                        "errors": str(retry_error),
                    }
            elif decision == "ACCEPT":
                translation_validation = {
                    "valid": False,
                    "overridden_by": "typesafe_accept",
                    "errors": str(validation_error),
                }
            else:  # HUMAN_REVIEW, or any unexpected answer
                translation_validation = {
                    "valid": False,
                    "overridden_by": "typesafe_human_review",
                    "errors": str(validation_error),
                }
        final_text_segments = _load_timeline_segments_from_json(translated_json_path)
        
        # 4. Generate ElevenLabs/fallback TTS audio (freestyle timeline)
        jobs[job_id]["status"] = "Generating ElevenLabs audio"
        elevenlabs_settings = build_elevenlabs_settings({
            "voice_id": tts_voice_id,
            "model_id": tts_model_id,
            "speed": tts_speed,
            "stability": tts_stability,
            "similarity_boost": tts_similarity_boost,
            "style": tts_style,
            "use_speaker_boost": tts_speaker_boost,
        })
        tts_lang = "en" if target_language == "tanglish" else target_language
        tts_audio_path, retimed_segments, freeze_regions = await generate_synced_audio(
            segments=final_text_segments,
            language=tts_lang,
            output_dir=str(AUDIO_DIR),
            filename_prefix=file_stem,
            voice_id=elevenlabs_settings["voice_id"],
            elevenlabs_settings=elevenlabs_settings,
        )
        elevenlabs_status = get_elevenlabs_runtime_status()

        # 4b. Mix translated narration back with the preserved original BGM
        final_audio_path = tts_audio_path
        bgm_status = {"state": "unavailable"}
        if bgm_path:
            jobs[job_id]["status"] = "Mixing background music with narration"
            try:
                final_audio_path = await asyncio.to_thread(
                    mix_narration_with_bgm, bgm_path, tts_audio_path, retimed_segments,
                    str(AUDIO_DIR / f"{file_stem}_mixed.wav"),
                )
                bgm_status = {"state": "mixed"}
            except Exception as e:
                logging.error(f"BGM mixing failed, falling back to TTS-only audio: {e}")
                bgm_status = {"state": "failed", "reason": str(e)}

        # 5. Generate subtitles using retimed timeline
        retimed_subtitle_segments = [
            {**segment, "text": subtitle.get("text", "")}
            for segment, subtitle in zip(retimed_segments, text_pipeline_result["subtitle_segments"])
        ]
        jobs[job_id]["status"] = "Preparing subtitles"
        subtitle_url = None
        subtitle_content = None
        try:
            subtitle_content = build_srt_content(retimed_subtitle_segments)
            subtitle_path = generate_subtitles(
                segments=retimed_subtitle_segments,
                output_dir=str(PROCESSED_DIR),
                filename_prefix=file_stem,
                language=target_language,
            )
            if subtitle_path:
                subtitle_url = f"/media/processed/{Path(subtitle_path).name}"
        except Exception as e:
            logging.error(f"Subtitle generation failed: {e}")

        # 6. Merge video + audio (freeze video frames where TTS overflows)
        jobs[job_id]["status"] = "Replacing video audio"
        output_filename = f"{file_stem}_{target_language}.mp4"
        final_video_path = PROCESSED_DIR / output_filename

        await asyncio.to_thread(
            merge_audio_video, video_path=str(file_location), audio_path=final_audio_path,
            output_path=str(final_video_path), freeze_regions=freeze_regions,
        )
        lip_sync_status = await _run_lip_sync_step(enable_lip_sync, str(final_video_path), final_audio_path)

        video_url = f"/media/processed/{output_filename}"
        original_video_url = f"/media/uploads/{file_location.name}"

        jobs[job_id]["status"] = "Completed"
        jobs[job_id]["result"] = {
            "status": "success",
            "filename": file_filename,
            "video_url": video_url,
            "original_video_url": original_video_url,
            "subtitle_url": subtitle_url,
            "subtitle": {
                "format": "srt",
                "language": target_language,
                "url": subtitle_url,
                "content": subtitle_content,
            },
            "transcription": {
                **transcription_result,
                "cleaned_segments": text_pipeline_result["cleaned_segments"],
                "cleaned_text": text_pipeline_result["cleaned_text"],
                "json_url": transcript_json_url,
                "json_filename": transcript_json_path.name,
            },
            "translation": {
                "target_language": target_language,
                "segments": final_text_segments,
                "transcript_segments": translated_transcript_segments,
                "raw_segments": text_pipeline_result["translated_segments"],
                "text": text_pipeline_result["subtitle_text"],
                "transcript_text": text_pipeline_result["translated_text"],
                "json_url": translated_json_url,
                "json_filename": translated_json_path.name,
                "validation": translation_validation,
            },
            "text_pipeline": {
                "stage_status": text_pipeline_result["stage_status"],
                "subtitle_segments": final_text_segments,
            },
            "tts": {
                "provider": "elevenlabs" if elevenlabs_status["available"] else "fallback",
                "voice_id": elevenlabs_settings["voice_id"],
                "settings": elevenlabs_settings,
                "elevenlabs": elevenlabs_status,
            },
            "lip_sync": lip_sync_status,
            "lip_sync_status": lip_sync_status.get("state"),
            "lip_sync_message": lip_sync_status.get("reason"),
            "bgm": bgm_status,
            "warnings": (
                ([lip_sync_status["reason"]] if lip_sync_status.get("state") == "failed" else [])
                + (
                    [f"Translation quality flagged by TypeSafe ({translation_validation['overridden_by']}): {translation_validation['errors']}"]
                    if isinstance(translation_validation, dict) and translation_validation.get("overridden_by")
                    else []
                )
            ),
            "message": "Video processed successfully."
        }

    except Exception as e:
        if isinstance(decision_provider, NoopDecisionProvider):
            jobs[job_id]["status"] = "Failed"
            jobs[job_id]["error"] = str(e)
            logging.error(f"Job {job_id} failed: {e}")
            return

        decision = await decision_provider.route_pipeline_failure({
            "stage": jobs[job_id].get("status"),
            "error": str(e),
            "job_id": job_id,
        })

        if decision == "retry" and not jobs[job_id].get("_retried"):
            jobs[job_id]["_retried"] = True
            logging.warning(f"Job {job_id} failed at '{jobs[job_id].get('status')}'; TypeSafe requested retry: {e}")
            await process_video_job(
                job_id, file_location_str, file_filename, target_language,
                tts_voice_id, tts_model_id, tts_speed, tts_stability,
                tts_similarity_boost, tts_style, tts_speaker_boost, enable_lip_sync,
            )
            return

        if decision == "continue":
            jobs[job_id]["status"] = "Failed"
            jobs[job_id]["error"] = str(e)
            jobs[job_id]["error_classification"] = "continue_requested_but_unsupported"
            logging.error(f"Job {job_id} failed: {e} (TypeSafe requested 'continue', not supported for a top-level failure)")
        else:
            jobs[job_id]["status"] = "Failed"
            jobs[job_id]["error"] = str(e)
            jobs[job_id]["error_classification"] = decision
            logging.error(f"Job {job_id} failed: {e} (classification: {decision})")


async def process_lipsync_only_job(
    job_id: str,
    file_location_str: str,
    file_filename: str,
    separate_audio_path: str | None,
):
    """
    Lip-sync-only pipeline: skips transcription/translation/TTS entirely.
    Runs Wav2Lip against either the video's own embedded audio track or a
    separately uploaded dub-audio file. Does NOT fall back to a plain
    merge on Wav2Lip failure — that would silently re-merge the video with
    its own audio (a no-op) and misreport as success, so a failure here
    must surface as "Failed".
    """
    decision_provider = create_decision_provider()
    try:
        file_location = Path(file_location_str)
        file_stem = file_location.stem

        if separate_audio_path:
            jobs[job_id]["status"] = "Using uploaded audio track"
            audio_path = separate_audio_path
        else:
            jobs[job_id]["status"] = "Extracting existing audio track"
            audio_path = extract_audio(str(file_location), str(AUDIO_DIR))

        jobs[job_id]["status"] = "Running lip-sync"
        output_filename = f"{file_stem}_lipsync.mp4"
        final_video_path = PROCESSED_DIR / output_filename

        lip_sync_status = {}
        lip_sync_result = await asyncio.to_thread(
            run_wav2lip,
            status=lip_sync_status,
            video_path=str(file_location),
            audio_path=audio_path,
            output_path=str(final_video_path),
        )

        if lip_sync_result is None:
            # This "Failed" outcome is intentional by design (see docstring) — do
            # not let TypeSafe introduce a silent fallback here. Only a bounded,
            # single "retry" is honored; every other decision keeps today's exact
            # behavior unchanged.
            if not isinstance(decision_provider, NoopDecisionProvider) and not jobs[job_id].get("_retried"):
                decision = await decision_provider.route_pipeline_failure({
                    "stage": "Running lip-sync",
                    "error": "lip-sync produced no output",
                    "job_id": job_id,
                })
                if decision == "retry":
                    jobs[job_id]["_retried"] = True
                    logging.warning(f"Job {job_id} (lip-sync-only) lip-sync produced no output; TypeSafe requested retry")
                    await process_lipsync_only_job(job_id, file_location_str, file_filename, separate_audio_path)
                    return

            jobs[job_id]["status"] = "Failed"
            jobs[job_id]["error"] = (
                "Lip-sync could not be produced. Wav2Lip is unavailable, its checkpoint "
                "is missing, or processing failed/timed out."
            )
            logging.error(f"Job {job_id} (lip-sync-only) failed: lip-sync produced no output")
            return

        jobs[job_id]["status"] = "Completed"
        jobs[job_id]["result"] = {
            "status": "success",
            "mode": "lipsync_only",
            "filename": file_filename,
            "video_url": f"/media/processed/{output_filename}",
            "original_video_url": f"/media/uploads/{file_location.name}",
            "audio_source": "uploaded" if separate_audio_path else "embedded",
            "message": "Lip-sync completed using the "
            + ("uploaded" if separate_audio_path else "existing")
            + " audio track.",
        }

    except Exception as e:
        if isinstance(decision_provider, NoopDecisionProvider):
            jobs[job_id]["status"] = "Failed"
            jobs[job_id]["error"] = str(e)
            logging.error(f"Job {job_id} (lip-sync-only) failed: {e}")
            return

        decision = await decision_provider.route_pipeline_failure({
            "stage": jobs[job_id].get("status"),
            "error": str(e),
            "job_id": job_id,
        })

        if decision == "retry" and not jobs[job_id].get("_retried"):
            jobs[job_id]["_retried"] = True
            logging.warning(f"Job {job_id} (lip-sync-only) failed at '{jobs[job_id].get('status')}'; TypeSafe requested retry: {e}")
            await process_lipsync_only_job(job_id, file_location_str, file_filename, separate_audio_path)
            return

        jobs[job_id]["status"] = "Failed"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["error_classification"] = decision
        logging.error(f"Job {job_id} (lip-sync-only) failed: {e} (classification: {decision})")


@app.post("/upload")
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    pipeline_mode: str = "full",  # "full" or "lipsync_only"
    audio_file: UploadFile | None = File(None),  # optional separate dub audio for lipsync_only
    target_language: str = "hi",  # Default to Hindi
    tts_voice_id: str = "default",
    tts_model_id: str = "eleven_multilingual_v2",
    tts_speed: float = 0.90,
    tts_stability: float = 0.75,
    tts_similarity_boost: float = 0.64,
    tts_style: float = 0.0,
    tts_speaker_boost: bool = True,
    enable_lip_sync: bool = True,
):
    try:
        file_location = UPLOAD_DIR / file.filename
        with open(file_location, "wb+") as file_object:
            shutil.copyfileobj(file.file, file_object)

        separate_audio_path = None
        if pipeline_mode == "lipsync_only" and audio_file is not None and audio_file.filename:
            audio_subdir = AUDIO_DIR / "lipsync_uploads"
            audio_subdir.mkdir(parents=True, exist_ok=True)
            audio_location = audio_subdir / audio_file.filename
            with open(audio_location, "wb+") as audio_object:
                shutil.copyfileobj(audio_file.file, audio_object)
            separate_audio_path = str(audio_location)

        job_id = str(uuid.uuid4())
        jobs[job_id] = {
            "status": "Queued",
            "filename": file.filename,
            "target_language": target_language,
            "pipeline_mode": pipeline_mode,
        }

        if pipeline_mode == "lipsync_only":
            background_tasks.add_task(
                process_lipsync_only_job,
                job_id,
                str(file_location),
                file.filename,
                separate_audio_path,
            )
        else:
            background_tasks.add_task(
                process_video_job,
                job_id,
                str(file_location),
                file.filename,
                target_language,
                tts_voice_id,
                tts_model_id,
                tts_speed,
                tts_stability,
                tts_similarity_boost,
                tts_style,
                tts_speaker_boost,
                enable_lip_sync,
            )

        return {"job_id": job_id, "status": "Queued"}
    except Exception as e:
        logging.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status/{job_id}")
def get_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]

class SegmentItem(BaseModel):
    start: float
    end: float
    text: str

class RerenderRequest(BaseModel):
    video_filename: str
    target_language: str
    segments: List[SegmentItem]
    tts_voice_id: str = "default"
    tts_model_id: str = "eleven_multilingual_v2"
    tts_speed: float = 0.90
    tts_stability: float = 0.75
    tts_similarity_boost: float = 0.64
    tts_style: float = 0.0
    tts_speaker_boost: bool = True
    enable_lip_sync: bool = True


@app.post("/rerender")
async def rerender_video(request: RerenderRequest):
    try:
        file_location = UPLOAD_DIR / request.video_filename
        if not file_location.exists():
            raise HTTPException(status_code=404, detail=f"Original video not found: {request.video_filename}")

        file_stem = Path(request.video_filename).stem
        target_language = request.target_language
        edited_segments = [s.model_dump() for s in request.segments]
        edited_json_path, edited_json_url = _write_pipeline_json(
            file_stem,
            f"{target_language}_edited_transcript",
            {
                "type": "edited_translated_transcript",
                "source_video": request.video_filename,
                "target_language": target_language,
                "segments": [
                    _segment_for_json(segment, index, "translated_text")
                    for index, segment in enumerate(edited_segments)
                ],
            },
        )
        edited_segments = _load_timeline_segments_from_json(edited_json_path)

        # 0. Reuse (or re-extract) the original source audio to isolate BGM
        source_audio_path = AUDIO_DIR / f"{file_stem}.mp3"
        if not source_audio_path.exists():
            source_audio_path = Path(extract_audio(str(file_location), str(AUDIO_DIR)))
        bgm_path = await asyncio.to_thread(separate_vocals_and_bgm, str(source_audio_path), str(AUDIO_DIR))

        # 1. Generate TTS Audio (freestyle timeline)
        elevenlabs_settings = build_elevenlabs_settings(
            {
                "voice_id": request.tts_voice_id,
                "model_id": request.tts_model_id,
                "speed": request.tts_speed,
                "stability": request.tts_stability,
                "similarity_boost": request.tts_similarity_boost,
                "style": request.tts_style,
                "use_speaker_boost": request.tts_speaker_boost,
            }
        )
        tts_lang = "en" if target_language == "tanglish" else target_language
        tts_audio_path, retimed_segments, freeze_regions = await generate_synced_audio(
            segments=edited_segments,
            language=tts_lang,
            output_dir=str(AUDIO_DIR),
            filename_prefix=file_stem,
            voice_id=elevenlabs_settings["voice_id"],
            elevenlabs_settings=elevenlabs_settings,
        )
        elevenlabs_status = get_elevenlabs_runtime_status()

        # 1b. Mix translated narration back with the preserved original BGM
        final_audio_path = tts_audio_path
        bgm_status = {"state": "unavailable"}
        if bgm_path:
            try:
                final_audio_path = await asyncio.to_thread(
                    mix_narration_with_bgm, bgm_path, tts_audio_path, retimed_segments,
                    str(AUDIO_DIR / f"{file_stem}_mixed.wav"),
                )
                bgm_status = {"state": "mixed"}
            except Exception as e:
                logging.error(f"BGM mixing failed, falling back to TTS-only audio: {e}")
                bgm_status = {"state": "failed", "reason": str(e)}

        # 2. Generate Subtitles (SRT) using retimed timeline
        subtitle_url = None
        subtitle_content = None
        try:
            subtitle_content = build_srt_content(retimed_segments)
            subtitle_path = generate_subtitles(
                segments=retimed_segments,
                output_dir=str(PROCESSED_DIR),
                filename_prefix=file_stem,
                language=target_language,
            )
            if subtitle_path:
                subtitle_url = f"/media/processed/{Path(subtitle_path).name}"
        except Exception as e:
            print(f"Subtitle failed: {e}")

        # 3. Re-compose Video (freeze frames where TTS overflows)
        output_filename = f"{file_stem}_{target_language}.mp4"
        final_video_path = PROCESSED_DIR / output_filename

        await asyncio.to_thread(
            merge_audio_video, video_path=str(file_location), audio_path=final_audio_path,
            output_path=str(final_video_path), freeze_regions=freeze_regions,
        )
        lip_sync_status = await _run_lip_sync_step(
            request.enable_lip_sync, str(final_video_path), final_audio_path
        )

        return {
            "status": "success",
            "video_url": f"/media/processed/{output_filename}",
            "subtitle_url": subtitle_url,
            "subtitle": {
                "format": "srt",
                "language": target_language,
                "url": subtitle_url,
                "content": subtitle_content,
            },
            "translation": {
                "target_language": target_language,
                "segments": edited_segments,
                "json_url": edited_json_url,
                "json_filename": edited_json_path.name,
            },
            "tts": {
                "provider": "elevenlabs" if elevenlabs_status["available"] else "fallback",
                "voice_id": elevenlabs_settings["voice_id"],
                "settings": elevenlabs_settings,
                "elevenlabs": elevenlabs_status,
            },
            "lip_sync": lip_sync_status,
            "lip_sync_status": lip_sync_status.get("state"),
            "lip_sync_message": lip_sync_status.get("reason"),
            "bgm": bgm_status,
            "warnings": ([lip_sync_status["reason"]] if lip_sync_status.get("state") == "failed" else []),
            "message": "Video re-rendered with edited timeline.",
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Re-render failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("startup")
async def _on_startup():
    # Auto-open browser only when running as compiled .exe
    if getattr(sys, 'frozen', False):
        threading.Timer(1.5, lambda: webbrowser.open("http://localhost:8000")).start()

# Serve bundled React frontend at root — MUST be mounted last so API routes take priority
_frontend_dist = _BUNDLE_DIR / "frontend_dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="frontend")

if __name__ == "__main__":
    if getattr(sys, 'frozen', False):
        uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
    else:
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
