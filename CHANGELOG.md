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
- Local attention for long audio, DSP noise reduction for industrial
  environments, Bearer-token auth, upload and duration limits.
- CPU, CUDA 12 and CUDA 13 images for `linux/amd64` and `linux/arm64`,
  Docker Compose files, a Helm chart and plain Kubernetes manifests.
- CI: lint, unit tests, Helm/manifest validation, hadolint, smoke tests with
  the real model and a Trivy scan of the CPU image.
- Commercial license for the official images from 0.2.0 on; the source code
  stays Apache-2.0.
- Contribution terms with DCO sign-off, code of conduct, security policy and
  issue/PR templates.

### Security

- Override `hydra-core` to 1.3.4 (CVE-2026-68508).

[Unreleased]: https://github.com/tems-ai/temsai-asr-server/commits/main
