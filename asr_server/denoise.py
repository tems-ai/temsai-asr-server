"""Optional denoise front-end for factory-floor narration (DENOISE_ENABLED,
off by default). DENOISE_METHOD picks one of two.

Why off: on benchmark/ (a 214-word passage, TTS and a real recording, mixed
with pink, machine and industrial noise from 20 to -5 dB SNR) Parakeet v3 with
NO denoise averaged 2.7% WER across 13 conditions; spectral 3.3%, RNNoise
2.8-4.0%. Parakeet is trained on noisy speech, and enhancer artifacts cost it
more than the noise does. Turn it on only where it measurably helps your audio.

rnnoise: RNNoise via FFmpeg's built-in arnndn filter (no extra library, just a
.rnnn model file). Full strength HURT (std model 4.0%, pink 0 dB 7.9%->15.0%);
mix=0.5 blends half the original back in and cut that loss to 2.95% (pink
5 dB 2.8%->1.9%, but pink 0 dB still 12.1%). The "sh" model from
GregorR/rnnoise-models scored 2.8% at mix=0.5, but ships without a clear
license, so the BSD-3 Xiph "std" model is the default.

spectral: classic DSP, the three stages below.

Stage 1: 4th-order Butterworth high-pass at 80 Hz (SOS form — numerically
stable at steep orders). Machine noise (motor hum, conveyor rumble, HVAC)
concentrates below 80 Hz; speech fundamentals start ~85 Hz and the
intelligibility-carrying formants live 300 Hz-3.4 kHz.

Stage 2: non-stationary spectral gating (noisereduce) — per-bin noise floor
estimated over a sliding window so the profile adapts as machines cycle
on/off. prop_decrease swept 0.6-0.85 against a ground-truth factory clip:
0.85 cut Parakeet WER 48%->32% while 0.6 only reached 44%; clean speech was
unaffected. Deep enhancers (DeepFilterNet3) were tested and HURT
transcription — perceptual cleanliness is not ASR accuracy.

Stage 3: peak-normalize to 0.97 so the model sees a healthy level.

Failure policy: best-effort — any error returns the original path
(degrade, never 500), same contract as confidence.py.
"""

import logging
import os
import subprocess
import uuid

logger = logging.getLogger(__name__)

HIGHPASS_HZ = 80
HIGHPASS_ORDER = 4
PROP_DECREASE = 0.85
N_FFT = 1024
RNNOISE_MIX = 0.5  # share of denoised signal; 1.0 (full) measured worse, see above


def denoise_wav(src_path: str, workdir: str, method: str = "spectral", rnnoise_model: str = "") -> str:
    """Denoise a 16 kHz mono PCM16 WAV; return the cleaned path, or
    src_path unchanged when the input is too short or processing fails."""
    try:
        if method == "rnnoise":
            return _rnnoise(src_path, workdir, rnnoise_model)
        return _spectral(src_path, workdir)
    except Exception:  # noqa: BLE001 — degrade to undenoised audio, never fail the request
        logger.exception("denoise (%s) failed — transcribing undenoised audio", method)
        return src_path


def _rnnoise(src_path: str, workdir: str, model_path: str) -> str:
    if not os.path.isfile(model_path):
        raise FileNotFoundError(f"RNNoise model not found: {model_path!r} (set RNNOISE_MODEL_PATH)")
    if "'" in model_path:
        raise ValueError("RNNoise model path must not contain a single quote")
    out = os.path.join(workdir, f"{uuid.uuid4().hex}_denoised.wav")
    # arnndn runs at 48 kHz; FFmpeg resamples in and back out to 16 kHz. The
    # quotes keep ':' in the path from being read as an option separator.
    filtergraph = f"arnndn=m='{model_path}':mix={RNNOISE_MIX}"
    proc = subprocess.run(
        ["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", src_path, "-af", filtergraph]
        + ["-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", out],
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg arnndn rc={proc.returncode}: {proc.stderr[-500:].decode(errors='replace')}")
    return out


def _spectral(src_path: str, workdir: str) -> str:
    import noisereduce as nr
    import numpy as np
    from scipy.io import wavfile
    from scipy.signal import butter, sosfilt

    sr, data = wavfile.read(src_path)
    signal = data.astype(np.float32) / 32768.0  # decode_to_wav_16k_mono emits PCM16 mono
    if len(signal) < N_FFT:
        logger.info("audio shorter than one STFT frame (%d samples) — skipping denoise", len(signal))
        return src_path

    sos = butter(HIGHPASS_ORDER, HIGHPASS_HZ, btype="highpass", fs=sr, output="sos")
    filtered = sosfilt(sos, signal)

    reduced = nr.reduce_noise(y=filtered, sr=sr, stationary=False, prop_decrease=PROP_DECREASE, n_fft=N_FFT)
    # An all-zero (digitally silent) input makes the spectral gate divide 0/0;
    # NaN -> int16 is undefined behaviour, so pin those samples to zero.
    reduced = np.nan_to_num(reduced, nan=0.0, posinf=0.0, neginf=0.0)

    peak = float(np.max(np.abs(reduced)))
    if peak > 0:
        reduced = reduced / peak * 0.97

    out = os.path.join(workdir, f"{uuid.uuid4().hex}_denoised.wav")
    wavfile.write(out, sr, (np.clip(reduced, -1.0, 1.0) * 32767.0).astype(np.int16))
    return out
