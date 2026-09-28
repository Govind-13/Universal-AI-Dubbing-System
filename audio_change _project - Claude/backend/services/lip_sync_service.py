"""Run the configured Wav2Lip checkout with isolated writable runtime state."""
import logging
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
import imageio_ffmpeg

MAX_WORKING_HEIGHT = 360
WAV2LIP_TIMEOUT_SECONDS = 1200
LIP_SYNC_DISABLED_MESSAGE = "Lip-sync skipped because this video uses a cartoon or non-human character."

logger = logging.getLogger(__name__)


def friendly_failure_reason(technical_error: str) -> str:
    """Short user-facing reason; the full technical error belongs in logs only."""
    if "Face not detected" in technical_error:
        return ("Lip-sync failed: no human face was detected in the video. "
                "The translated video was produced without lip-sync.")
    if "timed out" in technical_error.lower():
        return ("Lip-sync timed out. The translated video was produced without lip-sync.")
    return ("Lip-sync failed. The translated video was produced without lip-sync; "
            "see backend logs for details.")


def _runtime_env(work_dir: Path, cache_dir: Path | None = None) -> dict:
    env = os.environ.copy()
    cache_dir = cache_dir or work_dir
    for key, folder in (("NUMBA_CACHE_DIR", "numba"), ("MPLCONFIGDIR", "matplotlib"),
                        ("TORCH_HOME", "torch"), ("TEMP", "tmp"), ("TMP", "tmp")):
        target = (work_dir if key in {"TEMP", "TMP"} else cache_dir) / folder
        target.mkdir(parents=True, exist_ok=True)
        env[key] = str(target)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    bin_dir = cache_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    source = Path(imageio_ffmpeg.get_ffmpeg_exe())
    binary = bin_dir / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    if not binary.exists() or binary.stat().st_size != source.stat().st_size:
        shutil.copy2(source, binary)
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    return env


def _inspect_video(video_path: str) -> tuple[bool | None, int]:
    """Sample faces; detector failure leaves inference enabled."""
    try:
        import cv2
        cap = cv2.VideoCapture(video_path)
        try:
            if not cap.isOpened():
                return None, 0
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cascade = Path(__file__).resolve().parents[1] / "assets" / "haarcascade_frontalface_default.xml"
            if not cascade.is_file():
                cascade = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
            if not cascade.is_file():
                return None, height
            detector = cv2.CascadeClassifier(str(cascade))
            if detector.empty():
                return None, height
            read = 0
            for fraction in (0, .2, .4, .6, .8, .95):
                cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int((count - 1) * fraction)))
                ok, frame = cap.read()
                if not ok:
                    continue
                read += 1
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                if len(detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4)):
                    return True, height
            return (False if read else None), height
        finally:
            cap.release()
    except Exception:
        return None, 0


def run_wav2lip(video_path: str, audio_path: str, output_path: str,
                status: dict | None = None) -> str | None:
    status = status if status is not None else {}

    def outcome(state: str, reason: str):
        status.update(state=state, reason=reason)
        print(f"[LIP-SYNC] {state}: {reason}")

    checkout = os.getenv("WAV2LIP_PATH")
    checkpoint = os.getenv("WAV2LIP_CHECKPOINT")
    if not checkout or not checkpoint:
        outcome("not_configured", "Wav2Lip path or checkpoint is not configured.")
        return None
    script = Path(checkout).resolve() / "inference.py"
    checkpoint_path = Path(checkpoint).resolve()
    if not script.is_file() or not checkpoint_path.is_file():
        outcome("failed", "Wav2Lip script or checkpoint does not exist.")
        return None
    python = os.getenv("WAV2LIP_PYTHON")
    if not python:
        if getattr(sys, "frozen", False):
            outcome("failed", "Set WAV2LIP_PYTHON to a Python interpreter for packaged builds.")
            return None
        python = sys.executable
    output = Path(output_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    video_path, audio_path = str(Path(video_path).resolve()), str(Path(audio_path).resolve())
    has_face, height = _inspect_video(video_path)
    if has_face is False and os.getenv("WAV2LIP_SKIP_NO_FACE", "true").lower() == "true":
        outcome("skipped_no_face", "No face found in sampled frames; ordinary dubbing used. Set WAV2LIP_SKIP_NO_FACE=false to force inference.")
        return None
    try:
        with tempfile.TemporaryDirectory(prefix="lipsync_", dir=output.parent) as temp:
            work = Path(temp)
            (work / "temp").mkdir()
            env = _runtime_env(work, output.parent / "runtime_cache")
            check = subprocess.run([python, "-c", "import torch,cv2,librosa; import librosa.filters; print('runtime ready')"],
                cwd=work, env=env, capture_output=True, text=True, encoding="utf8", errors="replace", timeout=120)
            if check.returncode:
                raise RuntimeError("Runtime preflight failed: " + check.stderr[-1500:])
            temporary_output = work / "result.mp4"
            cmd = [python, str(script), "--checkpoint_path", str(checkpoint_path),
                   "--face", video_path, "--audio", audio_path, "--outfile", str(temporary_output), "--nosmooth"]
            if height > MAX_WORKING_HEIGHT:
                cmd += ["--resize_factor", str(math.ceil(height / MAX_WORKING_HEIGHT))]
            result = subprocess.run(cmd, cwd=work, env=env, capture_output=True,
                                    text=True, encoding="utf8", errors="replace", timeout=WAV2LIP_TIMEOUT_SECONDS)
            if result.returncode:
                raise RuntimeError(result.stderr[-1500:])
            if not temporary_output.is_file() or temporary_output.stat().st_size == 0:
                raise RuntimeError("Inference did not create a non-empty video.")
            os.replace(temporary_output, output)
        outcome("completed", "Lip-sync rendered successfully.")
        return str(output)
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        logger.error("Wav2Lip failed for %s:\n%s", video_path, exc)
        outcome("failed", friendly_failure_reason(str(exc)))
        return None
