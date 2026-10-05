#!/usr/bin/env python3
"""Synthesize factory-floor noise and mix it into a clean speech clip at several levels.

  python benchmark/make_industrial_noise.py benchmark/speech_clean.mp3 --out benchmark

Writes industrial_noise.wav (the noise bed alone) and speech_noise_<level>.wav for each level.
Each layer imitates a source that is common on a shop floor and hard for ASR in a different way:
steady tonal hum (masks vowels), broadband ventilation rumble, rhythmic conveyor rattle,
and impulsive metal impacts and air bursts that blank out whole syllables.
"""

import argparse
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

SR = 16000
# name -> speech-to-noise ratio in dB (RMS over the whole clip); lower is harder
LEVELS = {"1_low": 20, "2_moderate": 10, "3_high": 5, "4_very_high": 0, "5_extreme": -5}


def load(path):
    raw = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
        check=True,
        capture_output=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.float32).astype(np.float64)


def bandpass(x, lo, hi):
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    spec[(f < lo) | (f > hi)] = 0
    return np.fft.irfft(spec, len(x))


def unit(x):
    return x / np.sqrt(np.mean(x**2))


def industrial_noise(n, rng):
    t = np.arange(n) / SR

    # Motor hum: 50 Hz mains-driven motor with harmonics and a slow speed wobble.
    wobble = 1 + 0.004 * np.sin(2 * np.pi * 0.3 * t)
    hum = sum(a * np.sin(2 * np.pi * 50 * k * wobble * t) for k, a in [(1, 1), (2, 0.7), (3, 0.5), (6, 0.25)])

    # Ventilation / compressor: brown-ish broadband rumble, strongest below 500 Hz.
    rumble = bandpass(np.cumsum(rng.standard_normal(n)), 20, 2000)
    rumble += 0.3 * bandpass(rng.standard_normal(n), 300, 4000)

    # Conveyor: band-limited rattle amplitude-modulated at ~5.5 Hz roller rhythm.
    rattle = bandpass(rng.standard_normal(n), 1500, 6000) * (0.5 + 0.5 * np.sin(2 * np.pi * 5.5 * t)) ** 4

    # Metal impacts: decaying inharmonic modes, every 0.8-3 s.
    impacts = np.zeros(n)
    pos = int(rng.uniform(0.3, 1.5) * SR)
    while pos < n:
        length = min(int(0.4 * SR), n - pos)
        tt = np.arange(length) / SR
        modes = sum(np.sin(2 * np.pi * f * tt) for f in rng.uniform(700, 4500, 4))
        impacts[pos : pos + length] += rng.uniform(2, 5) * modes * np.exp(-tt * rng.uniform(15, 40))
        pos += int(rng.uniform(0.8, 3.0) * SR)

    # Pneumatic air release: 0.3-0.8 s bursts of high-frequency hiss, every 4-9 s.
    air = np.zeros(n)
    hiss = bandpass(rng.standard_normal(n), 3000, 7900)
    pos = int(rng.uniform(1, 4) * SR)
    while pos < n:
        length = min(int(rng.uniform(0.3, 0.8) * SR), n - pos)
        air[pos : pos + length] = hiss[pos : pos + length] * np.hanning(length) * 3
        pos += int(rng.uniform(4, 9) * SR)

    # Relative weights set the character: hum and rumble dominate, the rest punch through.
    return unit(
        0.8 * unit(hum)
        + 1.0 * unit(rumble)
        + 0.35 * unit(rattle)
        + 0.5 * impacts / np.sqrt(np.mean(impacts**2) + 1e-12)
        + 0.3 * air / np.sqrt(np.mean(air**2) + 1e-12)
    )


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("speech")
    p.add_argument("--out", default=".")
    p.add_argument("--seed", type=int, default=7)
    a = p.parse_args()

    out = Path(a.out)
    speech = load(a.speech)
    noise = industrial_noise(len(speech), np.random.default_rng(a.seed))
    sf.write(out / "industrial_noise.wav", noise * 0.9 / np.max(np.abs(noise)), SR, subtype="PCM_16")

    rms = np.sqrt(np.mean(speech**2))
    for name, snr in LEVELS.items():
        m = speech + noise * rms / 10 ** (snr / 20)
        # Peak-normalize each file: impacts set the peak, and a shared gain left the 20 dB mix at -31 dBFS.
        sf.write(out / f"speech_noise_{name}.wav", m * 0.9 / np.max(np.abs(m)), SR, subtype="PCM_16")
        print(f"speech_noise_{name}.wav  SNR {LEVELS[name]:+d} dB")


if __name__ == "__main__":
    main()
