
import os
import subprocess
import logging
import re
import imageio_ffmpeg
from pathlib import Path

logger = logging.getLogger(__name__)


def _probe_media_duration(media_path: Path, ffmpeg_exe: str) -> float:
    """Read media duration from FFmpeg without requiring a separate ffprobe binary."""
    result = subprocess.run(
        [ffmpeg_exe, "-hide_banner", "-i", str(media_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr)
    if not match:
        raise RuntimeError(f"Unable to determine media duration: {media_path}")

    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def extract_audio(video_path: str, output_dir: str) -> str:
    """
    Extracts audio from a video file using FFmpeg (direct subprocess call).
    Returns the path to the generated audio file.
    """
    video_path = Path(video_path).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    audio_filename = video_path.stem + ".mp3"
    audio_path = output_dir / audio_filename
    
    # Get the ffmpeg executable path from imageio-ffmpeg
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    print(f"FFmpeg binary: {ffmpeg_exe}")
    
    # Command: ffmpeg -i input -vn -acodec libmp3lame -q:a 4 -y output
    cmd = [
        ffmpeg_exe,
        "-i", str(video_path),
        "-vn",
        "-acodec", "libmp3lame",
        "-q:a", "4",
        "-y",
        str(audio_path)
    ]

    print(f"Extraction started: {video_path} -> {audio_path}")
    print(f"Command: {cmd}")

    try:
        # Run ffmpeg command
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            encoding='utf-8',
            errors='replace'
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg failed (code {result.returncode}): {result.stderr}")
            
        print(f"Audio extracted successfully: {audio_path}")
        return str(audio_path)

    except Exception as e:
        print(f"General Error during audio extraction: {e}")
        raise RuntimeError(f"Audio extraction failed: {str(e)}")

def _build_freeze_filter(freeze_regions: list[dict]) -> str:
    """Build FFmpeg filter_complex that splits video at each freeze point,
    clones the last frame for the overflow duration, then concatenates."""
    regions = sorted(freeze_regions, key=lambda r: r["video_time_sec"])
    filter_parts = []
    concat_inputs = []

    for idx, region in enumerate(regions):
        vt = region["video_time_sec"]
        dur = region["duration_sec"]
        prev_end = regions[idx - 1]["video_time_sec"] if idx > 0 else 0.0

        # Normal video segment before this freeze
        filter_parts.append(
            f"[0:v]trim=start={prev_end:.3f}:end={vt:.3f},setpts=PTS-STARTPTS[seg{idx}]"
        )
        # Freeze: grab one frame at the freeze point, clone it for overflow duration
        filter_parts.append(
            f"[0:v]trim=start={vt:.3f}:end={vt + 0.04:.3f},"
            f"setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration={dur:.3f}[frz{idx}]"
        )
        concat_inputs.append(f"[seg{idx}][frz{idx}]")

    # Final segment: rest of video after last freeze point
    last_vt = regions[-1]["video_time_sec"]
    filter_parts.append(
        f"[0:v]trim=start={last_vt:.3f},setpts=PTS-STARTPTS[segfinal]"
    )
    concat_inputs.append("[segfinal]")

    n_parts = len(regions) * 2 + 1
    fc = "; ".join(filter_parts)
    fc += f"; {''.join(concat_inputs)}concat=n={n_parts}:v=1:a=0[outv]"
    return fc


def merge_audio_video(video_path: str, audio_path: str, output_path: str,
                      freeze_regions: list[dict] | None = None) -> str:
    """
    Merges dubbed audio into video. If freeze_regions is provided, the video
    freezes at each specified point (per-segment frame freeze) so the dubbed
    audio plays fully without speedup. No freeze_regions = simple fast merge.
    """
    video_path = Path(video_path).resolve()
    audio_path = Path(audio_path).resolve()
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    video_duration = _probe_media_duration(video_path, ffmpeg_exe)
    audio_duration = _probe_media_duration(audio_path, ffmpeg_exe)
    temp_output_path = output_path.with_name(f"{output_path.stem}.tmp{output_path.suffix}")
    temp_output_path.unlink(missing_ok=True)

    if freeze_regions:
        filter_complex = _build_freeze_filter(freeze_regions)
        cmd = [
            ffmpeg_exe,
            "-hide_banner",
            "-loglevel", "error",
            "-nostdin",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-filter_complex", filter_complex,
            "-map", "[outv]",
            "-map", "1:a:0",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "20",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            "-shortest",
            "-y",
            str(temp_output_path),
        ]
    else:
        output_duration = max(video_duration, audio_duration)
        cmd = [
            ffmpeg_exe,
            "-hide_banner",
            "-loglevel", "error",
            "-nostdin",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-c:v", "copy",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:a", "aac",
            "-b:a", "192k",
            "-af", "apad",
            "-t", f"{output_duration:.3f}",
            "-movflags", "+faststart",
            "-y",
            str(temp_output_path),
        ]

    logger.info(
        "Merging started: %s + %s -> %s (freezes: %d)",
        video_path, audio_path, output_path, len(freeze_regions or []),
    )

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=900,
        )

        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg failed (code {result.returncode}): {result.stderr}")

        if not temp_output_path.exists() or temp_output_path.stat().st_size == 0:
            raise RuntimeError("FFmpeg completed without creating a valid output file.")

        os.replace(temp_output_path, output_path)

        logger.info(
            "Merge successful: %s (%.2f MB)",
            output_path,
            output_path.stat().st_size / (1024 * 1024),
        )
        return str(output_path)

    except subprocess.TimeoutExpired as e:
        temp_output_path.unlink(missing_ok=True)
        logger.error("Video merge timed out after 900 seconds: %s", output_path)
        raise RuntimeError("Video merge timed out after 15 minutes.") from e
    except Exception as e:
        temp_output_path.unlink(missing_ok=True)
        logger.error("General error during merge: %s", e)
        raise RuntimeError(f"Video merge failed: {str(e)}")
