import subprocess

import pytest

from conftest import StubTranscriber, make_settings, post_audio, requires_ffmpeg


def test_health(make_client):
    r = make_client().get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "model_loaded": True}


def test_health_503_while_model_not_loaded(make_client):
    stub = StubTranscriber()
    stub.loaded = False
    r = make_client(transcriber=stub).get("/health")
    assert r.status_code == 503
    assert r.json()["model_loaded"] is False


def test_models_lists_loaded_models(make_client):
    client = make_client(transcriber_en=StubTranscriber("nvidia/parakeet-tdt-0.6b-v2"))
    ids = [m["id"] for m in client.get("/v1/models").json()["data"]]
    assert ids == ["nvidia/parakeet-tdt-0.6b-v3", "nvidia/parakeet-tdt-0.6b-v2"]


def test_rejects_bad_content_type(make_client):
    r = post_audio(make_client(), b"hello", "f.txt", "text/plain")
    assert r.status_code == 415


@pytest.mark.parametrize("fmt", ["xml", "", "JSON", "verbose-json"])
def test_rejects_bad_response_format(make_client, fmt):
    r = post_audio(make_client(), b"RIFF", response_format=fmt)
    assert r.status_code == 400


def test_rejects_oversize(make_client):
    client = make_client(make_settings(max_upload_bytes=10))
    r = post_audio(client, b"x" * 11)
    assert r.status_code == 413


def test_accepts_exactly_max_size_upload(make_client):
    # 10 bytes == limit is allowed through to the decoder (which rejects garbage with 400)
    client = make_client(make_settings(max_upload_bytes=10))
    r = post_audio(client, b"x" * 10)
    assert r.status_code == 400


def test_rejects_empty_upload(make_client):
    r = post_audio(make_client(), b"")
    assert r.status_code == 400
    assert "empty" in r.json()["detail"]


def test_missing_file_field_is_422(make_client):
    r = make_client().post("/v1/audio/transcriptions", data={"language": "de"})
    assert r.status_code == 422


@requires_ffmpeg
def test_garbage_audio_is_400_not_500(make_client):
    r = post_audio(make_client(), b"\x00\x01not audio at all" * 100)
    assert r.status_code == 400


@requires_ffmpeg
def test_missing_content_type_reaches_decoder(make_client, wav_bytes):
    r = post_audio(make_client(), wav_bytes, content_type="")
    assert r.status_code == 200


@requires_ffmpeg
def test_default_format_is_json_text_only(make_client, wav_bytes):
    r = post_audio(make_client(), wav_bytes)
    assert r.status_code == 200
    assert r.json() == {"text": "stub"}


@requires_ffmpeg
def test_verbose_json(make_client, wav_bytes):
    r = post_audio(make_client(), wav_bytes, response_format="verbose_json", language="de", prompt="ignored, logged")
    assert r.status_code == 200
    body = r.json()
    assert body["task"] == "transcribe"
    assert body["text"] == "stub" and body["language"] == "de" and body["duration"] > 0


@requires_ffmpeg
def test_text_format(make_client, wav_bytes):
    r = post_audio(make_client(), wav_bytes, response_format="text")
    assert r.status_code == 200
    assert r.text == "stub"


@requires_ffmpeg
@pytest.mark.parametrize(
    "fmt,marker", [("srt", "00:00:00,000 --> 00:00:01,500"), ("vtt", "00:00:00.000 --> 00:00:01.500")]
)
def test_subtitle_formats(make_client, wav_bytes, fmt, marker):
    stub = StubTranscriber(segments=[{"id": 0, "start": 0.0, "end": 1.5, "text": "hello"}])
    r = post_audio(make_client(transcriber=stub), wav_bytes, response_format=fmt)
    assert r.status_code == 200
    assert marker in r.text and "hello" in r.text


@requires_ffmpeg
@pytest.mark.parametrize("language", ["", "   "])
def test_blank_language_treated_as_absent(make_client, wav_bytes, language):
    stub = StubTranscriber()
    post_audio(make_client(transcriber=stub), wav_bytes, language=language)
    assert stub.calls == [None]


@requires_ffmpeg
def test_whisper_model_name_is_accepted(make_client, wav_bytes):
    # OpenAI clients often hardcode model="whisper-1"; it must not be rejected.
    r = post_audio(make_client(), wav_bytes, model="whisper-1")
    assert r.status_code == 200


@requires_ffmpeg
def test_denoise_applied_when_enabled(make_client, wav_bytes, monkeypatch):
    calls = []
    monkeypatch.setattr("asr_server.main.denoise_wav", lambda wav, workdir, *_: calls.append(wav) or wav)
    post_audio(make_client(make_settings(denoise=True)), wav_bytes)
    assert len(calls) == 1
    post_audio(make_client(make_settings(denoise=False)), wav_bytes)
    assert len(calls) == 1


@requires_ffmpeg
@pytest.mark.parametrize("limit,status", [(1, 200), (2, 200), (0, 200)])
def test_max_audio_seconds_boundary_and_unlimited(make_client, wav_bytes, limit, status):
    # wav_bytes is exactly 1.0 s: equal to the limit is allowed, 0 means unlimited.
    r = post_audio(make_client(make_settings(max_audio_seconds=limit)), wav_bytes)
    assert r.status_code == status


@requires_ffmpeg
def test_max_audio_seconds_rejects_longer_audio_before_inference(make_client, tmp_path):
    src = str(tmp_path / "3s.wav")
    subprocess.run(
        ["ffmpeg", "-nostdin", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=3", src],
        check=True,
        capture_output=True,
    )
    stub = StubTranscriber()
    with open(src, "rb") as f:
        r = post_audio(make_client(make_settings(max_audio_seconds=2), transcriber=stub), f.read())
    assert r.status_code == 413
    assert "limit is 2s" in r.json()["detail"]
    assert stub.calls == []  # never reaches the model
