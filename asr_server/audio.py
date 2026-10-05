import json
import logging
import os
import subprocess
import uuid

logger = logging.getLogger(__name__)


class AudioDecodeError(Exception):
    pass


def decode_to_wav_16k_mono(src_path: str, workdir: str) -> tuple[str, float]:
    """ffmpeg-decode any container to 16 kHz mono WAV; return (path, duration_s)."""
    out = os.path.join(workdir, f"{uuid.uuid4().hex}.wav")
    proc = subprocess.run(
        ["ffmpeg", "-nostdin", "-y", "-i", src_path, "-vn", "-ac", "1", "-ar", "16000", "-f", "wav", out],
        capture_output=True,
    )
    if proc.returncode != 0:
        logger.warning(
            "ffmpeg decode failed rc=%s stderr=%s", proc.returncode, proc.stderr[-500:].decode(errors="replace")
        )
        raise AudioDecodeError("could not decode audio")
    probe = subprocess.run(
        # NOTE: no -nostdin here — ffprobe only supports it from FFmpeg 7.0+;
        # older ffprobe builds fail with "Option not found" if passed.
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", out],
        capture_output=True,
    )
    if probe.returncode != 0:
        logger.warning(
            "ffprobe probe failed rc=%s stderr=%s", probe.returncode, probe.stderr[-500:].decode(errors="replace")
        )
        raise AudioDecodeError("could not probe decoded audio")
    try:
        duration = float(json.loads(probe.stdout)["format"]["duration"])
    except (KeyError, ValueError):
        logger.warning("could not parse duration from ffprobe output: %s", probe.stdout[:500])
        raise AudioDecodeError("could not determine audio duration") from None
    return out, duration
