# Noise benchmark

Compares ASR engines by word error rate on one recording at several noise levels.

- `extinguisher.txt`: reference transcript ("how to use a fire extinguisher", 214 words).
- `extinguisher.wav`: that text synthesized with espeak-ng (`-v en-us -s 190`), 60 s, 16 kHz mono.
- `machine_noise.wav`: synthetic factory-like noise (50/100/150 Hz hum, brown rumble, pink hiss), made with ffmpeg.
- `noise_benchmark.py`: mixes the noise in at the requested SNRs and scores each engine through the
  OpenAI `/v1/audio/transcriptions` API (or local openai-whisper).

Both WAVs are synthetic and committed with `git add -f` (the repo ignores `*.wav`). They were made with:

```bash
espeak-ng -v en-us -s 190 -w /tmp/tts.wav -f benchmark/extinguisher.txt
ffmpeg -y -i /tmp/tts.wav -ar 16000 -ac 1 benchmark/extinguisher.wav
ffmpeg -y -f lavfi -i "sine=f=50:d=60" -f lavfi -i "sine=f=100:d=60" -f lavfi -i "sine=f=150:d=60" \
  -f lavfi -i "anoisesrc=c=brown:d=60:a=0.5" -f lavfi -i "anoisesrc=c=pink:d=60:a=0.2" \
  -filter_complex "amix=inputs=5:weights=1 0.6 0.4 1.5 1,tremolo=f=6:d=0.3" -ar 16000 -ac 1 benchmark/machine_noise.wav
```

Then run the comparison:

```bash
docker run -d -p 8000:8000 -v asr-models:/models ghcr.io/tems-ai/temsai-asr-server:cpu
pip install jiwer numpy soundfile openai openai-whisper
python benchmark/noise_benchmark.py --audio benchmark/extinguisher.wav --reference benchmark/extinguisher.txt \
  --engine parakeet=http://localhost:8000/v1 --whisper-local large-v3 \
  --noise pink --noise benchmark/machine_noise.wav --snr clean 10 5 0 --out benchmark_out
```

TTS speech is cleaner than a real recording, so treat the results as indicative; differences show mainly
in the noisy conditions.
