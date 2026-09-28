from pydub import AudioSegment
import imageio_ffmpeg
import os

ffprobe_dir = r"C:\Program Files (x86)\Digiarty\Winxvideo AI"
os.environ["PATH"] = ffprobe_dir + os.pathsep + os.environ.get("PATH", "")

AudioSegment.converter = imageio_ffmpeg.get_ffmpeg_exe()

try:
    print("Testing AudioSegment with ffprobe in path...")
    
    # Generate 1s silent audio to test
    silent = AudioSegment.silent(duration=1000)
    silent.export("test_silent.mp3", format="mp3")
    
    seg = AudioSegment.from_file("test_silent.mp3")
    print("Loaded successfully! Duration raw:", len(seg))
except Exception as e:
    import traceback
    traceback.print_exc()

