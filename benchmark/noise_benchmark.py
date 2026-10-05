#!/usr/bin/env python3
"""Compare ASR engines on one recording at several noise levels (word error rate).

Every engine is reached through the OpenAI /v1/audio/transcriptions API, so the same
code measures temsai-asr-server, a local Whisper server (e.g. speaches) or OpenAI's
hosted whisper-1. A local openai-whisper model can be added with --whisper-local.

  pip install jiwer numpy soundfile openai          # + openai-whisper for --whisper-local
  python noise_benchmark.py --audio talk.wav --reference talk.txt \
      --engine parakeet=http://localhost:8000/v1 \
      --engine parakeet-denoise=http://localhost:8001/v1 \
      --whisper-local large-v3 \
      --noise pink --noise factory.wav --snr clean 20 10 5 0

The noisy mixes are written to --out so you can listen to them.
"""

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import jiwer
import numpy as np
import soundfile as sf

SR = 16000


def load(path):
    """Decode anything ffmpeg reads to 16 kHz mono float32."""
    raw = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
        check=True,
        capture_output=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def colored_noise(kind, n, rng):
    """White, pink (1/f) or brown (1/f^2) noise, unit RMS."""
    white = rng.standard_normal(n)
    if kind == "white":
        x = white
    else:
        spec = np.fft.rfft(white)
        f = np.fft.rfftfreq(n)
        f[0] = f[1]
        spec /= np.sqrt(f) if kind == "pink" else f
        x = np.fft.irfft(spec, n)
    return x / np.sqrt(np.mean(x**2))


def noise_signal(spec, n, rng):
    if spec in ("white", "pink", "brown"):
        return colored_noise(spec, n, rng)
    x = load(spec)
    x = np.tile(x, int(np.ceil(n / len(x))))[:n]  # loop a short recording over the whole clip
    return x / np.sqrt(np.mean(x**2))


def mix(speech, noise, snr_db):
    """Scale noise so that RMS(speech)/RMS(noise) == snr_db, then peak-normalize if it clips."""
    rms = np.sqrt(np.mean(speech**2))
    out = speech + noise * rms / (10 ** (snr_db / 20))
    peak = np.max(np.abs(out))
    return out / peak * 0.99 if peak > 0.99 else out


def normalize(text):
    """Lowercase, drop punctuation and fillers, so WER counts words, not formatting."""
    text = text.lower().replace("-", " ")
    text = re.sub(r"[^\w\s']", " ", text)
    text = re.sub(r"\b(uh|um|hmm|mm|ah|er)\b", " ", text)
    return " ".join(text.split())


def api_engine(base_url, model, api_key):
    from openai import OpenAI

    client = OpenAI(base_url=base_url, api_key=api_key or "unused", timeout=3600)

    def run(path, language):
        with open(path, "rb") as f:
            kwargs = {"language": language} if language else {}
            return client.audio.transcriptions.create(model=model, file=f, response_format="text", **kwargs)

    return run


def whisper_engine(size):
    import whisper

    model = whisper.load_model(size)

    def run(path, language):
        return model.transcribe(str(path), language=language, fp16=False)["text"]

    return run


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--audio", required=True, help="speech recording (any format ffmpeg reads)")
    p.add_argument("--reference", required=True, help="text file with the exact transcript")
    p.add_argument("--engine", action="append", default=[], metavar="NAME=BASE_URL[,MODEL[,API_KEY]]")
    p.add_argument("--whisper-local", action="append", default=[], metavar="SIZE", help="e.g. large-v3, medium")
    p.add_argument("--noise", action="append", default=[], help="white|pink|brown or a noise recording")
    p.add_argument("--snr", nargs="+", default=["clean", "20", "10", "5", "0"], help="dB values, or 'clean'")
    p.add_argument("--language", default="en")
    p.add_argument("--out", default="benchmark_out")
    p.add_argument("--seed", type=int, default=0)
    a = p.parse_args()

    engines = {}
    for spec in a.engine:
        name, _, rest = spec.partition("=")
        url, model, key = (rest.split(",") + ["whisper-1", ""])[:3]
        engines[name] = api_engine(url, model, key)
    for size in a.whisper_local:
        engines[f"whisper-{size}"] = whisper_engine(size)
    if not engines:
        p.error("add at least one --engine or --whisper-local")

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    speech = load(a.audio)
    reference = normalize(Path(a.reference).read_text())
    rng = np.random.default_rng(a.seed)

    conditions = []  # (label, wav path)
    for noise in a.noise or ["pink"]:
        noise_x = noise_signal(noise, len(speech), rng)
        tag = Path(noise).stem
        for snr in a.snr:
            if snr == "clean":
                if not any(c[0] == "clean" for c in conditions):
                    path = out / "clean.wav"
                    sf.write(path, speech, SR)
                    conditions.append(("clean", path))
                continue
            path = out / f"{tag}_snr{snr}.wav"
            sf.write(path, mix(speech, noise_x, float(snr)), SR)
            conditions.append((f"{tag} {snr} dB", path))

    duration = len(speech) / SR
    results = []
    for label, path in conditions:
        for name, run in engines.items():
            t = time.perf_counter()
            hyp = normalize(str(run(path, a.language)))
            elapsed = time.perf_counter() - t
            m = jiwer.process_words(reference, hyp)
            results.append(
                {
                    "condition": label,
                    "engine": name,
                    "wer": m.wer,
                    "sub": m.substitutions,
                    "del": m.deletions,
                    "ins": m.insertions,
                    "rtf": elapsed / duration,
                    "hypothesis": hyp,
                }
            )
            print(f"{label:>16}  {name:<22} WER {m.wer:6.1%}  RTF {elapsed / duration:.2f}", file=sys.stderr)

    (out / "results.json").write_text(json.dumps(results, indent=2))
    names = list(engines)
    lines = [f"Audio: {a.audio} ({duration:.0f} s, {len(reference.split())} words)", ""]
    lines += ["| Condition | " + " | ".join(names) + " |", "| --- |" + " ---: |" * len(names)]
    for label, _ in conditions:
        row = {r["engine"]: r for r in results if r["condition"] == label}
        lines.append(f"| {label} | " + " | ".join(f"{row[n]['wer']:.1%}" for n in names) + " |")
    lines += ["", "WER in %, lower is better. Real-time factor per engine:"]
    lines += [f"- {n}: {np.mean([r['rtf'] for r in results if r['engine'] == n]):.2f}" for n in names]
    (out / "results.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
