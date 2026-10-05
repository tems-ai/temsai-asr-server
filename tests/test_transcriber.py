import logging
import sys
import types
from dataclasses import dataclass, field

import pytest

omegaconf = pytest.importorskip("omegaconf")
OmegaConf = omegaconf.OmegaConf


@dataclass
class _StubConfidenceMethodConfig:
    name: str = "max_prob"
    entropy_type: str = "gibbs"
    alpha: float = 0.33
    entropy_norm: str = "exp"


@dataclass
class _StubConfidenceConfig:
    preserve_frame_confidence: bool = False
    preserve_token_confidence: bool = False
    preserve_word_confidence: bool = False
    exclude_blank: bool = True
    aggregation: str = "min"
    tdt_include_duration: bool = False
    method_cfg: _StubConfidenceMethodConfig = field(default_factory=_StubConfidenceMethodConfig)


@pytest.fixture()
def transcriber(monkeypatch):
    # nemo_toolkit is too heavy for the unit-test env; _configure_decoding only
    # needs the two config dataclasses, so substitute structurally-equal stubs.
    stub = types.ModuleType("nemo.collections.asr.parts.utils.asr_confidence_utils")
    stub.ConfidenceConfig = _StubConfidenceConfig
    stub.ConfidenceMethodConfig = _StubConfidenceMethodConfig
    for name in [
        "nemo",
        "nemo.collections",
        "nemo.collections.asr",
        "nemo.collections.asr.parts",
        "nemo.collections.asr.parts.utils",
    ]:
        monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
    monkeypatch.setitem(sys.modules, "nemo.collections.asr.parts.utils.asr_confidence_utils", stub)

    from asr_server.transcriber import ParakeetTranscriber

    return ParakeetTranscriber("/nonexistent.nemo", "test-model", long_audio_seconds=180)


class FakeTDTModel:
    """Replays NeMo's TDT decoding constraint (rnnt_decoding.py): word/token
    confidence forces frame confidence, which requires preserve_alignments."""

    cfg = OmegaConf.create(
        {
            "decoding": {
                "strategy": "greedy_batch",
                "preserve_alignments": None,
                "greedy": {"preserve_alignments": False},
            }
        }
    )

    def __init__(self):
        self.captured = None

    def change_decoding_strategy(self, decoding_cfg):
        preserve_alignments = decoding_cfg.get("preserve_alignments", None)
        if preserve_alignments is None:
            preserve_alignments = decoding_cfg.greedy.get("preserve_alignments", False)
        c = decoding_cfg.confidence_cfg
        frame_confidence = c.preserve_frame_confidence or c.preserve_token_confidence or c.preserve_word_confidence
        if frame_confidence and not preserve_alignments:
            raise ValueError(
                "If `preserve_frame_confidence` flag is set, then `preserve_alignments` flag must also be set."
            )
        self.captured = decoding_cfg


def test_configure_decoding_preserves_alignments(transcriber):
    transcriber.model = FakeTDTModel()
    transcriber._configure_decoding()

    cfg = transcriber.model.captured
    assert cfg is not None
    assert cfg.preserve_alignments is True
    assert cfg.confidence_cfg.preserve_word_confidence is True
    assert cfg.confidence_cfg.preserve_token_confidence is True


class FakeAttentionModel:
    def __init__(self):
        self.calls = []

    def change_attention_model(self, self_attention_model, att_context_size):
        self.calls.append((self_attention_model, list(att_context_size)))

    def transcribe(self, paths, **kwargs):
        return [
            types.SimpleNamespace(
                text="ok", score=0.0, y_sequence=[], word_confidence=[], timestamp={"word": [], "segment": []}
            )
        ]


@pytest.fixture()
def attention_model(transcriber):
    transcriber.model = FakeAttentionModel()
    transcriber._full_attention = ("rel_pos", [-1, -1])
    return transcriber


def test_short_audio_keeps_full_attention(attention_model):
    attention_model._transcribe_sync("a.wav", None, 180.0)  # boundary: equal is not "long"
    assert attention_model.model.calls == []


def test_long_audio_switches_to_local_and_back(attention_model):
    attention_model._transcribe_sync("a.wav", None, 180.01)
    attention_model._transcribe_sync("b.wav", None, 3600.0)  # already local: no redundant switch
    attention_model._transcribe_sync("c.wav", None, 5.0)
    assert attention_model.model.calls == [("rel_pos_local_attn", [256, 256]), ("rel_pos", [-1, -1])]


def test_threshold_zero_never_switches(attention_model):
    attention_model.long_audio_seconds = 0
    attention_model._transcribe_sync("a.wav", None, 10_000.0)
    assert attention_model.model.calls == []


def test_transcribe_returns_verbose_json_shape(attention_model):
    result = attention_model._transcribe_sync("a.wav", "de", 0.0)
    assert result == {
        "text": "ok",
        "language": "de",
        "duration": 0.0,
        "words": [],
        "segments": [{"id": 0, "start": 0.0, "end": 0.0, "text": "ok", "avg_logprob": 0.0}],
    }


@pytest.mark.parametrize(
    "requested,cuda,expected",
    [("auto", False, "cpu"), ("auto", True, "cuda"), ("cpu", True, "cpu"), ("cuda", True, "cuda")],
)
def test_resolve_device(monkeypatch, requested, cuda, expected):
    torch = types.SimpleNamespace(cuda=types.SimpleNamespace(is_available=lambda: cuda))
    monkeypatch.setitem(sys.modules, "torch", torch)
    from asr_server.transcriber import resolve_device

    assert resolve_device(requested) == expected


def test_resolve_device_cuda_without_gpu_fails_loudly(monkeypatch):
    torch = types.SimpleNamespace(cuda=types.SimpleNamespace(is_available=lambda: False))
    monkeypatch.setitem(sys.modules, "torch", torch)
    from asr_server.transcriber import resolve_device

    with pytest.raises(RuntimeError, match="DEVICE=cuda"):
        resolve_device("cuda")


@pytest.mark.parametrize(
    "level,emitted",
    [("ERROR", ["error"]), ("warning", ["warning", "error"]), (" info ", ["info", "warning", "error"])],
)
def test_quiet_nemo_logs_filters_below_level(level, emitted):
    from asr_server.transcriber import quiet_nemo_logs

    nemo_logger = logging.getLogger("nemo_logger")
    seen = []

    class Capture(logging.Handler):
        def emit(self, record):
            seen.append(record.getMessage())

    handler = Capture()
    nemo_logger.addHandler(handler)
    nemo_logger.setLevel(logging.DEBUG)  # NeMo resets the level itself; the filter must still apply
    try:
        quiet_nemo_logs(level)
        quiet_nemo_logs(level)  # idempotent: no stacked filters
        for name in ("info", "warning", "error"):
            getattr(nemo_logger, name)(name)
        assert seen == emitted
        assert len(nemo_logger.filters) == 1
    finally:
        nemo_logger.removeHandler(handler)
        nemo_logger.filters.clear()


@pytest.mark.parametrize("level", ["LOUD", "", "5x"])
def test_quiet_nemo_logs_rejects_unknown_level(level):
    from asr_server.transcriber import quiet_nemo_logs

    with pytest.raises(ValueError, match="NEMO_LOG_LEVEL"):
        quiet_nemo_logs(level)
