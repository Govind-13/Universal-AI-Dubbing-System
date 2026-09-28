from pydub import AudioSegment
import imageio_ffmpeg
AudioSegment.converter = imageio_ffmpeg.get_ffmpeg_exe()

try:
    # Try reading from a non-existent file, does it say WinError 2?
    AudioSegment.from_file("does_not_exist.mp3")
except Exception as e:
    import traceback
    traceback.print_exc()

import asyncio
from edge_tts import Communicate
async def generate():
    comm = Communicate("Hello", "en-US-ChristopherNeural")
    await comm.save("test_edge.mp3")
    
asyncio.run(generate())
try:
    AudioSegment.from_file("test_edge.mp3")
except Exception as e:
    import traceback
    traceback.print_exc()
