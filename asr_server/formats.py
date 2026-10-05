"""Subtitle renderers for response_format=srt|vtt (same output shape as the
OpenAI transcription API)."""


def _timestamp(seconds: float, sep: str) -> str:
    millis = max(int(round(float(seconds) * 1000)), 0)
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{sep}{millis:03d}"


def _cues(result: dict) -> list[tuple[float, float, str]]:
    cues = []
    for seg in result.get("segments") or []:
        text = (seg.get("text") or "").strip()
        if text:
            cues.append((seg.get("start", 0.0), seg.get("end", 0.0), text))
    return cues


def to_srt(result: dict) -> str:
    blocks = [
        f"{i}\n{_timestamp(start, ',')} --> {_timestamp(end, ',')}\n{text}\n"
        for i, (start, end, text) in enumerate(_cues(result), start=1)
    ]
    return "\n".join(blocks)


def to_vtt(result: dict) -> str:
    blocks = [f"{_timestamp(start, '.')} --> {_timestamp(end, '.')}\n{text}\n" for start, end, text in _cues(result)]
    return "WEBVTT\n\n" + "\n".join(blocks)
