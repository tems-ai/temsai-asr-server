import pytest

from conftest import make_settings, post_audio, requires_ffmpeg

KEY = "s3cret-key"


@pytest.fixture()
def client(make_client):
    return make_client(make_settings(api_key=KEY))


def test_health_is_public(client):
    assert client.get("/health").status_code == 200


@pytest.mark.parametrize(
    "header",
    [None, "", "Bearer", "Bearer ", "Bearer wrong", f"Basic {KEY}", KEY, f"Bearer {KEY}x", "Bearer " + "a" * 10_000],
)
def test_rejects_missing_or_wrong_key(client, header):
    headers = {} if header is None else {"Authorization": header}
    r = client.get("/v1/models", headers=headers)
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


def test_rejects_non_ascii_key_without_crashing(client):
    r = client.get("/v1/models", headers={"Authorization": "Bearer ключ".encode()})
    assert r.status_code == 401


@pytest.mark.parametrize("scheme", ["Bearer", "bearer", "BEARER"])
def test_accepts_correct_key(client, scheme):
    r = client.get("/v1/models", headers={"Authorization": f"{scheme} {KEY}"})
    assert r.status_code == 200


def test_transcription_requires_key_before_reading_upload(client):
    r = post_audio(client, b"x")
    assert r.status_code == 401


@requires_ffmpeg
def test_transcription_with_key(client, wav_bytes):
    r = post_audio(client, wav_bytes, headers={"Authorization": f"Bearer {KEY}"})
    assert r.status_code == 200


def test_no_key_configured_means_open(make_client):
    assert make_client(make_settings(api_key="")).get("/v1/models").status_code == 200
