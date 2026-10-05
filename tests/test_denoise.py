import numpy as np
import pytest
from scipy.io import wavfile

pytest.importorskip("noisereduce")

from asr_server.denoise import denoise_wav

SR = 16000


def _write_wav(path, signal, sr=SR):
    wavfile.write(str(path), sr, (np.clip(signal, -1, 1) * 32767).astype(np.int16))


def _band_db(signal, sr, lo, hi):
    spectrum = np.abs(np.fft.rfft(signal))
    freqs = np.fft.rfftfreq(len(signal), 1 / sr)
    band = spectrum[(freqs >= lo) & (freqs <= hi)]
    return 20 * np.log10(float(np.sqrt(np.mean(band**2))) + 1e-12)


def _noisy_speech_like(seconds=2.0):
    rng = np.random.default_rng(42)
    t = np.arange(int(SR * seconds)) / SR
    tone = 0.3 * np.sin(2 * np.pi * 1000 * t)  # speech-band content
    hum = 0.5 * np.sin(2 * np.pi * 50 * t)  # machine rumble below the 80 Hz cut
    noise = 0.1 * rng.standard_normal(len(t))
    return tone + hum + noise


def test_denoise_kills_rumble_keeps_speech_band(tmp_path):
    src = tmp_path / "noisy.wav"
    _write_wav(src, _noisy_speech_like())
    out = denoise_wav(str(src), str(tmp_path))
    assert out != str(src)
    sr, data = wavfile.read(out)
    cleaned = data.astype(np.float32) / 32768.0
    original = _noisy_speech_like()
    hum_drop = _band_db(original, SR, 40, 60) - _band_db(cleaned, sr, 40, 60)
    tone_drop = _band_db(original, SR, 950, 1050) - _band_db(cleaned, sr, 950, 1050)
    # 4th-order Butterworth = 24 dB/oct; 50 Hz is 0.68 oct below the 80 Hz
    # cutoff -> ~16 dB theoretical attenuation (renormalization eats gating gains).
    assert hum_drop > 12, f"50 Hz hum only dropped {hum_drop:.1f} dB"
    assert tone_drop < 6, f"1 kHz speech-band tone lost {tone_drop:.1f} dB"
    assert hum_drop - tone_drop > 10, "rumble not suppressed relative to speech band"


def test_denoise_output_is_16k_mono_pcm16_normalized(tmp_path):
    src = tmp_path / "noisy.wav"
    _write_wav(src, _noisy_speech_like())
    out = denoise_wav(str(src), str(tmp_path))
    sr, data = wavfile.read(out)
    assert sr == SR
    assert data.dtype == np.int16
    assert data.ndim == 1
    peak = float(np.max(np.abs(data))) / 32767.0
    assert 0.9 < peak <= 1.0  # peak-normalized to ~0.97


def test_too_short_input_returns_src_unchanged(tmp_path):
    src = tmp_path / "short.wav"
    _write_wav(src, np.zeros(256))  # < n_fft, STFT framing would misbehave
    assert denoise_wav(str(src), str(tmp_path)) == str(src)


def test_silent_input_does_not_crash(tmp_path):
    src = tmp_path / "silent.wav"
    _write_wav(src, np.zeros(SR))
    out = denoise_wav(str(src), str(tmp_path))
    _, data = wavfile.read(out)  # valid wav either way, no div-by-zero
    # The spectral gate yields NaN (0/0) on an all-zero signal; NaN -> int16 is
    # undefined, so the output must be explicitly zeroed, not platform luck.
    assert np.all(data == 0)


def test_unreadable_input_returns_src(tmp_path):
    src = tmp_path / "corrupt.wav"
    src.write_bytes(b"not a wav at all")
    assert denoise_wav(str(src), str(tmp_path)) == str(src)
