import asyncio
import copy
import logging
import os
from concurrent.futures import ThreadPoolExecutor

from .confidence import build_verbose_json

logger = logging.getLogger(__name__)

# Parakeet's FastConformer encoder uses full self-attention, whose memory grows
# quadratically with audio length. Above LONG_AUDIO_SECONDS the encoder is
# switched to limited-context ("local") attention, which the model card
# documents for audio up to ~3 h, and switched back afterwards. Measured on
# CPU (v3): full attention is accurate to ~3 min, drops words by 5 min and
# OOMs a 15 GB host at 10 min; local attention handled all three.
LOCAL_ATTENTION = "rel_pos_local_attn"
LOCAL_ATTENTION_CONTEXT = [256, 256]


class _MinLevelFilter(logging.Filter):
    def __init__(self, level: int):
        super().__init__()
        self.level = level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno >= self.level


def quiet_nemo_logs(level_name: str) -> None:
    """NeMo repeats the same dataloader warnings on every transcribe() call and
    forces its logger to WARNING inside transcribe(), so setLevel() is undone
    per request. A filter on the logger survives that; load-time output (logged
    before this runs) is kept."""
    level = logging.getLevelName(level_name.strip().upper())
    if not isinstance(level, int):
        raise ValueError(f"NEMO_LOG_LEVEL={level_name!r} is not a logging level")
    nemo_logger = logging.getLogger("nemo_logger")
    for existing in [f for f in nemo_logger.filters if isinstance(f, _MinLevelFilter)]:
        nemo_logger.removeFilter(existing)
    nemo_logger.addFilter(_MinLevelFilter(level))


def resolve_device(requested: str) -> str:
    """Map DEVICE=auto|cpu|cuda to a torch device string; fail loudly when
    cuda is requested but unavailable rather than silently running on CPU."""
    import torch

    cuda = torch.cuda.is_available()
    if requested == "cuda" and not cuda:
        raise RuntimeError(
            "DEVICE=cuda but torch sees no CUDA device (missing GPU, driver, or NVIDIA container runtime?)"
        )
    if requested == "auto":
        return "cuda" if cuda else "cpu"
    return requested


class ParakeetTranscriber:
    """NeMo Parakeet-TDT wrapper. A single-thread executor serializes inference
    (one model copy in memory, requests queue in asyncio, /health stays
    responsive; horizontal scale = replicas)."""

    def __init__(
        self,
        model_path: str,
        model_id: str,
        *,
        device: str = "cpu",
        executor: ThreadPoolExecutor | None = None,
        torch_num_threads: int | None = None,
        long_audio_seconds: int = 0,
    ):
        # executor may be shared across instances so two routed models (en/multi)
        # never run inference concurrently — one forward pass at a time.
        self.model_path = model_path
        self.model_id = model_id
        self.device = device
        self.torch_num_threads = torch_num_threads
        self.long_audio_seconds = long_audio_seconds
        self.model = None
        self._full_attention: tuple[str, list[int]] | None = None
        self._local_attention_active = False
        self._executor = executor or ThreadPoolExecutor(max_workers=1)

    @property
    def loaded(self) -> bool:
        return self.model is not None

    def load(self) -> None:
        import nemo.collections.asr as nemo_asr
        import torch

        if self.torch_num_threads:
            torch.set_num_threads(self.torch_num_threads)
        logger.info("loading %s on %s", self.model_path, self.device)
        self.model = nemo_asr.models.ASRModel.restore_from(self.model_path, map_location=self.device)
        self.model.to(self.device)
        self.model.eval()
        self._configure_decoding()
        encoder_cfg = self.model.cfg.get("encoder", {})
        self._full_attention = (
            encoder_cfg.get("self_attention_model", "rel_pos"),
            list(encoder_cfg.get("att_context_size", [-1, -1])),
        )
        logger.info("model loaded: %s (attention=%s)", self.model_id, self._full_attention)
        quiet_nemo_logs(os.getenv("NEMO_LOG_LEVEL", "").strip() or "ERROR")

    def _configure_decoding(self) -> None:
        from nemo.collections.asr.parts.utils.asr_confidence_utils import (
            ConfidenceConfig,
            ConfidenceMethodConfig,
        )
        from omegaconf import open_dict

        confidence_cfg = ConfidenceConfig(
            preserve_word_confidence=True,
            preserve_token_confidence=True,
            exclude_blank=True,
            aggregation="min",
            tdt_include_duration=False,
            method_cfg=ConfidenceMethodConfig(name="entropy", entropy_type="tsallis", alpha=0.33, entropy_norm="exp"),
        )
        decoding_cfg = copy.deepcopy(self.model.cfg.decoding)
        with open_dict(decoding_cfg):
            decoding_cfg.confidence_cfg = confidence_cfg
            # Word/token confidence forces frame confidence internally, and TDT
            # decoding rejects frame confidence without preserved alignments.
            decoding_cfg.preserve_alignments = True
        self.model.change_decoding_strategy(decoding_cfg)

    def _set_attention(self, local: bool) -> None:
        """Switch encoder attention; runs on the inference thread only, so it
        can never race a forward pass of this model."""
        if local == self._local_attention_active or self._full_attention is None:
            return
        if local:
            logger.info("switching to local attention %s for long audio", LOCAL_ATTENTION_CONTEXT)
            # The conv front-end already auto-chunks (subsampling_conv_chunking_factor
            # defaults to 1); don't touch it — NeMo's -1 ("off") path crashes in 3.0.
            self.model.change_attention_model(LOCAL_ATTENTION, LOCAL_ATTENTION_CONTEXT)
        else:
            logger.info("restoring full attention %s", self._full_attention)
            self.model.change_attention_model(*self._full_attention)
        self._local_attention_active = local

    def _transcribe_sync(self, wav_path: str, language: str | None, duration: float) -> dict:
        self._set_attention(bool(self.long_audio_seconds) and duration > self.long_audio_seconds)
        # language is NOT passed to the model — Parakeet auto-detects and takes no
        # language argument; the param only feeds the response field.
        hyps = self.model.transcribe([wav_path], timestamps=True, return_hypotheses=True, batch_size=1, verbose=False)
        return build_verbose_json(hyps[0], language=language, duration=duration)

    async def transcribe(self, wav_path: str, *, language: str | None, duration: float) -> dict:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, self._transcribe_sync, wav_path, language, duration)
