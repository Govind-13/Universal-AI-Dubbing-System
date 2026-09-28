import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from services.tts_service import _generate_with_elevenlabs

load_dotenv()

def test_elevenlabs():
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("FAIL: ELEVENLABS_API_KEY not found in .env")
        return
    
    print(f"API Key found: {api_key[:5]}...{api_key[-4:] if len(api_key)>10 else ''}")
    
    output_dir = Path("test_audio_output")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "test_elevenlabs_out.mp3"
    
    print("Testing ElevenLabs generation...")
    try:
        _generate_with_elevenlabs(
            text="Hello, this is a test to verify if ElevenLabs text to speech is working correctly.",
            language="en",
            output_path=output_path,
            api_key=api_key
        )
        print(f"SUCCESS: Audio generated successfully at {output_path}")
        if output_path.exists():
            print(f"File size: {output_path.stat().st_size} bytes")
    except Exception as e:
        print(f"FAIL: ElevenLabs generation failed with error: {e}")

if __name__ == "__main__":
    test_elevenlabs()
