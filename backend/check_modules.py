import importlib

modules = [
    "fastapi", "uvicorn", "pydub", "edge_tts", "whisper", "gTTS", "imageio_ffmpeg", "pydub.effects"
]

for mod in modules:
    try:
        importlib.import_module(mod)
        print(f"{mod}: OK")
    except ImportError as e:
        print(f"{mod}: FAILED - {e}")
