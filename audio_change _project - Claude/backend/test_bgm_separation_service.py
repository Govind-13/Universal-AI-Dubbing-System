import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.bgm_separation_service import separate_vocals_and_bgm


class SeparateVocalsAndBgmTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = BACKEND_DIR / "_test_tmp_bgm_sep"
        self.tmp_dir.mkdir(exist_ok=True)
        self.audio_path = self.tmp_dir / "lecture.mp3"
        self.audio_path.write_bytes(b"fake-audio")

    def tearDown(self):
        for f in self.tmp_dir.rglob("*"):
            if f.is_file():
                f.unlink()
        for d in sorted(self.tmp_dir.rglob("*"), reverse=True):
            if d.is_dir():
                d.rmdir()
        self.tmp_dir.rmdir()

    def _expected_no_vocals_path(self, output_dir: Path) -> Path:
        return output_dir / "bgm_separation" / "htdemucs" / "lecture" / "no_vocals.wav"

    def test_returns_no_vocals_path_on_success(self):
        expected = self._expected_no_vocals_path(self.tmp_dir)
        expected.parent.mkdir(parents=True, exist_ok=True)
        expected.write_bytes(b"fake-wav")

        with patch("services.bgm_separation_service.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            result = separate_vocals_and_bgm(str(self.audio_path), str(self.tmp_dir))

        self.assertEqual(result, str(expected))
        args = mock_run.call_args[0][0]
        self.assertIn("demucs", args)
        self.assertIn("--two-stems", args)
        self.assertIn(str(self.audio_path.resolve()), args)

    def test_returns_none_on_nonzero_returncode(self):
        with patch("services.bgm_separation_service.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="boom")
            result = separate_vocals_and_bgm(str(self.audio_path), str(self.tmp_dir))
        self.assertIsNone(result)

    def test_returns_none_when_output_file_missing(self):
        with patch("services.bgm_separation_service.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            result = separate_vocals_and_bgm(str(self.audio_path), str(self.tmp_dir))
        self.assertIsNone(result)

    def test_returns_none_on_timeout(self):
        with patch("services.bgm_separation_service.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="demucs", timeout=1800)
            result = separate_vocals_and_bgm(str(self.audio_path), str(self.tmp_dir))
        self.assertIsNone(result)

    def test_returns_none_when_demucs_not_installed(self):
        with patch("services.bgm_separation_service.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("no demucs")
            result = separate_vocals_and_bgm(str(self.audio_path), str(self.tmp_dir))
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
