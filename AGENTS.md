# AGENTS.md

Guidance for AI coding agents (Claude Code, Codex, Cursor, Copilot and others)
working in this repository. `CLAUDE.md` is a symlink to this file. Human
contributors: see [CONTRIBUTING.md](CONTRIBUTING.md).

## Project

An OpenAI/Whisper-compatible speech-to-text server (FastAPI) for NVIDIA
Parakeet-TDT models, run with NeMo on CPU or NVIDIA GPU, shipped as Docker
images, a Helm chart and plain Kubernetes manifests.

| Path | What it holds |
| --- | --- |
| `asr_server/main.py` | FastAPI app, endpoints, auth, upload limits |
| `asr_server/config.py` | Every environment variable, read once at startup |
| `asr_server/transcriber.py` | Model loading, routing (v3 / English v2), long-audio local attention, serialized inference |
| `asr_server/confidence.py` | NeMo hypothesis → Whisper `verbose_json` (words, segments, confidence) |
| `asr_server/audio.py` | ffmpeg/ffprobe decoding to 16 kHz mono |
| `asr_server/denoise.py` | High-pass + spectral-gating front-end |
| `asr_server/formats.py` | `srt` / `vtt` rendering |
| `asr_server/model_fetch.py` | Local `.nemo` file or pinned Hugging Face download |
| `tests/` | Unit tests; torch and NeMo are stubbed |
| `deploy/helm/`, `deploy/kubernetes/` | Chart, and manifests rendered from it |
| `scripts/` | `render-manifests.sh`, `smoke_test.sh` |

## Commands

```bash
pip install -r requirements/dev.txt      # no torch/NeMo needed
ruff check . && ruff format --check . && pytest
scripts/render-manifests.sh              # after any change to the Helm chart
scripts/smoke_test.sh <image>            # end-to-end with the real model (slow, ~2.4 GB download)
```

Run the first line before you finish any change. Some tests need `ffmpeg` on
`PATH` and are skipped without it.

## Rules

- **Keep docs in sync.** `config.py` and `confidence.py` say so in their
  docstrings: a new or changed environment variable, response field or
  confidence semantic must be updated in the README tables in the same change.
  User-visible changes also get a line under "Unreleased" in `CHANGELOG.md`.
- **OpenAI compatibility comes first.** Request fields and response shapes match
  OpenAI's `/v1/audio/transcriptions`. Accept unknown OpenAI fields and ignore
  them rather than rejecting them. Never fabricate values Parakeet does not
  produce (for example `no_speech_prob`): omit the field.
- **Pin everything.** Python dependencies have exact versions in
  `requirements/`; Hugging Face downloads use a pinned revision. Security
  overrides go in `requirements/overrides.txt` with the CVE and why.
- **Do not edit `deploy/kubernetes/*.yaml` by hand.** Change the chart, then run
  `scripts/render-manifests.sh`; CI fails if they differ.
- **Tests stub torch and NeMo.** Do not add them to `requirements/dev.txt`.
  Import them only lazily, inside functions in `transcriber.py`, never at
  module level. Behavior that needs the real model belongs in
  `scripts/smoke_test.sh`.
- **Style:** ruff with line length 119 and the rule set in `pyproject.toml`.
  Comments explain *why* (measurements, trade-offs), as in `denoise.py` and
  `transcriber.py`.
- **Licensing:** the source is Apache-2.0. Do not add GPL/AGPL code, model
  weights or third-party code without its license in `NOTICE`. Do not change
  `LICENSE`, `COMMERCIAL-LICENSE.md` or the contribution terms unless asked.
- **Commits** need a DCO sign-off: `git commit -s`. Never commit secrets,
  API keys or customer audio.
