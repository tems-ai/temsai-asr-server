# syntax=docker/dockerfile:1.7
#
# One Dockerfile for every published variant:
#   TORCH_VARIANT=cpu    -> CPU-only PyTorch            (linux/amd64, linux/arm64)
#   TORCH_VARIANT=cu126  -> CUDA 12.6 PyTorch, driver >= 560 (or 525+ with forward compat)
#   TORCH_VARIANT=cu130  -> CUDA 13.0 PyTorch, driver >= 580; needed for Blackwell GPUs
# The CUDA runtime ships inside the PyTorch wheels (nvidia-* pip packages), so
# the base stays python:slim — the host only needs the NVIDIA driver and the
# NVIDIA Container Toolkit.
#
#   docker build -t temsai-asr-server:cpu .
#   docker build --build-arg TORCH_VARIANT=cu126 -t temsai-asr-server:cuda12 .
#   docker build --build-arg BAKE_MODEL=true -t temsai-asr-server:cpu-offline .

# Overridable for registry mirrors (e.g. mirror.gcr.io/library/python:3.12-slim-bookworm).
ARG BASE_IMAGE=python:3.12-slim-bookworm
ARG FFMPEG_IMAGE=mwader/static-ffmpeg:8.1.1

# DL3006: both images ARE pinned — via the ARG defaults above; hadolint
# 2.12 can't resolve ARG-substituted tags.
# hadolint ignore=DL3006
FROM ${FFMPEG_IMAGE} AS ffmpeg

# hadolint ignore=DL3006
FROM ${BASE_IMAGE} AS base

# --- dependencies -------------------------------------------------------------
FROM base AS builder
ARG TORCH_VERSION=2.14.1
ARG TORCH_VARIANT=cpu

# A few NeMo transitive deps are sdist-only; the toolchain stays in this
# discarded stage.
RUN apt-get update \
    && apt-get install --no-install-recommends --no-install-suggests -y build-essential \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY requirements/runtime.txt requirements/overrides.txt /tmp/

# Wheels pattern: every dependency becomes a wheel here (toolchain discarded
# with this stage) and the runtime installs them offline. The constraint pins
# the variant's local version (e.g. 2.14.1+cpu) so pip can never swap in the
# default CUDA torch from PyPI while resolving nemo_toolkit.
RUN case "$TORCH_VARIANT" in cpu|cu126|cu130) ;; *) echo "unsupported TORCH_VARIANT=$TORCH_VARIANT" >&2; exit 1;; esac \
    && echo "torch==${TORCH_VERSION}+${TORCH_VARIANT}" > /tmp/torch-constraint.txt \
    && pip wheel --no-cache-dir --wheel-dir /usr/src/app/wheels \
       --extra-index-url "https://download.pytorch.org/whl/${TORCH_VARIANT}" \
       -c /tmp/torch-constraint.txt torch -r /tmp/runtime.txt \
    && pip wheel --no-cache-dir --no-deps --wheel-dir /usr/src/app/overrides -r /tmp/overrides.txt \
    && pip uninstall -y pip setuptools wheel

# --- optional baked checkpoint (air-gapped clusters) ---------------------------
FROM base AS model
ARG BAKE_MODEL=false
ARG MODEL_REPO=nvidia/parakeet-tdt-0.6b-v3
ARG MODEL_REVISION=7c35754d166cca382ad1e53e68b01e7c575f3a1d
RUN mkdir -p /models \
    && if [ "$BAKE_MODEL" = "true" ]; then \
         pip install --no-cache-dir "huggingface_hub>=0.30" \
         && python -c "import sys; from huggingface_hub import hf_hub_download; \
r = sys.argv[1]; hf_hub_download(r, r.rsplit('/', 1)[-1] + '.nemo', revision=sys.argv[2], local_dir='/models')" \
            "$MODEL_REPO" "$MODEL_REVISION" \
         && rm -rf /models/.cache; \
       fi

# --- runtime --------------------------------------------------------------------
FROM base AS runtime
ARG TORCH_VARIANT=cpu
ARG VERSION=dev
ARG MODEL_REPO=nvidia/parakeet-tdt-0.6b-v3
ARG MODEL_REVISION=7c35754d166cca382ad1e53e68b01e7c575f3a1d
# Self-built images are Apache-2.0 only. Official release builds (docker.yml)
# override both: see COMMERCIAL-LICENSE.md.
ARG IMAGE_LICENSE=Apache-2.0
ARG IMAGE_VENDOR=""

LABEL org.opencontainers.image.title="temsai-asr-server" \
      org.opencontainers.image.description="OpenAI/Whisper-compatible speech-to-text server for NVIDIA Parakeet-TDT (${TORCH_VARIANT})" \
      org.opencontainers.image.source="https://github.com/tems-ai/temsai-asr-server" \
      org.opencontainers.image.licenses="${IMAGE_LICENSE}" \
      org.opencontainers.image.vendor="${IMAGE_VENDOR}" \
      org.opencontainers.image.version="${VERSION}"

ENV PYTHONDONTWRITEBYTECODE=1

# libgomp1: torch's native libs link libgomp.so.1, absent from slim.
RUN apt-get update \
    && apt-get install --no-install-recommends --no-install-suggests -y ca-certificates libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Static ffmpeg/ffprobe (multi-arch). Never apt ffmpeg (~450 MB of desktop deps).
COPY --from=ffmpeg /ffmpeg /ffprobe /usr/local/bin/

# NeMo writes cache/config under $HOME, so the user gets a real home directory.
RUN groupadd -g 1000 asr \
    && useradd -u 1000 -g asr -s /usr/sbin/nologin -m -d /home/asr asr \
    && mkdir -p /models && chown asr:asr /models

COPY --from=model --chown=asr:asr /models /models

# wandb/jedi: NeMo transitive deps never touched at inference. Everything else
# that looks removable is NOT: nemo.collections.asr eagerly imports pyarrow,
# onnx, pandas, sklearn, matplotlib and IPython at load time.
# overrides (requirements/overrides.txt): security fixes newer than NeMo's own
# pins, installed over the resolved set without dependency resolution.
RUN --mount=type=bind,from=builder,source=/usr/src/app/wheels,target=/wheels \
    --mount=type=bind,from=builder,source=/usr/src/app/overrides,target=/overrides \
    pip install --no-cache-dir --no-index --find-links=/wheels/ /wheels/* \
    && pip install --no-cache-dir --no-index --no-deps /overrides/* \
    && pip uninstall -y wandb jedi \
    && pip uninstall -y pip setuptools wheel

COPY LICENSE NOTICE COMMERCIAL-LICENSE.md /licenses/

WORKDIR /app
COPY asr_server /app/asr_server

ENV PYTHONUNBUFFERED=1 \
    HOME=/home/asr \
    HF_HUB_DISABLE_PROGRESS_BARS=1 \
    HF_HUB_DISABLE_TELEMETRY=1 \
    MODEL_DIR=/models \
    MODEL_REPO=${MODEL_REPO} \
    MODEL_REVISION=${MODEL_REVISION} \
    DEVICE=auto \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility

USER 1000:1000
EXPOSE 8000
VOLUME ["/models"]

# Generous start period: the first boot downloads ~2.4 GB, every boot restores
# the .nemo checkpoint (~1 min on CPU).
HEALTHCHECK --interval=30s --timeout=5s --start-period=600s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"]

# One worker per container: each worker would load its own model copy and
# inference is serialized anyway. Scale with replicas.
CMD ["uvicorn", "asr_server.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
