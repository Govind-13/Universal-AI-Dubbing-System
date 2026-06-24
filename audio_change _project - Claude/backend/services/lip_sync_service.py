import os
import subprocess
import sys
from pathlib import Path


def run_wav2lip(video_path: str, audio_path: str, output_path: str) -> str | None:
    """
    Runs Wav2Lip lip-sync on a video + audio pair.

    Requires two env vars:
      WAV2LIP_PATH        — path to the cloned Wav2Lip repo directory
      WAV2LIP_CHECKPOINT  — path to the .pth checkpoint file
                            (e.g. Wav2Lip/checkpoints/wav2lip_gan.pth)

    Returns the output path on success, or None if Wav2Lip is not
    configured / unavailable (caller falls back to simple audio merge).

    Setup (one-time):
      git clone https://github.com/Rudrabha/Wav2Lip
      cd Wav2Lip
      pip install -r requirements.txt
      # Download checkpoint: wav2lip_gan.pth from the Wav2Lip release page
      # Place in Wav2Lip/checkpoints/
    """
    wav2lip_dir = os.getenv("WAV2LIP_PATH")
    checkpoint = os.getenv("WAV2LIP_CHECKPOINT")

    if not wav2lip_dir or not checkpoint:
        print("[LIP-SYNC] Skipped — WAV2LIP_PATH / WAV2LIP_CHECKPOINT not set in .env")
        return None

    wav2lip_dir = Path(wav2lip_dir).resolve()
    checkpoint_path = Path(checkpoint).resolve()
    inference_script = wav2lip_dir / "inference.py"

    if not inference_script.exists():
        print(f"[LIP-SYNC] inference.py not found at {inference_script}. Skipping.")
        return None

    if not checkpoint_path.exists():
        print(f"[LIP-SYNC] Checkpoint not found at {checkpoint_path}. Skipping.")
        return None

    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        str(inference_script),
        "--checkpoint_path", str(checkpoint_path),
        "--face", str(video_path),
        "--audio", str(audio_path),
        "--outfile", str(output_path),
        "--nosmooth",
    ]

    print(f"[LIP-SYNC] Running Wav2Lip...")
    print(f"[LIP-SYNC] Command: {' '.join(str(c) for c in cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(wav2lip_dir),
        )

        if result.returncode != 0:
            # Print last 2000 chars of stderr to avoid flooding logs
            print(f"[LIP-SYNC] Wav2Lip failed (code {result.returncode}):\n{result.stderr[-2000:]}")
            return None

        if not output_path.exists():
            print("[LIP-SYNC] Wav2Lip finished but output file not found. Falling back.")
            return None

        print(f"[LIP-SYNC] Lip-sync complete: {output_path}")
        return str(output_path)

    except Exception as e:
        print(f"[LIP-SYNC] Error running Wav2Lip: {e}")
        return None
