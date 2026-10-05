# Noise benchmark

Compares ASR engines by word error rate on one recording at several noise levels.

- `extinguisher.txt`: reference transcript ("how to use a fire extinguisher", 214 words).
- `extinguisher.wav`: that text synthesized with espeak-ng (`-v en-us -s 190`), 60 s, 16 kHz mono.
- `machine_noise.wav`: synthetic factory-like noise (50/100/150 Hz hum, brown rumble, pink hiss), made with ffmpeg.
- `noise_benchmark.py`: mixes the noise in at the requested SNRs and scores each engine through the
  OpenAI `/v1/audio/transcriptions` API (or local openai-whisper).

```bash
docker run -d -p 8000:8000 -v asr-models:/models ghcr.io/tems-ai/temsai-asr-server:cpu
pip install jiwer numpy soundfile openai openai-whisper
python benchmark/noise_benchmark.py --audio benchmark/extinguisher.wav --reference benchmark/extinguisher.txt \
  --engine parakeet=http://localhost:8000/v1 --whisper-local large-v3 \
  --noise pink --noise benchmark/machine_noise.wav --snr clean 10 5 0 --out benchmark_out
```

TTS speech is cleaner than a real recording, so treat the results as indicative; differences show mainly
in the noisy conditions.
