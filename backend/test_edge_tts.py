import asyncio
from pathlib import Path
import sys
import os

# Add the backend directory to sys.path so services can be imported correctly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.tts_service import _generate_with_edge

async def test_edge():
    print("Testing Edge TTS Alternative...")
    output_dir = Path("test_audio_output")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "test_edge_out.mp3"
    
    try:
        await _generate_with_edge(
            text="Hello from Edge TTS! This is a completely free and unlimited alternative to ElevenLabs. The fallback is working perfectly.", 
            language="en", 
            output_path=output_path
        )
        print(f"SUCCESS: Edge TTS Audio generated successfully at {output_path}")
        if output_path.exists():
            print(f"File size: {output_path.stat().st_size} bytes")
    except Exception as e:
        print(f"FAIL: Edge TTS generation failed with error: {e}")

if __name__ == "__main__":
    asyncio.run(test_edge())
