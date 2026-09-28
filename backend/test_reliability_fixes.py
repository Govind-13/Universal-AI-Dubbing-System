import asyncio
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest
from pydub import AudioSegment
from pydub.generators import Sine

sys.path.insert(0, str(Path(__file__).parent))
from services import tts_service as tts
from services import lip_sync_service as lip
from services.translation_service import AnthropicTextProcessingProvider, OpenAITextProcessingProvider
from services.text_pipeline_service import TextPipelineService
from config import TextPipelineConfig
from test_text_pipeline import FakeProvider
from services.audio_processor import merge_audio_video, _probe_media_duration


def test_decode_without_ffprobe(tmp_path):
    path = tmp_path / 'tone.mp3'
    subprocess.run([tts.imageio_ffmpeg.get_ffmpeg_exe(), '-loglevel', 'error', '-f', 'lavfi', '-i',
                    'sine=frequency=440:duration=0.2', '-y', str(path)], check=True)
    with patch('pydub.audio_segment.mediainfo_json', side_effect=PermissionError('ffprobe blocked')):
        audio = tts._load_audio_segment(path)
    assert 190 <= len(audio) <= 220
    assert audio.rms > 0


def test_all_providers_fail_raises(tmp_path, monkeypatch):
    monkeypatch.delenv('ELEVENLABS_API_KEY', raising=False)
    with patch.object(tts, '_generate_with_edge', AsyncMock(side_effect=RuntimeError('offline'))), patch.object(tts, 'gTTS', None):
        with pytest.raises(RuntimeError, match='All TTS providers failed'):
            asyncio.run(tts.generate_tts_async('hello', 'en', str(tmp_path), 'test'))


@pytest.mark.parametrize('audio', [AudioSegment.empty(), AudioSegment.silent(duration=500)])
def test_silent_speech_rejected(audio):
    with pytest.raises(RuntimeError, match='empty or silent'):
        tts._require_speech(audio, 'test')


def test_decode_failure_fails_render_and_cleans_temp(tmp_path):
    with patch.object(tts, 'generate_tts_with_alignment_async', AsyncMock(return_value=('missing.mp3', None))):
        with pytest.raises(RuntimeError, match='segment 1'):
            asyncio.run(tts.generate_synced_audio([{'start':0,'end':1,'text':'hello'}], 'en', str(tmp_path), 'test'))
    assert not list(tmp_path.glob('speech_*'))
    assert not list(tmp_path.glob('*.wav'))


def test_small_overflow_is_accounted_for(tmp_path):
    with patch.object(tts, 'generate_tts_with_alignment_async', AsyncMock(return_value=('unused', None))), patch.object(tts, '_load_audio_segment', return_value=Sine(440).to_audio_segment(duration=1020)):
        _, segments, freezes = asyncio.run(tts.generate_synced_audio([{'start':0,'end':1,'text':'hello'}], 'en', str(tmp_path), 'test'))
    assert freezes[0]['duration_sec'] == .02
    assert segments[0]['end'] == 1.02


@pytest.mark.parametrize('provider_class', [AnthropicTextProcessingProvider, OpenAITextProcessingProvider])
def test_review_prompt_contains_source(provider_class):
    provider = object.__new__(provider_class)
    provider._complete = AsyncMock(return_value='repaired')
    asyncio.run(provider.review_translation('What formula finds the equation?', 'wrong', 'ta', 'student_friendly', []))
    system, user = provider._complete.call_args.args
    assert 'What formula finds the equation?' in user
    assert 'wrong' in user
    assert 'subject/object' in system


def test_review_double_failure_retains_candidate():
    primary = FakeProvider(review_behavior=lambda *args: RuntimeError('primary unavailable'))
    fallback = FakeProvider(review_behavior=lambda *args: RuntimeError('fallback unavailable'))
    config = TextPipelineConfig(transcript_cleanup_enabled=False, subtitle_compression_enabled=False)
    service = TextPipelineService(config, primary, fallback)
    result = asyncio.run(service.process_segments([{'start':0,'end':1,'text':'source'}], 'en'))
    assert result['reviewed_segments'][0]['text'] == result['translated_segments'][0]['text']
    assert result['stage_status']['translation_review_fallback_used']


def test_lipsync_missing_config_explicit(monkeypatch):
    monkeypatch.delenv('WAV2LIP_PATH', raising=False)
    status={}
    assert lip.run_wav2lip('video','audio','output',status) is None
    assert status['state'] == 'not_configured'


def test_lipsync_failure_does_not_replace_existing_output(tmp_path, monkeypatch):
    (tmp_path/'inference.py').write_text('')
    (tmp_path/'model.pt').write_text('')
    monkeypatch.setenv('WAV2LIP_PATH',str(tmp_path))
    monkeypatch.setenv('WAV2LIP_CHECKPOINT',str(tmp_path/'model.pt'))
    output=tmp_path/'existing.mp4';output.write_bytes(b'previous')
    status={}
    with patch.object(lip,'_inspect_video',return_value=(True,720)), patch.object(lip,'_runtime_env',return_value=os.environ.copy()), patch.object(lip.subprocess,'run',return_value=subprocess.CompletedProcess([],1,'','runtime failure')):
        assert lip.run_wav2lip('video','audio',str(output),status) is None
    assert status['state']=='failed'
    assert output.read_bytes()==b'previous'


def test_invalid_duration_fails_before_speech(tmp_path):
    with patch.object(tts, 'generate_tts_with_alignment_async', AsyncMock()) as generate:
        with pytest.raises(ValueError, match='positive duration'):
            asyncio.run(tts.generate_synced_audio([{'start':1,'end':0,'text':'hello'}], 'en', str(tmp_path), 'test'))
        generate.assert_not_called()


def test_freeze_merge_preserves_trailing_silent_video(tmp_path):
    ffmpeg=tts.imageio_ffmpeg.get_ffmpeg_exe()
    video=tmp_path/'source.mp4'; audio=tmp_path/'speech.wav'; output=tmp_path/'output.mp4'
    subprocess.run([ffmpeg,'-loglevel','error','-f','lavfi','-i','color=c=blue:s=160x120:r=25:d=2',
                    '-c:v','libx264','-y',str(video)],check=True)
    Sine(440).to_audio_segment(duration=1000).export(audio,format='wav')
    merge_audio_video(str(video),str(audio),str(output),[{'video_time_sec':.5,'duration_sec':.4}])
    assert abs(_probe_media_duration(output,ffmpeg)-2.4)<.06
