import asyncio
from services.tts_service import generate_synced_audio
import os

async def test():
    segments = [{"start": 0, "end": 2, "text": "Hello world"}]
    print("Testing generate_synced_audio")
    res = await generate_synced_audio(segments, "hi", "test_audio_output", "test_vid")
    print("Result:", res)

if __name__ == "__main__":
    asyncio.run(test())
