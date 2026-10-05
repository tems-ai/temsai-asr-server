"""OpenAI/Whisper-compatible transcription API for NVIDIA Parakeet-TDT models."""

import asyncio
import hmac
import logging
import os
import shutil
import tempfile
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse

from . import __version__
from .audio import AudioDecodeError, decode_to_wav_16k_mono
from .config import Settings
from .denoise import denoise_wav
from .formats import to_srt, to_vtt

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

ALLOWED_CONTENT_PREFIXES = ("audio/", "video/", "application/octet-stream")
RESPONSE_FORMATS = ("json", "verbose_json", "text", "srt", "vtt")
_CHUNK = 1024 * 1024


def _load_transcribers(settings: Settings):
    from concurrent.futures import ThreadPoolExecutor

    from .model_fetch import ensure_model
    from .transcriber import ParakeetTranscriber, resolve_device

    device = resolve_device(settings.device)
    # Shared 1-thread executor: the two routed models never infer concurrently.
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="asr")
    common = dict(
        device=device,
        executor=executor,
        torch_num_threads=settings.torch_num_threads,
        long_audio_seconds=settings.long_audio_seconds,
    )
    main = ParakeetTranscriber(ensure_model(settings.model), settings.model.model_id, **common)
    main.load()
    english = None
    if settings.english_model:
        english = ParakeetTranscriber(ensure_model(settings.english_model), settings.english_model.model_id, **common)
        english.load()
    return main, english


def create_app(settings: Settings | None = None, transcriber=None, transcriber_en=None) -> FastAPI:
    """Build the app. Tests pass settings and stub transcribers; in production
    both are resolved in the lifespan so a bad config fails startup, not import."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if app.state.settings is None:
            app.state.settings = Settings.from_env()
        if app.state.transcriber is None:
            started = time.monotonic()
            # Model restore is slow and blocking; keep it off the event loop.
            main, english = await asyncio.to_thread(_load_transcribers, app.state.settings)
            app.state.transcriber, app.state.transcriber_en = main, english
            logger.info("ready in %.1fs", time.monotonic() - started)
        yield

    app = FastAPI(title="temsai-asr-server", version=__version__, lifespan=lifespan)
    app.state.settings = settings
    app.state.transcriber = transcriber
    app.state.transcriber_en = transcriber_en

    def require_api_key(request: Request) -> None:
        expected = request.app.state.settings.api_key
        if not expected:
            return
        header = request.headers.get("authorization", "")
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not hmac.compare_digest(token.strip().encode(), expected.encode()):
            raise HTTPException(401, "invalid or missing API key", headers={"WWW-Authenticate": "Bearer"})

    def select_transcriber(model: str | None, language: str | None):
        """English requests go to the optional English-only model (measurably more
        noise-robust on English speech, and denoise HURTS it); everything else,
        including no language, goes to the multilingual model (auto-detects)."""
        en = app.state.transcriber_en
        if en is not None:
            if model and model == en.model_id:
                return en, False  # (transcriber, denoise_allowed)
            primary = (language or "").lower().replace("_", "-").split("-")[0]
            if primary == "en" and not (model and model == app.state.transcriber.model_id):
                return en, False
        return app.state.transcriber, True

    @app.get("/health")
    async def health():
        main = app.state.transcriber
        en = app.state.transcriber_en
        loaded = main is not None and main.loaded and (en is None or en.loaded)
        body = {"status": "ok" if loaded else "loading", "model_loaded": loaded}
        return JSONResponse(body, status_code=200 if loaded else 503)

    @app.get("/v1/models", dependencies=[Depends(require_api_key)])
    async def list_models():
        models = [t for t in (app.state.transcriber, app.state.transcriber_en) if t is not None]
        return {
            "object": "list",
            "data": [{"id": t.model_id, "object": "model", "owned_by": "nvidia"} for t in models],
        }

    async def _save_upload_capped(file: UploadFile, dest_path: str) -> None:
        limit = app.state.settings.max_upload_bytes
        size = 0
        with open(dest_path, "wb") as out:
            while chunk := await file.read(_CHUNK):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(413, f"file too large (limit {limit} bytes)")
                out.write(chunk)
        if size == 0:
            raise HTTPException(400, "empty file")

    @app.post("/v1/audio/transcriptions", dependencies=[Depends(require_api_key)])
    async def transcriptions(
        file: UploadFile = File(...),
        model: str | None = Form(None),
        language: str | None = Form(None),
        prompt: str | None = Form(None),
        response_format: str = Form("json"),
    ):
        # Missing content-type is treated as octet-stream; ffmpeg is the real validator
        content_type = file.content_type or "application/octet-stream"
        if not content_type.startswith(ALLOWED_CONTENT_PREFIXES):
            raise HTTPException(415, f"unsupported content type {content_type!r}")
        if response_format not in RESPONSE_FORMATS:
            raise HTTPException(400, f"unsupported response_format; use one of {RESPONSE_FORMATS}")
        language = (language or "").strip() or None
        if prompt:
            logger.info("prompt received (%d chars) — Parakeet has no biasing; ignored", len(prompt))

        settings = app.state.settings
        workdir = tempfile.mkdtemp(prefix="asr_")
        try:
            src = os.path.join(workdir, "upload.bin")
            await _save_upload_capped(file, src)
            try:
                wav, duration = await asyncio.to_thread(decode_to_wav_16k_mono, src, workdir)
            except AudioDecodeError as exc:
                raise HTTPException(400, str(exc)) from exc
            if settings.max_audio_seconds and duration > settings.max_audio_seconds:
                raise HTTPException(413, f"audio is {duration:.0f}s long; limit is {settings.max_audio_seconds}s")
            transcriber, denoise_allowed = select_transcriber(model, language)
            if settings.denoise and denoise_allowed:
                wav = await asyncio.to_thread(
                    denoise_wav, wav, workdir, settings.denoise_method, settings.rnnoise_model
                )
            started = time.monotonic()
            result = await transcriber.transcribe(wav, language=language, duration=duration)
            logger.info(
                "transcribed %.1fs audio with %s in %.1fs: %d words, %d segments",
                duration,
                transcriber.model_id,
                time.monotonic() - started,
                len(result["words"]),
                len(result["segments"]),
            )
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

        if response_format == "text":
            return PlainTextResponse(result["text"])
        if response_format == "srt":
            return PlainTextResponse(to_srt(result))
        if response_format == "vtt":
            return PlainTextResponse(to_vtt(result), media_type="text/vtt")
        if response_format == "json":
            return {"text": result["text"]}
        return {"task": "transcribe", **result}

    return app


app = create_app()
