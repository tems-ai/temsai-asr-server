"""Runtime configuration, read once from environment variables.

Every knob is documented in README.md ("Configuration") — keep the two in sync.
"""

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Pinned Hugging Face revisions: a runtime download must be exactly as
# immutable as a model baked into the image, so a moving `main` is never used
# unless the operator asks for it explicitly.
DEFAULT_MODEL_REPO = "nvidia/parakeet-tdt-0.6b-v3"
DEFAULT_MODEL_REVISION = "7c35754d166cca382ad1e53e68b01e7c575f3a1d"
DEFAULT_ENGLISH_MODEL_REPO = "nvidia/parakeet-tdt-0.6b-v2"
DEFAULT_ENGLISH_MODEL_REVISION = "ae9ad07059c7c739ffaf932226a8fe64ae2620b0"

_TRUE = ("1", "true", "yes", "on")
_FALSE = ("0", "false", "no", "off")


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    if raw in _TRUE:
        return True
    if raw in _FALSE:
        return False
    raise ValueError(f"{name}={raw!r} is not a boolean (use one of {_TRUE + _FALSE})")


def _int(name: str, default: int | None) -> int | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"{name}={raw!r} is not an integer") from None


def _choice(name: str, default: str, choices: tuple[str, ...]) -> str:
    raw = os.getenv(name, "").strip().lower() or default
    if raw not in choices:
        raise ValueError(f"{name}={raw!r} must be one of {choices}")
    return raw


@dataclass(frozen=True)
class ModelSpec:
    """Where a .nemo checkpoint lives locally and how to fetch it if absent."""

    model_id: str  # public id echoed by /v1/models, e.g. "nvidia/parakeet-tdt-0.6b-v3"
    path: str
    repo: str | None
    revision: str | None


def _model_spec(prefix: str, default_repo: str, default_revision: str, model_dir: str) -> ModelSpec:
    repo = os.getenv(f"{prefix}_REPO", "").strip() or default_repo
    # A custom repo without a revision must not silently inherit the default
    # model's pinned SHA (it would 404); require the operator to pin it.
    default_rev = default_revision if repo == default_repo else ""
    revision = os.getenv(f"{prefix}_REVISION", "").strip() or default_rev or None
    filename = repo.rsplit("/", 1)[-1] + ".nemo"
    path = os.getenv(f"{prefix}_PATH", "").strip() or os.path.join(model_dir, filename)
    return ModelSpec(model_id=os.getenv(f"{prefix}_ID", "").strip() or repo, path=path, repo=repo, revision=revision)


@dataclass(frozen=True)
class Settings:
    model: ModelSpec
    english_model: ModelSpec | None
    device: str  # "auto" | "cpu" | "cuda"
    torch_num_threads: int | None
    max_upload_bytes: int
    denoise: bool
    api_key: str
    long_audio_seconds: int  # switch to local attention above this; 0 disables
    max_audio_seconds: int  # reject longer audio with 413; 0 = unlimited

    @classmethod
    def from_env(cls) -> "Settings":
        model_dir = os.getenv("MODEL_DIR", "").strip() or "/models"
        english = None
        if _bool("ENGLISH_MODEL_ENABLED", False):
            english = _model_spec(
                "ENGLISH_MODEL", DEFAULT_ENGLISH_MODEL_REPO, DEFAULT_ENGLISH_MODEL_REVISION, model_dir
            )
        settings = cls(
            model=_model_spec("MODEL", DEFAULT_MODEL_REPO, DEFAULT_MODEL_REVISION, model_dir),
            english_model=english,
            device=_choice("DEVICE", "auto", ("auto", "cpu", "cuda")),
            torch_num_threads=_int("TORCH_NUM_THREADS", None),
            max_upload_bytes=_int("MAX_UPLOAD_BYTES", 200 * 1024 * 1024) or 0,
            denoise=_bool("DENOISE_ENABLED", True),
            api_key=os.getenv("API_KEY", ""),
            long_audio_seconds=_int("LONG_AUDIO_SECONDS", 180) or 0,
            max_audio_seconds=_int("MAX_AUDIO_SECONDS", 0) or 0,
        )
        if settings.max_upload_bytes <= 0:
            raise ValueError("MAX_UPLOAD_BYTES must be a positive integer")
        if settings.torch_num_threads is not None and settings.torch_num_threads <= 0:
            raise ValueError("TORCH_NUM_THREADS must be a positive integer")
        if settings.long_audio_seconds < 0:
            raise ValueError("LONG_AUDIO_SECONDS must be >= 0")
        if settings.max_audio_seconds < 0:
            raise ValueError("MAX_AUDIO_SECONDS must be >= 0")
        logger.info(
            "config: model=%s english_model=%s device=%s denoise=%s auth=%s long_audio_seconds=%s "
            "max_audio_seconds=%s",
            settings.model.model_id,
            settings.english_model.model_id if settings.english_model else None,
            settings.device,
            settings.denoise,
            bool(settings.api_key),
            settings.long_audio_seconds,
            settings.max_audio_seconds,
        )
        return settings
