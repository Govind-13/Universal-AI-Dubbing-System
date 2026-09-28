from services.audio_processor import merge_audio_video
try:
    print("Testing merge empty...")
    merge_audio_video("media/uploads/test_with_audio.mp4", "test_audio_output/empty_synced_hi.mp3", "test_out_merge2.mp4")
except Exception as e:
    import traceback
    traceback.print_exc()
