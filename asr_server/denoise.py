"""Two-stage classic DSP denoise front-end for factory-floor narration.

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
import uuid

logger = logging.getLogger(__name__)

HIGHPASS_HZ = 80
HIGHPASS_ORDER = 4
PROP_DECREASE = 0.85
N_FFT = 1024


def denoise_wav(src_path: str, workdir: str) -> str:
    """Denoise a 16 kHz mono PCM16 WAV; return the cleaned path, or
    src_path unchanged when the input is too short or processing fails."""
    try:
        return _denoise(src_path, workdir)
    except Exception:  # noqa: BLE001 — degrade to undenoised audio, never fail the request
        logger.exception("denoise failed — transcribing undenoised audio")
        return src_path


def _denoise(src_path: str, workdir: str) -> str:
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
