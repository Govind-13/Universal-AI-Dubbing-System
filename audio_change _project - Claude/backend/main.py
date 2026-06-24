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
        text = segment.get("text") or segment.get("subtitle_text") or segment.get("translated_text") or ""
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
from services.lip_sync_service import run_wav2lip
from services.translation_validation_service import validate_translation_json

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
    tts_speaker_boost: bool
):
    try:
        file_location = Path(file_location_str)
        file_stem = file_location.stem
        
        # 1. Extract source audio from the uploaded video
        jobs[job_id]["status"] = "Extracting source audio"
        audio_path = extract_audio(str(file_location), str(AUDIO_DIR))

        # 2. Convert source audio to same-language transcript text
        jobs[job_id]["status"] = "Creating same-language transcript"
        transcription_result = transcribe_audio(audio_path)
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
        jobs[job_id]["status"] = "Verifying translated transcript"
        try:
            translation_validation = validate_translation_json(
                translated_json_path,
                transcription_result.get("segments", []),
                target_language,
            )
        except Exception as val_exc:
            logging.warning(f"Translation validation warning (proceeding anyway): {val_exc}")
            translation_validation = {"warning": str(val_exc)}
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

        # 5. Generate subtitles using retimed timeline
        jobs[job_id]["status"] = "Preparing subtitles"
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
            logging.error(f"Subtitle generation failed: {e}")

        # 6. Merge video + audio (freeze video frames where TTS overflows)
        jobs[job_id]["status"] = "Replacing video audio"
        output_filename = f"{file_stem}_{target_language}.mp4"
        final_video_path = PROCESSED_DIR / output_filename

        lip_sync_result = run_wav2lip(
            video_path=str(file_location),
            audio_path=tts_audio_path,
            output_path=str(final_video_path),
        )

        if lip_sync_result is None:
            merge_audio_video(
                video_path=str(file_location),
                audio_path=tts_audio_path,
                output_path=str(final_video_path),
                freeze_regions=freeze_regions,
            )

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
            "message": "Video processed successfully (Locatization Complete)."
        }

    except Exception as e:
        jobs[job_id]["status"] = "Failed"
        jobs[job_id]["error"] = str(e)
        logging.error(f"Job {job_id} failed: {e}")


@app.post("/upload")
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...), 
    target_language: str = "hi",  # Default to Hindi
    tts_voice_id: str = "default",
    tts_model_id: str = "eleven_multilingual_v2",
    tts_speed: float = 0.90,
    tts_stability: float = 0.75,
    tts_similarity_boost: float = 0.64,
    tts_style: float = 0.0,
    tts_speaker_boost: bool = True,
):
    try:
        file_location = UPLOAD_DIR / file.filename
        with open(file_location, "wb+") as file_object:
            shutil.copyfileobj(file.file, file_object)

        job_id = str(uuid.uuid4())
        jobs[job_id] = {
            "status": "Queued",
            "filename": file.filename,
            "target_language": target_language
        }

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
            tts_speaker_boost
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

        lip_sync_result = run_wav2lip(
            video_path=str(file_location),
            audio_path=tts_audio_path,
            output_path=str(final_video_path),
        )
        if lip_sync_result is None:
            merge_audio_video(
                video_path=str(file_location),
                audio_path=tts_audio_path,
                output_path=str(final_video_path),
                freeze_regions=freeze_regions,
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
