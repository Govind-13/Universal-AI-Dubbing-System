from pydub import AudioSegment
import imageio_ffmpeg

AudioSegment.converter = imageio_ffmpeg.get_ffmpeg_exe()

try:
    print("Testing with format='mp3'")
    AudioSegment.from_file("backend/test_audioop.py", format="mp3") # any file with format specified
except Exception as e:
    import traceback
    traceback.print_exc()
