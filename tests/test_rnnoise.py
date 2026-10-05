import os
import shutil
import subprocess
import wave

import pytest

from asr_server.denoise import denoise_wav

requires_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
# The model is baked into the image, not the repo; point RNNOISE_MODEL_PATH at a
# local std.rnnn to run the real-filter test outside Docker.
MODEL = os.getenv("RNNOISE_MODEL_PATH", "/usr/local/share/rnnoise/std.rnnn")
requires_model = pytest.mark.skipif(not os.path.isfile(MODEL), reason="RNNoise model not available")


@pytest.fixture()
def noisy_wav(tmp_path):
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not installed")
    src = str(tmp_path / "in.wav")
    noise = ["-f", "lavfi", "-i", "anoisesrc=c=pink:d=2:a=0.1", "-filter_complex", "amix=inputs=2"]
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i", "sine=f=440:d=2", *noise]
    subprocess.run([*cmd, "-ac", "1", "-ar", "16000", src], check=True)
    return src


def test_missing_model_returns_src(tmp_path):
    src = str(tmp_path / "in.wav")
    assert denoise_wav(src, str(tmp_path), "rnnoise", str(tmp_path / "absent.rnnn")) == src


def test_quote_in_model_path_is_rejected(tmp_path):
    model = tmp_path / "it's.rnnn"
    model.write_bytes(b"x")
    src = str(tmp_path / "in.wav")
    assert denoise_wav(src, str(tmp_path), "rnnoise", str(model)) == src


@requires_ffmpeg
def test_invalid_model_degrades_to_src(noisy_wav, tmp_path):
    bad = tmp_path / "bad.rnnn"
    bad.write_bytes(b"not a model")
    assert denoise_wav(noisy_wav, str(tmp_path), "rnnoise", str(bad)) == noisy_wav


@requires_ffmpeg
@requires_model
def test_rnnoise_output_is_16k_mono_pcm16(noisy_wav, tmp_path):
    out = denoise_wav(noisy_wav, str(tmp_path), "rnnoise", MODEL)
    assert out != noisy_wav
    with wave.open(out) as w, wave.open(noisy_wav) as orig:
        assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (16000, 1, 2)
        assert abs(w.getnframes() - orig.getnframes()) < 160  # same length within 10 ms
