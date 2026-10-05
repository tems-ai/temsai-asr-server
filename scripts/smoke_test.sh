#!/usr/bin/env bash
# End-to-end check of a built image with the real model:
#   scripts/smoke_test.sh ghcr.io/tems-ai/temsai-asr-server:cpu
# Starts the container (downloads the model on first run), waits for /health,
# transcribes a LibriSpeech sample (CC BY 4.0) and checks the words and formats.
set -euo pipefail
image=$1
port=${PORT:-18000}
name=asr-smoke-$$
key=smoke-test-key
workdir=$(mktemp -d)
trap 'docker logs "$name" 2>&1 | tail -n 40; docker rm -f "$name" >/dev/null 2>&1 || true; rm -rf "$workdir"' EXIT

curl -fsSL -o "$workdir/sample.flac" \
  https://huggingface.co/datasets/Narsil/asr_dummy/resolve/main/1.flac

docker run -d --name "$name" -p "127.0.0.1:$port:8000" -e API_KEY="$key" \
  -v "${MODELS_VOLUME:-asr-smoke-models}:/models" ${DOCKER_RUN_ARGS:-} "$image" >/dev/null

echo "waiting for the model to load..."
for _ in $(seq 1 120); do
  if curl -fs "http://127.0.0.1:$port/health" >/dev/null; then break; fi
  if [ "$(docker inspect -f '{{.State.Running}}' "$name")" != "true" ]; then echo "container exited"; exit 1; fi
  sleep 10
done
curl -fs "http://127.0.0.1:$port/health"; echo

post() { curl -fsS "http://127.0.0.1:$port/v1/audio/transcriptions" -H "Authorization: Bearer $key" \
  -F file=@"$workdir/sample.flac" "$@"; }

status=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$port/v1/audio/transcriptions" \
  -F file=@"$workdir/sample.flac")
[ "$status" = 401 ] || { echo "expected 401 without API key, got $status"; exit 1; }

text=$(post -F response_format=text)
echo "text: $text"
grep -qi "stew for dinner" <<<"$text" || { echo "unexpected transcription"; exit 1; }

post -F response_format=verbose_json | python3 -c '
import json, sys
d = json.load(sys.stdin)
assert d["language"] == "en", d["language"]
assert len(d["words"]) > 20 and all(0 <= w["probability"] <= 1 for w in d["words"]), d["words"][:3]
assert d["segments"] and d["segments"][0]["avg_logprob"] <= 0
print("verbose_json ok:", len(d["words"]), "words")'

post -F response_format=srt | grep -q -- "-->" && echo "srt ok"

# DENOISE_METHOD=rnnoise is off by default, so check the baked model is usable
# by the runtime user (a bad --chmod once made it unreadable).
docker exec "$name" ffmpeg -nostdin -v error -f lavfi -i "sine=d=1" \
  -af "arnndn=m=/usr/local/share/rnnoise/std.rnnn" -f null - && echo "rnnoise ok"
echo "SMOKE TEST PASSED"
