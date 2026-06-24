
import os
from pathlib import Path

def format_timestamp(seconds: float) -> str:
    """
    Converts seconds (float) to SRT timestamp format (HH:MM:SS,mmm).
    """
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hrs:02}:{mins:02}:{secs:02},{millis:03}"


def build_srt_content(segments: list) -> str:
    """
    Renders subtitle segments to SRT text.
    """
    blocks = []

    for segment in segments:
        text = str(segment.get("text", "")).strip()
        if not text:
            continue

        start = format_timestamp(segment["start"])
        end = format_timestamp(segment["end"])
        blocks.append(f"{len(blocks) + 1}\n{start} --> {end}\n{text}")

    if not blocks:
        return ""

    return "\n\n".join(blocks) + "\n"


def retime_segments(segments: list, freeze_regions: list[dict]) -> list:
    """Shift segment timestamps forward to account for frame-freeze insertions."""
    if not freeze_regions:
        return segments
    regions = sorted(freeze_regions, key=lambda r: r["start_sec"])
    retimed = []
    for seg in segments:
        start = float(seg["start"])
        end = float(seg["end"])
        shift = sum(r["duration_sec"] for r in regions if r["start_sec"] <= start)
        retimed.append({**seg, "start": start + shift, "end": end + shift})
    return retimed


def generate_subtitles(segments: list, output_dir: str, filename_prefix: str, language: str) -> str:
    """
    Generates an SRT subtitle file from transcription segments.
    Returns path to the .srt file.
    """
    try:
        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"{filename_prefix}_{language}.srt"
        output_path = output_dir / filename
        srt_content = build_srt_content(segments)
        
        print(f"Generating Subtitles ({language})...")
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(srt_content)
                
        print(f"Subtitles generated: {output_path}")
        return str(output_path)

    except Exception as e:
        print(f"Subtitle generation failed: {e}")
        # Non-critical failure, don't crash whole pipeline?
        # Better to raise so main knows.
        raise RuntimeError(f"Subtitle generation failed: {str(e)}")
