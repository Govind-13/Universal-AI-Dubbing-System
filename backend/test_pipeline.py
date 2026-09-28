
import requests
import os
import time

def test_pipeline():
    url = "http://localhost:8000/upload"
    video_file = "test_with_audio.mp4"
    
    if not os.path.exists(video_file):
        print(f"Error: {video_file} not found. Run create_test_video.py first.")
        return

    print(f"Uploading {video_file}...")
    with open(video_file, 'rb') as f:
        files = {'file': (video_file, f, 'video/mp4')}
        try:
            response = requests.post(url, files=files)
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print("\n[SUCCESS] Pipeline Complete!")
                
                if "transcription" in data:
                    print(f"Original Text: {data['transcription']['text'][:50]}...")
                
                if "translation" in data:
                    print(f"Translation ({data['translation']['target_language']}): found {len(data['translation']['segments'])} segments.")
                    try:
                        # printing safe for windows console
                        print(f"Sample: {data['translation']['segments'][0]['text'].encode('utf-8', 'replace').decode('utf-8')}") 
                    except:
                        pass
                    
                # Use the fields that are actually returned by the API
                print(f"[INFO] Processed video URL: {data.get('video_url')}")
                print(f"[INFO] Original video URL: {data.get('original_video_url')}")
                if data.get('subtitle_url'):
                    print(f"[SUCCESS] Subtitles generated at: {data['subtitle_url']}")
                else:
                    print("[WARNING] Subtitles missing.")

            else:
                print("\n[FAILED] Failed.")
                print(response.text)
                
        except Exception as e:
            print(f"Request failed: {e}")

def test_tanglish():
    print("\n--- Testing Tanglish Support ---")
    url = "http://localhost:8000/upload"
    video_file = "test_with_audio.mp4"
    if not os.path.exists(video_file): return

    with open(video_file, 'rb') as f:
        files = {'file': (video_file, f, 'video/mp4')}
        try:
            response = requests.post(url, files=files, params={"target_language": "tanglish"})
            data = response.json()
            if response.status_code == 200:
                print("[SUCCESS] Tanglish Request worked.")
                if "translation" in data and len(data["translation"]["segments"]) > 0:
                     try:
                        print(f"Sample Translation: {data['translation']['segments'][0]['text'].encode('utf-8', 'replace').decode('utf-8')}")
                     except:
                        pass
            else:
                 print(f"[FAILED] Tanglish request failed: {response.status_code}")
                 print(response.text)
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    test_pipeline()
    test_tanglish()
