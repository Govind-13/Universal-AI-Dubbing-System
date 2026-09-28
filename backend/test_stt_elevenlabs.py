import os
import requests
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

def test_stt():
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("No API Key")
        return
        
    url = "https://api.elevenlabs.io/v1/speech-to-text"
    headers = {
        "xi-api-key": api_key,
    }
    
    data = {
        "model_id": "scribe_v1",
        "tag_audio_events": "true",
        "diarize": "false"
    }

    # we need an audio file. I see test_silent.mp3 or we can use test_edge_out.mp3
    audio_path = "test_audio_output/test_edge_out.mp3"
    if not os.path.exists(audio_path):
        print(f"File not found: {audio_path}")
        return
        
    print("Calling Elevenlabs STT...")
    with open(audio_path, "rb") as f:
        files = {
            "file": ("test_edge_out.mp3", f, "audio/mpeg")
        }
        res = requests.post(url, headers=headers, data=data, files=files)
        
    if res.status_code == 200:
        print("Success")
        # save the json output to look at it
        with open("test_elevenlabs_stt_response.json", "w") as out:
            json.dump(res.json(), out, indent=2)
        print("Saved to test_elevenlabs_stt_response.json")
    else:
        print(f"Error {res.status_code}: {res.text}")

if __name__ == "__main__":
    test_stt()
