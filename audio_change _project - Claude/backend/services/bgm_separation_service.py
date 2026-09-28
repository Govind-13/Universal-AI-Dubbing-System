import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

BGM_SEPARATION_TIMEOUT_SECONDS = 1800


def separate_vocals_and_bgm(audio_path: str, output_dir: str) -> str | None:
    """Run Demucs to split narration from background music.

    Returns the path to the isolated background-music track (`no_vocals.wav`),
    or None on any failure/timeout/missing-dependency — BGM preservation is
    best-effort and must never break the main pipeline.
    """
    try:
        audio_path = Path(audio_path).resolve()
        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        separation_root = output_dir / "bgm_separation"
        cmd = [
            sys.executable, "-m", "demucs",
            "--two-stems", "vocals",
            "-o", str(separation_root),
            str(audio_path),
        ]

        logger.info(f"Starting BGM separation for: {audio_path}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=BGM_SEPARATION_TIMEOUT_SECONDS,
        )

        if result.returncode != 0:
            logger.warning(f"Demucs separation failed (code {result.returncode}): {result.stderr}")
            return None

        no_vocals_path = separation_root / "htdemucs" / audio_path.stem / "no_vocals.wav"
        if not no_vocals_path.exists():
            logger.warning(f"Demucs did not produce expected output: {no_vocals_path}")
            return None

        logger.info(f"BGM separation complete: {no_vocals_path}")
        return str(no_vocals_path)

    except subprocess.TimeoutExpired:
        logger.warning(f"BGM separation timed out after {BGM_SEPARATION_TIMEOUT_SECONDS}s: {audio_path}")
        return None
    except Exception as e:
        logger.warning(f"BGM separation unavailable/failed: {e}")
        return None
