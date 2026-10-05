# Changelog

All notable changes to this project are documented in this file. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- OpenAI/Whisper-compatible `POST /v1/audio/transcriptions` for NVIDIA
  Parakeet-TDT models, with `json`, `verbose_json`, `text`, `srt` and `vtt`
  output, per-word timestamps and per-word confidence.
- 25 European languages with automatic language detection
  (`parakeet-tdt-0.6b-v3`), plus optional English routing to `v2`.
- Local attention for long audio, Bearer-token auth, upload and duration
  limits.
- CPU, CUDA 12 and CUDA 13 images for `linux/amd64` and `linux/arm64`,
  Docker Compose files, a Helm chart and plain Kubernetes manifests.
- CI: lint, unit tests, Helm/manifest validation, hadolint, smoke tests with
  the real model and a Trivy scan of the CPU image.
- Commercial license for the official images from 0.2.0 on; the source code
  stays Apache-2.0.
- Contribution terms with DCO sign-off, code of conduct, security policy and
  issue/PR templates.
- RNNoise front-end (`DENOISE_METHOD=rnnoise`, the default method when
  noise reduction is enabled) through FFmpeg's `arnndn` filter, blended 50/50
  with the original audio. The image ships the Xiph `std` model;
  `RNNOISE_MODEL_PATH` selects another. `DENOISE_METHOD=spectral` keeps the
  previous DSP filter.
- `benchmark/`: WER comparison of engines and front-ends on TTS and recorded
  speech mixed with pink, machine and industrial noise.

### Changed

- Noise reduction is now off by default (`DENOISE_ENABLED=false`). On the new
  noise benchmark Parakeet scored 2.7% average WER without it and 3.3% with the
  spectral filter.

### Security

- Override `hydra-core` to 1.3.4 (CVE-2026-68508).

[Unreleased]: https://github.com/tems-ai/temsai-asr-server/commits/main
