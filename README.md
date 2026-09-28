# AI Video Translation & Localization Platform
**Organisation:** The Apprentice Project
**Domain:** Education

## Overview
An AI-driven pipeline to automatically translate and localize educational videos into Indian languages, including Tanglish support.
Tanglish outputs are optimized for classroom-style romanized Tamil so SRT subtitles read more like a teacher speaking to students.

The backend text pipeline now runs in this order:
`STT -> original transcript JSON -> transcript cleanup -> translation -> translation review/repair -> translated JSON -> subtitle compression -> synced TTS -> final merge`

Each optional text stage is controlled by configuration. If cleanup, review, or compression fails, the pipeline falls back to the previous successful output instead of breaking the full dubbing flow.

## Getting Started
### Prerequisites
- Node.js (v18+)
- Python (v3.10+)
- FFmpeg installed and available on `PATH`

### Configuration
Create a `.env` file in the `backend/` directory.

Recommended for Anthropic Claude text processing:
```env
ANTHROPIC_API_KEY=your_anthropic_api_key_here
ANTHROPIC_MODEL=claude-sonnet-4-6
ANTHROPIC_MAX_TOKENS=2048
PRIMARY_LLM_PROVIDER=anthropic
FALLBACK_LLM_PROVIDER=anthropic
```

Optional for ElevenLabs TTS:
```env
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
ELEVENLABS_VOICE_ID=default
ELEVENLABS_DEFAULT_VOICE_ID=pGYsZruQzo8cpdFVZyJc
ELEVENLABS_TTS_MODEL_ID=eleven_v3
ELEVENLABS_TTS_SPEED=0.90
ELEVENLABS_TTS_STABILITY=0.75
ELEVENLABS_TTS_SIMILARITY_BOOST=0.64
ELEVENLABS_TTS_STYLE=0.0
ELEVENLABS_TTS_SPEAKER_BOOST=true
ELEVENLABS_STT_MODEL_ID=scribe_v1
ELEVENLABS_STT_LANGUAGE_CODE=
ELEVENLABS_STT_TAG_AUDIO_EVENTS=true
ELEVENLABS_STT_DIARIZE=true
```

The UI includes multiple ElevenLabs voice presets for final dubbed audio. You can also pass a raw ElevenLabs voice ID through `tts_voice_id`, or set `ELEVENLABS_VOICE_ID` in `backend/.env` for the backend default.

Text pipeline feature flags and settings:
```env
TRANSCRIPT_CLEANUP_ENABLED=true
TRANSLATION_REVIEW_ENABLED=true
SUBTITLE_COMPRESSION_ENABLED=true
TRANSLATION_MODE=student_friendly
PRIMARY_LLM_PROVIDER=anthropic
FALLBACK_LLM_PROVIDER=anthropic
MAX_SUBTITLE_CHARS=42
MAX_SUBTITLE_WORDS=12
LOG_LEVEL=INFO
```

Optional for OpenAI text processing:
```env
OPENAI_API_KEY=your_openai_api_key_here
PRIMARY_LLM_PROVIDER=openai
FALLBACK_LLM_PROVIDER=google
```

You can also use `PRIMARY_LLM_PROVIDER=claude`; it is treated as an alias for `anthropic`.

Glossary configuration supports JSON or `source=>target` entries:
```env
GLOSSARY_TERMS=[{"source":"ATP","target":"ATP"},{"source":"Newton's law","target":"Ley de Newton"}]
```

or:
```env
GLOSSARY_TERMS=ATP;Newton's law=>Ley de Newton;Photosynthesis
```

### Translation Modes
- `academic_exact`
- `student_friendly`
- `teacher_explanatory`
- `subtitle_compact`

### Indian Language + English Targets
The translator follows the `language-translator` skill workflow:
- Translate sentence by sentence into a natural Indian language + English classroom mix.
- Keep math, science, technical terms, variables, operators, proper nouns, brands, tools, and model names in English.
- Use spoken/colloquial grammar with local connector words, particles, and verb endings.
- Preserve source line breaks when present.
- Output only the translated text; no labels, headers, bullets, or preamble.

Supported target codes include `hi`, `ta`, `tanglish`, `te`, `kn`, `ml`, `bn`, `mr`, `gu`, `pa`, `or`, `as`, `ur`, `sa`, `gom`, `ks`, `mai`, `sat`, `doi`, `brx`, `mni-mtei`, and `sd`. Friendly aliases such as `hinglish`, `thanglish`, `tenglish`, `kanglish`, and `manglish` are normalized automatically.

### Glossary Protection
- Terms without a mapped translation stay unchanged.
- Terms with mapped translations are restored to the configured target value after text processing.
- Protection is applied consistently during cleanup, translation, review, and subtitle compression.
- Protection runs per segment to avoid unnecessary timestamp drift.

