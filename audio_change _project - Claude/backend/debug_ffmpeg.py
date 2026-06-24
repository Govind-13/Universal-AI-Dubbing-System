
import imageio_ffmpeg
import subprocess
import os

# Use relative paths for portability in this environment
base_dir = os.path.dirname(os.path.abspath(__file__))
video_path = os.path.join(base_dir, "media", "uploads", "dummy_video.mp4")
audio_dir = os.path.join(base_dir, "media", "audio")
os.makedirs(audio_dir, exist_ok=True)
audio_path = os.path.join(audio_dir, "dummy_video.mp3")

ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

cmd = [ffmpeg_exe, "-i", video_path, "-vn", "-acodec", "libmp3lame", "-y", audio_path]
print(f"Running: {cmd}")

try:
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    print("Return Code:", result.returncode)
    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)
except Exception as e:
    print(f"Execution failed: {e}")
