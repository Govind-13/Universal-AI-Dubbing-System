from pathlib import Path
import sys

from pydub import AudioSegment

sys.path.insert(0, str(Path(__file__).resolve().parent))

from services.tts_service import _fit_audio_to_duration, is_tts_speakable_text


def test_fit_audio_to_duration_pads_short_audio():
    audio = AudioSegment.silent(duration=400)

    fitted = _fit_audio_to_duration(audio, 1000)

    assert len(fitted) == 1000


def test_fit_audio_to_duration_trims_or_speeds_long_audio():
    audio = AudioSegment.silent(duration=1800)

    fitted = _fit_audio_to_duration(audio, 900)

    assert len(fitted) == 900


def test_fit_audio_to_duration_handles_empty_audio():
    audio = AudioSegment.empty()

    fitted = _fit_audio_to_duration(audio, 650)

    assert len(fitted) == 650


def test_tts_placeholder_text_is_not_speakable():
    assert not is_tts_speakable_text("")
    assert not is_tts_speakable_text("(empty)")
    assert not is_tts_speakable_text("(empty source — nothing to translate)")
    assert not is_tts_speakable_text("(empty input â€” nothing to translate)")
    assert is_tts_speakable_text("Euler's theorem")
