import asyncio
import logging
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from services import lip_sync_service as lip
import main

WAV2LIP_FACE_ERROR = (
    " 99%|#########9| 82/83 [11:58<00:09,  9.35s/it]\x1b[A\n"
    "Traceback (most recent call last):\n"
    '  File "E:\\Wav2Lip\\inference.py", line 92, in face_detect\n'
    "ValueError: Face not detected! Ensure the video contains a face in all the frames.\n"
)


@pytest.mark.parametrize("error, expected", [
    (WAV2LIP_FACE_ERROR, "no human face was detected"),
    ("Command '...' timed out after 1200 seconds", "timed out"),
    ("Runtime preflight failed: ImportError torch", "see backend logs"),
])
def test_friendly_reason_is_short_and_clean(error, expected):
    reason = lip.friendly_failure_reason(error)
    assert expected in reason
    assert "Traceback" not in reason and "\x1b" not in reason and "it/s" not in reason
    assert len(reason) < 160


def _configured_wav2lip(tmp_path, monkeypatch):
    (tmp_path / "inference.py").write_text("")
    (tmp_path / "model.pt").write_text("")
    monkeypatch.setenv("WAV2LIP_PATH", str(tmp_path))
    monkeypatch.setenv("WAV2LIP_CHECKPOINT", str(tmp_path / "model.pt"))


def test_failure_status_is_short_but_full_error_is_logged(tmp_path, monkeypatch, caplog):
    _configured_wav2lip(tmp_path, monkeypatch)
    status = {}
    failed = subprocess.CompletedProcess([], 1, "", WAV2LIP_FACE_ERROR)
    with patch.object(lip, "_inspect_video", return_value=(True, 720)), \
         patch.object(lip, "_runtime_env", return_value=os.environ.copy()), \
         patch.object(lip.subprocess, "run", return_value=failed), \
         caplog.at_level(logging.ERROR, logger=lip.__name__):
        assert lip.run_wav2lip("video", "audio", str(tmp_path / "out.mp4"), status) is None

    assert status["state"] == "failed"
    assert "Traceback" not in status["reason"] and "it/s" not in status["reason"]
    assert "no human face" in status["reason"]
    assert "Face not detected" in caplog.text and "Traceback" in caplog.text


def test_disabled_lip_sync_skips_wav2lip_immediately():
    with patch.object(main, "run_wav2lip") as wav2lip:
        status = asyncio.run(main._run_lip_sync_step(False, "video.mp4", "audio.wav"))
    wav2lip.assert_not_called()
    assert status == {
        "state": "skipped",
        "reason": "Lip-sync skipped because this video uses a cartoon or non-human character.",
    }


def test_enabled_lip_sync_still_runs_wav2lip():
    def fake_run(status, video_path, audio_path, output_path):
        status.update(state="completed", reason="ok")
        assert video_path == output_path == "video.mp4"
    with patch.object(main, "run_wav2lip", side_effect=fake_run) as wav2lip:
        status = asyncio.run(main._run_lip_sync_step(True, "video.mp4", "audio.wav"))
    wav2lip.assert_called_once()
    assert status["state"] == "completed"


def test_upload_and_rerender_default_to_lip_sync_enabled():
    from fastapi.testclient import TestClient
    client = TestClient(main.app)
    with patch.object(main, "process_video_job") as job:
        response = client.post("/upload?target_language=tanglish",
                               files={"file": ("lipsync_default_test.mp4", b"x", "video/mp4")})
    try:
        assert response.status_code == 200
        assert job.call_args.args[-1] is True
        with patch.object(main, "process_video_job") as job_off:
            client.post("/upload?target_language=tanglish&enable_lip_sync=false",
                        files={"file": ("lipsync_default_test.mp4", b"x", "video/mp4")})
        assert job_off.call_args.args[-1] is False
    finally:
        (main.UPLOAD_DIR / "lipsync_default_test.mp4").unlink(missing_ok=True)
    assert main.RerenderRequest(video_filename="v.mp4", target_language="tanglish", segments=[]).enable_lip_sync is True
