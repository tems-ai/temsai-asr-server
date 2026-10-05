import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from asr_server.config import ModelSpec, Settings
from asr_server.main import create_app

requires_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


class StubTranscriber:
    """Stands in for ParakeetTranscriber; records the languages it was asked for."""

    def __init__(self, model_id="nvidia/parakeet-tdt-0.6b-v3", text="stub", segments=None):
        self.model_id = model_id
        self.text = text
        self.segments = segments or []
        self.loaded = True
        self.calls = []

    async def transcribe(self, wav_path, *, language, duration):
        self.calls.append(language)
        return {
            "text": self.text,
            "language": language or "en",
            "duration": duration,
            "words": [],
            "segments": self.segments,
        }


def make_settings(**overrides) -> Settings:
    values = dict(
        model=ModelSpec("nvidia/parakeet-tdt-0.6b-v3", "/models/v3.nemo", "nvidia/parakeet-tdt-0.6b-v3", "x"),
        english_model=None,
        device="cpu",
        torch_num_threads=None,
        max_upload_bytes=10 * 1024 * 1024,
        denoise=False,
        denoise_method="rnnoise",
        rnnoise_model="/nonexistent/std.rnnn",
        api_key="",
        long_audio_seconds=180,
        max_audio_seconds=0,
    )
    values.update(overrides)
    return Settings(**values)


@pytest.fixture()
def make_client():
    clients = []

    def _make(settings=None, transcriber=None, transcriber_en=None):
        app = create_app(settings or make_settings(), transcriber or StubTranscriber(), transcriber_en)
        client = TestClient(app)
        client.__enter__()
        clients.append(client)
        return client

    yield _make
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture(scope="session")
def wav_bytes(tmp_path_factory):
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not installed")
    src = str(tmp_path_factory.mktemp("audio") / "in.wav")
    subprocess.run(
        ["ffmpeg", "-nostdin", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=1", src],
        check=True,
        capture_output=True,
    )
    with open(src, "rb") as f:
        return f.read()


def post_audio(client, data_bytes, filename="in.wav", content_type="audio/wav", headers=None, **form):
    return client.post(
        "/v1/audio/transcriptions",
        files={"file": (filename, data_bytes, content_type)},
        data=form,
        headers=headers or {},
    )
