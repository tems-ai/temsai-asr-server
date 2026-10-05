import shutil
import subprocess
from unittest import mock

import pytest

from asr_server.audio import AudioDecodeError, decode_to_wav_16k_mono

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def _make_clip(path, seconds=2):
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:duration={seconds}",
            "-ar",
            "44100",
            "-ac",
            "2",
            path,
        ],
        check=True,
        capture_output=True,
    )


def test_decodes_to_16k_mono_and_reports_duration(tmp_path):
    src = str(tmp_path / "in.wav")
    _make_clip(src)
    wav, duration = decode_to_wav_16k_mono(src, str(tmp_path))
    assert wav.endswith(".wav")
    assert 1.8 <= duration <= 2.2
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=sample_rate,channels", "-of", "csv=p=0", wav],
        check=True,
        capture_output=True,
        text=True,
    )
    assert probe.stdout.strip() == "16000,1"


def test_garbage_input_raises(tmp_path):
    src = tmp_path / "bad.mp4"
    src.write_bytes(b"not audio at all")
    with pytest.raises(AudioDecodeError):
        decode_to_wav_16k_mono(str(src), str(tmp_path))


def test_malformed_ffprobe_output_raises(tmp_path):
    """Test that missing format.duration in ffprobe output raises AudioDecodeError."""
    src = str(tmp_path / "in.wav")
    _make_clip(src)

    # Mock subprocess.run to return success for ffmpeg but malformed output for ffprobe
    call_count = [0]
    original_run = subprocess.run

    def mock_run(*args, **kwargs):
        call_count[0] += 1
        # First call is ffmpeg (should succeed normally)
        if call_count[0] == 1:
            return original_run(*args, **kwargs)
        # Second call is ffprobe (return malformed output)
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout=b'{"format": {}}',  # Missing duration key
            stderr=b"",
        )

    with mock.patch("asr_server.audio.subprocess.run", side_effect=mock_run):
        with pytest.raises(AudioDecodeError, match="could not determine audio duration"):
            decode_to_wav_16k_mono(src, str(tmp_path))
