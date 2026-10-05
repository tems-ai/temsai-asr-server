import pytest

from conftest import StubTranscriber, make_settings, post_audio

pytestmark = pytest.mark.usefixtures("wav_bytes")

V3 = "nvidia/parakeet-tdt-0.6b-v3"
V2 = "nvidia/parakeet-tdt-0.6b-v2"


@pytest.fixture()
def models():
    return StubTranscriber(V3, text="v3"), StubTranscriber(V2, text="v2")


@pytest.fixture()
def client(make_client, models):
    return make_client(make_settings(denoise=True), *models)


@pytest.mark.parametrize("language", ["en", "EN", "en-US", "en_GB"])
def test_english_routes_to_en_model(client, wav_bytes, language):
    assert post_audio(client, wav_bytes, language=language).json()["text"] == "v2"


@pytest.mark.parametrize("language", ["de", "ru", "fr-CA", "eng", "e", "-en"])
def test_other_languages_route_to_default_model(client, wav_bytes, language):
    assert post_audio(client, wav_bytes, language=language).json()["text"] == "v3"


def test_no_language_routes_to_default_model(client, wav_bytes):
    assert post_audio(client, wav_bytes).json()["text"] == "v3"  # v3 auto-detects


def test_explicit_model_overrides_language(client, wav_bytes):
    assert post_audio(client, wav_bytes, model=V2, language="de").json()["text"] == "v2"
    assert post_audio(client, wav_bytes, model=V3, language="en").json()["text"] == "v3"


def test_english_falls_back_when_en_model_absent(make_client, wav_bytes):
    client = make_client(make_settings(), StubTranscriber(V3, text="v3"), None)
    assert post_audio(client, wav_bytes, language="en").json()["text"] == "v3"
    assert post_audio(client, wav_bytes, model=V2).json()["text"] == "v3"


def test_denoise_skipped_for_en_model(client, wav_bytes, monkeypatch):
    # Measured on noisy ground-truth audio: denoise helps v3 (48->32% WER)
    # but HURTS v2 (24->28%) — the English path must bypass it.
    calls = []
    monkeypatch.setattr("asr_server.main.denoise_wav", lambda wav, workdir, *_: calls.append(wav) or wav)
    post_audio(client, wav_bytes, language="en")
    assert calls == []
    post_audio(client, wav_bytes, language="de")
    assert len(calls) == 1


def test_health_requires_both_models_loaded(client, models):
    models[1].loaded = False
    r = client.get("/health")
    assert r.status_code == 503
    assert r.json()["model_loaded"] is False
