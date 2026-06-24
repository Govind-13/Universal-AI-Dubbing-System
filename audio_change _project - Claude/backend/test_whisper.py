
import whisper
import sys

try:
    print("Loading Whisper model (tiny)...")
    model = whisper.load_model("tiny")
    print("Model loaded successfully.")
except Exception as e:
    print(f"Error loading model: {e}")
    sys.exit(1)
