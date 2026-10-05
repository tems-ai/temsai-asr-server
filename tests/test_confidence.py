import math
from types import SimpleNamespace

from asr_server.confidence import (
    build_verbose_json,
    fallback_avg_logprob,
    segment_avg_logprob,
    word_probability,
)


def _hyp(
    words=None, segments=None, text="hello world", score=-2.0, word_confidence=(0.9, 0.8), y_sequence=(1, 2, 3, 4)
):
    return SimpleNamespace(
        text=text,
        score=score,
        word_confidence=list(word_confidence),
        y_sequence=list(y_sequence),
        timestamp={
            "word": words
            if words is not None
            else [
                {"word": "hello", "start": 0.1, "end": 0.5},
                {"word": "world", "start": 0.6, "end": 1.0},
            ],
            "segment": segments
            if segments is not None
            else [
                {"start": 0.1, "end": 1.0, "segment": "hello world"},
            ],
        },
    )


def test_word_probability_clamps():
    assert word_probability(0.93) == 0.93
    assert word_probability(-0.1) == 0.0
    assert word_probability(1.7) == 1.0


def test_segment_avg_logprob_is_mean_ln():
    got = segment_avg_logprob([0.5, 0.5])
    assert math.isclose(got, math.log(0.5))
    assert segment_avg_logprob([1.0]) == 0.0  # never positive
    assert segment_avg_logprob([0.0]) == math.log(1e-6)  # clamped, no -inf


def test_fallback_avg_logprob_normalizes_by_tokens():
    assert fallback_avg_logprob(-4.0, 4) == -1.0
    assert fallback_avg_logprob(-4.0, 0) == -4.0  # max(n,1) guard


def test_build_verbose_json_shape():
    out = build_verbose_json(_hyp(), language="en", duration=1.0)
    assert out["text"] == "hello world"
    assert out["language"] == "en"
    assert out["duration"] == 1.0
    assert out["words"][0] == {"word": "hello", "start": 0.1, "end": 0.5, "probability": 0.9}
    seg = out["segments"][0]
    assert seg["id"] == 0 and seg["text"] == "hello world"
    assert seg["avg_logprob"] <= 0.0
    assert "no_speech_prob" not in seg  # NEVER fabricated


def test_word_confidence_length_mismatch_omits_probability():
    hyp = _hyp(word_confidence=[0.9])  # 1 conf for 2 words (NeMo-Speech#15143)
    out = build_verbose_json(hyp, language="en", duration=1.0)
    assert all("probability" not in w for w in out["words"])
    # segments fall back to length-normalized hypothesis score
    assert math.isclose(out["segments"][0]["avg_logprob"], -2.0 / 4)


def test_timestamp_failure_degrades_to_single_segment():
    hyp = _hyp()
    hyp.timestamp = None  # NeMo#14854 crash path
    out = build_verbose_json(hyp, language="en", duration=7.5)
    assert out["words"] == []
    assert out["segments"] == [{"id": 0, "start": 0.0, "end": 7.5, "text": "hello world", "avg_logprob": -2.0 / 4}]


def test_timestamp_extraction_exception_degrades_gracefully():
    # Force an actual exception inside _words_from_hyp by omitting "start" key.
    # This exercises the except-branch that is NOT covered by test_timestamp_failure_degrades_to_single_segment.
    hyp = _hyp(words=[{"word": "hello"}])  # Missing "start" and "end" keys
    out = build_verbose_json(hyp, language="en", duration=3.0)
    # No exception should propagate.
    assert out["words"] == []
    assert len(out["segments"]) == 1
    seg = out["segments"][0]
    assert seg["id"] == 0
    assert seg["start"] == 0.0
    assert seg["end"] == 3.0
    assert seg["text"] == "hello world"
    # avg_logprob should be the fallback value
    assert math.isclose(seg["avg_logprob"], -2.0 / 4)


class _TensorStub:
    """Mimics torch.Tensor: bool() on a multi-element tensor raises, len() works."""

    def __init__(self, values):
        self._values = list(values)

    def __bool__(self):
        raise RuntimeError("Boolean value of Tensor with more than one value is ambiguous")

    def __len__(self):
        return len(self._values)


def test_tensor_y_sequence_fallback_does_not_crash():
    # Real NeMo hyps carry y_sequence as a torch.Tensor; `x or []` on it raises.
    hyp = _hyp(word_confidence=[0.9])  # length mismatch → fallback uses y_sequence
    hyp.y_sequence = _TensorStub([1, 2, 3, 4])
    out = build_verbose_json(hyp, language="en", duration=1.0)
    assert math.isclose(out["segments"][0]["avg_logprob"], -2.0 / 4)


def test_tensor_y_sequence_degraded_segment_does_not_crash():
    hyp = _hyp()
    hyp.timestamp = None  # degraded single-segment path also reads y_sequence
    hyp.y_sequence = _TensorStub([1, 2, 3, 4])
    out = build_verbose_json(hyp, language="en", duration=7.5)
    assert out["segments"] == [{"id": 0, "start": 0.0, "end": 7.5, "text": "hello world", "avg_logprob": -2.0 / 4}]


def test_language_detection_when_not_given():
    out = build_verbose_json(_hyp(), language=None, duration=1.0)
    assert out["language"] == "en"  # py3langid restricted to the 25 supported codes


def test_empty_text_echoes_language_or_empty():
    hyp = _hyp(text="", words=[], segments=[])
    assert build_verbose_json(hyp, language="de", duration=1.0)["language"] == "de"
    assert build_verbose_json(hyp, language=None, duration=1.0)["language"] == ""
