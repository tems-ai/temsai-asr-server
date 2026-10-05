# temsai-asr-server

A self-hosted speech-to-text server for **NVIDIA Parakeet-TDT** models with an
**OpenAI/Whisper-compatible API**. Point any Whisper client at it. It runs on
CPU or NVIDIA GPU, on `amd64` and `arm64`.

- `POST /v1/audio/transcriptions`: same request and response shapes as OpenAI's
  endpoint (`json`, `verbose_json`, `text`, `srt`, `vtt`).
- Per-word timestamps and **per-word confidence** in `verbose_json`.
- 25 European languages with automatic language detection (`parakeet-tdt-0.6b-v3`).
  An optional English-only model (`v2`) can be routed for `language=en`.
- Long audio: switches the encoder to local attention above a threshold, so a
  10-minute file fits in memory on CPU.
- Optional DSP noise reduction tuned for noisy, machine-heavy environments.
- Optional Bearer-token auth, upload and duration limits.
- Images for CPU, CUDA 12 and CUDA 13 on `linux/amd64` and `linux/arm64`, plus
  Docker Compose files, a Helm chart and plain Kubernetes manifests.

## Why we open-sourced it

[Tems.AI](https://tems.ai) turns frontline manufacturing know-how into digital
guides, and much of that knowledge arrives as video recorded on the shop floor.
Two problems kept coming up with our industrial customers:

- **Sovereignty.** Many plants cannot send audio from their production floor to
  a third-party cloud API. Recordings show proprietary processes, the network
  is often isolated, and data must stay on site or in-country. They need a
  speech-to-text engine they can run themselves, on their own hardware, with
  no outbound calls at inference time.
- **Noise.** Factory audio is hard: motors, conveyors, compressors and HVAC sit
  right on top of the speech. General-purpose ASR servers transcribe whatever
  arrives and leave noise handling to the caller.

This server is our answer to both, and we publish it so that anyone with the
same constraints can use it:

- It runs **fully on premises**: CPU or GPU, x86 or ARM, Docker or Kubernetes,
  including air-gapped clusters (`BAKE_MODEL=true` puts the model in the image).
- It is **built for industrial environments**: an embedded denoise front-end
  (high-pass filter + adaptive spectral gating, tuned on real factory
  recordings) runs before recognition. On a ground-truth factory clip it cut
  the word error rate from 48% to 32%, with no extra service to deploy.
- It **speaks the OpenAI API**, so existing Whisper clients and tools switch to
  a local engine by changing a base URL.

Tems.AI is developed by TemsSoft B.V., which is certified to **ISO/IEC 27001**
for information security management.


## Quick start

> **Licensing in one line:** the source code is Apache-2.0 and free for any use.
> The official images below are free for evaluation and non-commercial use;
> running them in production for a business needs a commercial license, sized
> by the number of production hosts. Images you build yourself are always free.
> See [License](#license).

```bash
# CPU (amd64 or arm64). The first start downloads the model (~2.4 GB) into the volume.
docker run -d --name asr -p 8000:8000 -v asr-models:/models ghcr.io/tems-ai/temsai-asr-server:cpu

# NVIDIA GPU (needs the NVIDIA Container Toolkit)
docker run -d --name asr --gpus all -p 8000:8000 -v asr-models:/models ghcr.io/tems-ai/temsai-asr-server:cuda12

curl http://localhost:8000/health          # {"status":"ok","model_loaded":true} once loaded (~1 min on CPU)
curl http://localhost:8000/v1/audio/transcriptions -F file=@meeting.mp3
```

Any container format ffmpeg can read works: wav, mp3, m4a, flac, ogg, and video
files such as mp4 or mov. Audio is extracted automatically.

### With the OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="unused-or-your-API_KEY")
with open("meeting.mp3", "rb") as f:
    result = client.audio.transcriptions.create(
        model="nvidia/parakeet-tdt-0.6b-v3",  # any value is accepted, e.g. "whisper-1"
        file=f,
        response_format="verbose_json",
    )
print(result.text)
```

## Image variants

| Tag | PyTorch | Platforms | Host requirements |
| --- | --- | --- | --- |
| `cpu`, `latest`, `<version>-cpu` | CPU | amd64, arm64 | none |
| `cuda12`, `<version>-cuda12` | CUDA 12.6 | amd64, arm64 (SBSA, e.g. Grace Hopper) | NVIDIA driver ≥ 560 |
| `cuda13`, `<version>-cuda13` | CUDA 13.0 | amd64, arm64 (SBSA, e.g. Grace Blackwell) | NVIDIA driver ≥ 580; **required for Blackwell GPUs** |

The CUDA runtime ships inside the PyTorch wheels. The host only needs the
driver and the NVIDIA Container Toolkit. Jetson (L4T) is not supported by these
images. The CUDA images also run on CPU when no GPU is present (`DEVICE=auto`).

Build an image yourself (free for any use, including commercial production,
under Apache-2.0):

```bash
docker build -t temsai-asr-server:cpu .
docker build --build-arg TORCH_VARIANT=cu126 -t temsai-asr-server:cuda12 .
docker build --build-arg TORCH_VARIANT=cu130 -t temsai-asr-server:cuda13 .
docker buildx build --platform linux/arm64 -t temsai-asr-server:cpu-arm64 .
# Air-gapped clusters: bake the default checkpoint into the image (+2.4 GB)
docker build --build-arg BAKE_MODEL=true -t temsai-asr-server:cpu-offline .
```

Behind a registry mirror, override the base images with
`--build-arg BASE_IMAGE=... --build-arg FFMPEG_IMAGE=...`.

## Deployment

### Docker Compose

```bash
docker compose up -d                                         # CPU
docker compose -f compose.yaml -f compose.gpu.yaml up -d     # NVIDIA GPU
API_KEY=change-me docker compose up -d                       # with auth
```

### Kubernetes (Helm)

```bash
helm install asr ./deploy/helm/temsai-asr-server                          # CPU
helm install asr ./deploy/helm/temsai-asr-server \
  -f ./deploy/helm/temsai-asr-server/values-gpu.yaml                      # GPU (NVIDIA device plugin required)
helm install asr ./deploy/helm/temsai-asr-server --set apiKey.value=change-me
```

The chart creates a Deployment, a Service and a PVC for the model cache (kept on
uninstall), plus an optional Ingress and Secret. See
[`values.yaml`](deploy/helm/temsai-asr-server/values.yaml) for every option.
`TORCH_NUM_THREADS` follows the container CPU limit by default.

### Kubernetes (plain manifests)

```bash
kubectl create namespace asr
kubectl apply -n asr -f deploy/kubernetes/cpu.yaml   # or gpu.yaml
```

These files are rendered from the chart with default values by
`scripts/render-manifests.sh`.

## API

### `POST /v1/audio/transcriptions`

`multipart/form-data` fields:

| Field | Default | Notes |
| --- | --- | --- |
| `file` | required | Audio or video, up to `MAX_UPLOAD_BYTES`. |
| `model` | | Optional. Selects the English model when it matches its id; any other value (e.g. `whisper-1`) uses the default model. |
| `language` | | ISO-639-1 code. Not needed for recognition: the model detects the language itself. When set, it is echoed in the response, and `en` routes to the English model if enabled. When absent, the response's `language` is detected from the text (py3langid, restricted to the 25 supported languages). |
| `prompt` | | Accepted for compatibility and ignored: Parakeet has no prompt biasing. |
| `response_format` | `json` | `json` → `{"text"}`; `verbose_json` → text, language, duration, words, segments; `text`, `srt`, `vtt` → plain text. |

Other OpenAI fields such as `temperature` and `timestamp_granularities[]` are
accepted and ignored. `verbose_json` always contains both words and segments.

Errors: `400` (undecodable or empty audio, bad `response_format`), `401`
(missing or wrong API key), `413` (over `MAX_UPLOAD_BYTES` or
`MAX_AUDIO_SECONDS`), `415` (non-audio/video content type), `422` (no `file`).

Example `verbose_json`:

```json
{
  "task": "transcribe",
  "text": "He hoped there would be stew for dinner, …",
  "language": "en",
  "duration": 10.435,
  "words": [{"word": "He", "start": 0.32, "end": 0.48, "probability": 0.93}, …],
  "segments": [{"id": 0, "start": 0.32, "end": 10.24, "text": "He hoped …", "avg_logprob": -0.21}]
}
```

### Confidence semantics

- `words[].probability`: NeMo per-word confidence (entropy-based, Tsallis
  α=0.33, exp-normalized, blank-excluded, min-aggregated over tokens), in [0, 1].
- `segments[].avg_logprob`: the mean of `ln(probability)` over the segment's
  words. It has the same shape as Whisper's (≤ 0, closer to 0 is better) but
  it is **a different estimator**, so never compare the numbers across engines.
- If NeMo returns unusable word confidences, `probability` is omitted and
  `avg_logprob` falls back to the length-normalized hypothesis score.
- `no_speech_prob` is **omitted**: Parakeet has no no-speech head. Empty text
  is the no-speech signal. The server never fabricates a value.

### Other endpoints

- `GET /health`: `200 {"status":"ok","model_loaded":true}` when ready, `503`
  while loading. Never requires auth.
- `GET /v1/models`: the loaded model ids, in OpenAI's list format.

## Configuration

All settings are environment variables. Invalid values stop the server at
startup with a clear error.

| Variable | Default | Description |
| --- | --- | --- |
| `MODEL_REPO` | `nvidia/parakeet-tdt-0.6b-v3` | Hugging Face repo of the default `.nemo` checkpoint. |
| `MODEL_REVISION` | pinned commit | Required when `MODEL_REPO` is changed. Downloads are always pinned to a revision. |
| `MODEL_PATH` | `$MODEL_DIR/<repo-name>.nemo` | Use a local checkpoint file instead. |
| `MODEL_ID` | `MODEL_REPO` | Id reported by `/v1/models`. |
| `MODEL_DIR` | `/models` | Download/cache directory. Mount a volume here. |
| `ENGLISH_MODEL_ENABLED` | `false` | Also load `nvidia/parakeet-tdt-0.6b-v2` and route `language=en` to it. On noisy English audio it halved WER compared with v3 (48% → 24%) in our tests. Costs about 3 GB more RAM. `ENGLISH_MODEL_REPO`, `_REVISION`, `_PATH` and `_ID` work like the `MODEL_*` variables. |
| `DEVICE` | `auto` | `auto`, `cpu` or `cuda`. With `cuda`, startup fails if no GPU is visible. |
| `TORCH_NUM_THREADS` | torch default | CPU threads used for inference. |
| `DENOISE_ENABLED` | `true` | Applies an 80 Hz high-pass filter, non-stationary spectral gating and peak normalization before the multilingual model. Never applied to the English model, where it hurt accuracy. |
| `LONG_AUDIO_SECONDS` | `180` | Above this duration the encoder uses local attention (256/256 context). `0` keeps full attention always. |
| `MAX_AUDIO_SECONDS` | `0` (unlimited) | Rejects longer audio with `413` before inference. |
| `MAX_UPLOAD_BYTES` | `209715200` (200 MB) | Upload size limit. |
| `API_KEY` | empty | When set, `/v1/*` requires `Authorization: Bearer <API_KEY>`. |
| `LOG_LEVEL` | `INFO` | Server log level. |
| `NEMO_LOG_LEVEL` | `ERROR` | NeMo's log level after the model has loaded. NeMo repeats warnings on every request otherwise. |

## Sizing

Measured on CPU (4 threads, x86_64) with `parakeet-tdt-0.6b-v3`:

| | |
| --- | --- |
| Model load | ~60 s; peak RSS ~6–7 GB, resident ~6 GB |
| 10 s of speech | ~1 s (RTFx ≈ 10) |
| 130 s / 300 s / 611 s audio (local attention) | 11 s / 24 s / 47 s |
| Extra memory per request | ~0.45 GB per minute of audio (≈ 10 GB peak for a 10-min file) |

Measured with full attention, for comparison: 300 s of audio took 58 s, peaked at
9.3 GB and dropped words, and 611 s ran out of memory on a 15 GB host. Local
attention handled all of these lengths, which is why the default threshold is
180 s.

Inference is serialized within a container: one request runs at a time and
others queue. Scale throughput with replicas. Use `MAX_AUDIO_SECONDS` together
with the memory limit, or split very long recordings on the client side.

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements/dev.txt   # no torch/NeMo needed: unit tests stub them
ruff check . && ruff format --check . && pytest

# End-to-end with the real model (builds nothing, uses an existing image):
scripts/smoke_test.sh temsai-asr-server:cpu
```

CI (`.github/workflows/`) runs lint, unit tests, Helm/manifest validation and
hadolint on every push and PR. Image builds are smoke-tested with the real
model:

- pushes to `main` and PRs that touch the image build only the CPU `linux/amd64`
  image and publish nothing;
- a release tag `vX.Y.Z` builds all six variants on native amd64 and arm64
  runners and publishes multi-arch manifests to GHCR;
- **Run workflow** (manual) builds all six without publishing.

## License

**Source code: [Apache-2.0](LICENSE).** You can use, modify and redistribute the
code, and run images you build from it, for any purpose, commercial included,
free of charge.

**Official images: [commercial license](COMMERCIAL-LICENSE.md).** The images
Tems.AI publishes at `ghcr.io/tems-ai/temsai-asr-server`, from version 0.2.0 on:

| Use | Official images | Images you build yourself |
| --- | --- | --- |
| Personal, non-commercial, education | Free | Free |
| Evaluation, development, testing, CI, PoC | Free | Free |
| Commercial production use | **Commercial license** | Free (Apache-2.0) |
| Updates and support from Tems.AI | With a license | No |

The commercial license is a subscription sized by the **maximum number of
production hosts**: the nodes of each production Kubernetes cluster that runs
the images (or only the dedicated node pool, if you pin the images to one), or
the Docker hosts that run them. Details are in
[COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md). For pricing and licenses, write
to **support@tems.ai**. Licenses are granted by TemsSoft B.V., the ISO/IEC
27001-certified company that develops Tems.AI.

What the license pays for is the maintained build: six tested image variants
(CPU, CUDA 12 and CUDA 13 on amd64 and arm64), pinned NeMo and PyTorch
versions, vulnerability scanning and patched dependencies, and support. If you
would rather maintain your own build, `docker build .` gives you the same
server under Apache-2.0. Images released before 0.2.0 stay Apache-2.0.

Third-party components keep their own licenses, listed in [NOTICE](NOTICE) and
copied into every image under `/licenses`. The model weights are **not** part of
this repository and are downloaded from Hugging Face at runtime:
`nvidia/parakeet-tdt-0.6b-v3` and `-v2` are licensed by NVIDIA under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). If you redistribute
an image built with `BAKE_MODEL=true`, it contains those weights, so keep the
attribution from [NOTICE](NOTICE).

Images derived from the official images (built `FROM` them, or modified,
mirrored or re-tagged copies) stay under the commercial license, and if you
publish one it must be distributed under that license too. Images you build
yourself from source are Apache-2.0 and may be published, but not under the
Tems.AI name: "Tems.AI" is a trademark of TemsSoft B.V., and a public
self-built image must not use "Tems.AI", "TemsAI" or "temsai" in its image name,
tags or vendor label.

This project is not affiliated with or endorsed by NVIDIA. "NVIDIA" and
"Parakeet" are used only to identify the models this server runs.
