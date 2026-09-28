
import os
import subprocess
import edge_tts
import asyncio
import imageio_ffmpeg
from pathlib import Path

def create_test_video(filename="test_with_audio.mp4"):
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    
    # 1. Generate speech using edge-tts
    text = "Hello viewer. This is a test video for the AI Video Localization Platform. We are testing the automatic transcription and translation capabilities."
    audio_temp = "temp_speech.mp3"
    print("Generating speech...")
    
    async def gen_speech():
        communicate = edge_tts.Communicate(text, "en-US-ChristopherNeural")
        await communicate.save(audio_temp)
    
    asyncio.run(gen_speech())
    
    # 2. Generate video and merge with speech
    # Using a 5 second video background
    cmd = [
        ffmpeg_exe,
        "-y",
        "-f", "lavfi", "-i", "testsrc=duration=10:size=640x480:rate=24",
        "-i", audio_temp,
        "-c:v", "libx264", "-c:a", "aac",
        "-map", "0:v:0", "-map", "1:a:0",
        "-shortest",
        filename
    ]
    
    print(f"Generating {filename} with speech...")
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("Video generated successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error generating video: {e.stderr.decode()}")
        raise
    finally:
        if os.path.exists(audio_temp):
            os.remove(audio_temp)

if __name__ == "__main__":
    create_test_video()
