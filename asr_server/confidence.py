"""Map NeMo Parakeet-TDT hypothesis output into Whisper verbose_json shape.

Mapping contract (documented in README.md — keep in sync):
- words[].probability  := NeMo per-word confidence (entropy-based Tsallis
  alpha=0.33 exp-norm, blank-excluded, min-aggregated), clamped to [0,1].
- segments[].avg_logprob := mean(ln(clamp(p_word, 1e-6, 1))) over the words in
  the segment. Shape-compatible with Whisper (<=0, closer to 0 = better) but a
  DIFFERENT estimator — never compare numerically across providers.
- If word_confidence is unusable (NeMo-Speech#15143 length mismatch):
  probability is OMITTED and avg_logprob falls back to the length-normalized
  TDT hypothesis score (sum of chosen-token log-softmax / emitted tokens).
- no_speech_prob: OMITTED — Parakeet has no no-speech head; empty text is the
  no-speech signal. Never fabricated.
- language: request value when provided, else py3langid text classification
  restricted to the 25 supported ISO-639-1 codes (measurement, not fabrication).
"""

import logging
import math

logger = logging.getLogger(__name__)

_EPS = 1e-6

SUPPORTED_LANGUAGES = (
    "bg",
    "hr",
    "cs",
    "da",
    "nl",
    "en",
    "et",
    "fi",
    "fr",
    "de",
    "el",
    "hu",
    "it",
    "lv",
    "lt",
    "mt",
    "pl",
    "pt",
    "ro",
    "sk",
    "sl",
    "es",
    "sv",
    "ru",
    "uk",
)

_langid = None


def _detect_language(text: str) -> str:
    global _langid
    if not text.strip():
        return ""
    if _langid is None:
        import py3langid as langid

        langid.set_languages(list(SUPPORTED_LANGUAGES))
        _langid = langid
    code, _score = _langid.classify(text)
    return code


def word_probability(word_conf: float) -> float:
    return min(max(float(word_conf), 0.0), 1.0)


def segment_avg_logprob(word_probs: list[float]) -> float:
    return sum(math.log(min(max(p, _EPS), 1.0)) for p in word_probs) / len(word_probs)


def fallback_avg_logprob(hyp_score: float, n_tokens: int) -> float:
    return float(hyp_score) / max(int(n_tokens), 1)


def _hyp_fallback_avg_logprob(hyp) -> float:
    # NeMo hyps carry score/y_sequence as torch tensors; `x or default` on a
    # multi-element tensor raises "Boolean value of Tensor is ambiguous".
    score = getattr(hyp, "score", None)
    y_sequence = getattr(hyp, "y_sequence", None)
    n_tokens = 0 if y_sequence is None else len(y_sequence)
    return fallback_avg_logprob(0.0 if score is None else float(score), n_tokens)


def _words_from_hyp(hyp) -> tuple[list[dict], bool]:
    """Return (words, confidences_usable)."""
    raw = (hyp.timestamp or {}).get("word") or []
    words = [{"word": w["word"], "start": float(w["start"]), "end": float(w["end"])} for w in raw]
    confs = list(getattr(hyp, "word_confidence", None) or [])
    if words and len(confs) == len(words):
        for w, c in zip(words, confs, strict=True):
            w["probability"] = word_probability(c)
        return words, True
    if words and confs:
        logger.warning(
            "word/word_confidence length mismatch (%d vs %d) — omitting probability",
            len(words),
            len(confs),
        )
    return words, False


def _segments_from_hyp(hyp, words: list[dict], confidences_usable: bool) -> list[dict]:
    raw = (hyp.timestamp or {}).get("segment") or []
    hyp_fallback = _hyp_fallback_avg_logprob(hyp)
    segments = []
    for i, seg in enumerate(raw):
        start, end = float(seg["start"]), float(seg["end"])
        entry = {"id": i, "start": start, "end": end, "text": seg.get("segment") or seg.get("text") or ""}
        if confidences_usable:
            inside = [w["probability"] for w in words if start <= w["start"] <= end]
            entry["avg_logprob"] = segment_avg_logprob(inside) if inside else hyp_fallback
        else:
            entry["avg_logprob"] = hyp_fallback
        segments.append(entry)
    return segments


def build_verbose_json(hyp, *, language: str | None, duration: float) -> dict:
    text = getattr(hyp, "text", "") or ""
    try:
        words, confidences_usable = _words_from_hyp(hyp)
        segments = _segments_from_hyp(hyp, words, confidences_usable)
    except Exception:  # noqa: BLE001 — NeMo#14854: degrade, never 500 on timestamps
        logger.exception("timestamp extraction failed — degrading to single segment")
        words, segments = [], []
    if not segments and text:
        logger.warning("no usable timestamps — degrading to single segment spanning [0, %s]", duration)
        hyp_fallback = _hyp_fallback_avg_logprob(hyp)
        segments = [{"id": 0, "start": 0.0, "end": float(duration), "text": text, "avg_logprob": hyp_fallback}]
    return {
        "text": text,
        "language": language or _detect_language(text),
        "duration": float(duration),
        "words": words,
        "segments": segments,
    }
