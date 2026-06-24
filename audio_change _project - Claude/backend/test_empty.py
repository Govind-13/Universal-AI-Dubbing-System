import asyncio
from services.tts_service import generate_synced_audio

async def test():
    # TEST EMPTY SEGMENTS
    print("Testing empty segments")
    try:
        await generate_synced_audio([], "hi", "test_audio_output", "empty")
        print("Done empty")
    except Exception as e:
        print("Error empty:", e)

if __name__ == "__main__":
    asyncio.run(test())
