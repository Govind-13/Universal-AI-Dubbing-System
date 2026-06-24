from services.audio_processor import merge_audio_video
import os

try:
    print("Testing merge...")
    merge_audio_video("media/uploads/test_with_audio.mp4", "test_audio_output/test_vid_synced_hi.mp3", "test_out_merge.mp4")
    print("Success")
except Exception as e:
    import traceback
    traceback.print_exc()
