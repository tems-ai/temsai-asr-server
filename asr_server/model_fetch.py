"""Model resolution: use a local .nemo file when present, otherwise download it
once from Hugging Face into the model directory.

Images can be built with the default checkpoint baked in (BAKE_MODEL=true) for
air-gapped clusters; otherwise mount a volume at MODEL_DIR so restarts skip the
~2.4 GB download.
"""

import logging
import os

from .config import ModelSpec

logger = logging.getLogger(__name__)


def ensure_model(spec: ModelSpec) -> str:
    """Return the local checkpoint path, downloading it if it is missing.

    Raises RuntimeError when the file is absent and no pinned revision is
    configured — tracking a moving branch at runtime is never done implicitly.
    """
    if os.path.exists(spec.path):
        logger.info("using local checkpoint %s", spec.path)
        return spec.path
    if not spec.repo or not spec.revision:
        raise RuntimeError(
            f"model file {spec.path!r} is missing and no pinned Hugging Face revision is "
            "configured — set *_REPO and *_REVISION, or provide the file"
        )
    from huggingface_hub import hf_hub_download

    directory = os.path.dirname(spec.path) or "."
    os.makedirs(directory, exist_ok=True)
    logger.info("downloading %s@%s -> %s", spec.repo, spec.revision, spec.path)
    got = hf_hub_download(spec.repo, os.path.basename(spec.path), revision=spec.revision, local_dir=directory)
    logger.info("download complete: %s", got)
    return got
