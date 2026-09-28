import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from pydub import AudioSegment
from pydub.generators import Sine

from services.audio_mixing_service import mix_narration_with_bgm, _merge_windows


def _tone(duration_ms, freq=440, gain_db=-6.0):
    return Sine(freq).to_audio_segment(duration=duration_ms).apply_gain(gain_db)


class MergeWindowsTests(unittest.TestCase):
    def test_merges_overlapping_and_adjacent(self):
        self.assertEqual(_merge_windows([(0, 100), (50, 150), (150, 200)]), [(0, 200)])

    def test_keeps_disjoint_separate(self):
        self.assertEqual(_merge_windows([(0, 100), (500, 600)]), [(0, 100), (500, 600)])

    def test_drops_zero_or_negative_windows(self):
        self.assertEqual(_merge_windows([(100, 100), (200, 150)]), [])

    def test_empty_input(self):
        self.assertEqual(_merge_windows([]), [])


class MixNarrationWithBgmTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = BACKEND_DIR / "_test_tmp_audio_mixing"
        self.tmp_dir.mkdir(exist_ok=True)

    def tearDown(self):
        for f in self.tmp_dir.glob("*"):
            f.unlink()
        self.tmp_dir.rmdir()

    def _write(self, name, segment):
        path = self.tmp_dir / name
        segment.export(str(path), format="wav")
        return str(path)

    def test_output_duration_matches_narration_when_bgm_shorter(self):
        bgm = _tone(2000)
        narration = _tone(5000, freq=880)
        bgm_path = self._write("bgm.wav", bgm)
        tts_path = self._write("tts.wav", narration)
        out_path = str(self.tmp_dir / "out.wav")

        mix_narration_with_bgm(bgm_path, tts_path, [{"start": 0.0, "end": 5.0}], out_path)

        mixed = AudioSegment.from_file(out_path)
        self.assertAlmostEqual(len(mixed), len(narration), delta=5)

    def test_output_duration_matches_narration_when_bgm_longer(self):
        bgm = _tone(8000)
        narration = _tone(3000, freq=880)
        bgm_path = self._write("bgm.wav", bgm)
        tts_path = self._write("tts.wav", narration)
        out_path = str(self.tmp_dir / "out.wav")

        mix_narration_with_bgm(bgm_path, tts_path, [{"start": 0.0, "end": 3.0}], out_path)

        mixed = AudioSegment.from_file(out_path)
        self.assertAlmostEqual(len(mixed), len(narration), delta=5)

    def test_bgm_ducked_during_narration_window(self):
        bgm = _tone(4000, gain_db=-6.0)
        narration = AudioSegment.silent(duration=4000)  # isolate BGM level, no overlay masking
        bgm_path = self._write("bgm.wav", bgm)
        tts_path = self._write("tts.wav", narration)
        out_path = str(self.tmp_dir / "out.wav")

        mix_narration_with_bgm(
            bgm_path, tts_path, [{"start": 1.0, "end": 3.0}], out_path, duck_db=-20.0, fade_ms=100
        )

        mixed = AudioSegment.from_file(out_path)
        ducked_slice = mixed[1500:2500]
        normal_slice = mixed[3500:4000]
        self.assertLess(ducked_slice.dBFS, normal_slice.dBFS - 10)

    def test_bgm_returns_to_original_level_outside_narration(self):
        bgm = _tone(4000, gain_db=-6.0)
        narration = AudioSegment.silent(duration=4000)
        bgm_path = self._write("bgm.wav", bgm)
        tts_path = self._write("tts.wav", narration)
        out_path = str(self.tmp_dir / "out.wav")

        mix_narration_with_bgm(
            bgm_path, tts_path, [{"start": 1.0, "end": 2.0}], out_path, duck_db=-20.0, fade_ms=100
        )

        mixed = AudioSegment.from_file(out_path)
        before = mixed[0:800]
        after = mixed[2500:4000]
        self.assertAlmostEqual(before.dBFS, after.dBFS, delta=1.0)

    def test_narration_audible_in_mixed_output(self):
        bgm = _tone(3000, gain_db=-40.0)
        narration = _tone(3000, freq=880, gain_db=-6.0)
        bgm_path = self._write("bgm.wav", bgm)
        tts_path = self._write("tts.wav", narration)
        out_path = str(self.tmp_dir / "out.wav")

        mix_narration_with_bgm(bgm_path, tts_path, [{"start": 0.0, "end": 3.0}], out_path)

        mixed = AudioSegment.from_file(out_path)
        self.assertGreater(mixed.dBFS, -30.0)

    def test_no_narration_windows_leaves_bgm_untouched(self):
        bgm = _tone(3000, gain_db=-6.0)
        narration = AudioSegment.silent(duration=3000)
        bgm_path = self._write("bgm.wav", bgm)
        tts_path = self._write("tts.wav", narration)
        out_path = str(self.tmp_dir / "out.wav")

        mix_narration_with_bgm(bgm_path, tts_path, [], out_path)

        mixed = AudioSegment.from_file(out_path)
        self.assertAlmostEqual(mixed.dBFS, bgm.dBFS, delta=1.0)


if __name__ == "__main__":
    unittest.main()