### Quick Start
1. Run the setup script:
   ```bat
   setup.bat
   ```
2. Launch the application:
   ```bat
   start_app.bat
   ```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000/docs

## Architecture
- Frontend: React, Vite, TailwindCSS
- Backend: FastAPI, Python
- STT: ElevenLabs Speech-to-Text when available, Whisper fallback
- Text processing: provider-agnostic pipeline with primary and fallback providers (`openai`, `anthropic`/`claude`, or `google`)
- TTS: ElevenLabs, Edge TTS, gTTS fallback
- Audio sync: pydub segment timing with speed/padding
- Final merge: FFmpeg replaces original video audio with synced dubbed audio

## Project Structure
```text
audio_change_project/
|-- frontend/
|-- backend/
|   |-- config.py
|   |-- services/
|   |   |-- text_pipeline_service.py
|   |   |-- translation_service.py
|   |   |-- tts_service.py
|   |   `-- audio_processor.py
|   |-- media/
|   `-- main.py
|-- implementation_plan.md
|-- setup.bat
`-- start_app.bat
```

## Fallback Behavior
- Cleanup failure falls back to raw STT segments.
- Translation failure falls back to the configured fallback provider when available.
- Translation review failure falls back to the translated text.
- Subtitle compression failure falls back to the reviewed translation.
- Subtitle file generation remains non-critical.

## Analysis Report
### Current Pipeline Status
- Upload video through the frontend at http://localhost:5173.
- Backend extracts the original audio with FFmpeg.
- STT creates same-language transcript segments with timestamps.
- The original transcript is saved as JSON in `backend/media/processed/`.
- Anthropic Claude processes cleanup, translation, review, and subtitle-ready text.
- The translated timeline is saved as JSON in `backend/media/processed/`.
- Subtitles are generated from the translated JSON-backed segments.
- ElevenLabs Eleven v3 generates segment audio.
- pydub fits each segment to its target timestamp using padding, trimming, and speed adjustment.
- Final synced audio is exported as WAV to avoid MP3 encoder padding before merge.
- FFmpeg removes the original video audio and adds the synced dubbed audio.

### Generated Files
For a video named `lesson.mp4`, the expected outputs are:
```text
backend/media/processed/lesson_original_transcript.json
backend/media/processed/lesson_ta_translated_transcript.json
backend/media/processed/lesson_ta.srt
backend/media/processed/lesson_ta.mp4
backend/media/audio/lesson_synced_ta.wav
```

The frontend result panel includes download buttons for:
- Final video
- SRT file
- Original JSON
- Translation JSON

### JSON Timeline Format
The translated JSON keeps timing and text together so the rest of the pipeline can be rerun without redoing STT:
```json
{
  "schema_version": 1,
  "type": "translated_transcript",
  "source_language": "en",
  "target_language": "ta",
  "segments": [
    {
      "id": 1,
      "start": 0.0,
      "end": 4.2,
      "original_text": "In this session we are going to discuss matrices.",
      "translated_text": "இந்த session-la matrices பற்றி discuss பண்ண போறோம்.",
      "subtitle_text": "இந்த session-la matrices பற்றி discuss பண்ண போறோம்.",
      "text": "இந்த session-la matrices பற்றி discuss பண்ண போறோம்."
    }
  ]
}
```

### Recent Fixes
- Removed the old watchdog/folder-monitor flow.
- Added the `language-translator` skill rules into the translation prompts.
- Switched the recommended text provider setup to Anthropic-only.
- Added ElevenLabs Eleven v3 support.
- Added runtime handling so invalid ElevenLabs settings fall back cleanly.
- Added original and translated JSON outputs.
- Updated the pipeline so subtitles and TTS read from the translated JSON timeline.
- Fixed audio sync by locking each segment to exact start/end timing.
- Fixed final merge so short dubbed audio is padded instead of cutting the video early.

### Verified Checks
- Backend responds at http://localhost:8000/docs.
- Frontend responds at http://localhost:5173.
- ElevenLabs key test passed with `voices_status=200`.
- ElevenLabs model test passed with `eleven_v3_available=True`.
- Small ElevenLabs TTS generation produced an audio file successfully.
- Backend compile check passed for the edited Python files.
- Frontend build and lint checks passed after JSON download UI changes.

### Known Notes
- Outputs generated before the JSON pipeline update will not automatically get JSON files. Reprocess the video to create the new JSON outputs.
- If old backend processes are still running, restart the backend so `.env` and latest code changes are loaded.
- Do not commit real API keys from `backend/.env` or `backend/dist/.env`.
