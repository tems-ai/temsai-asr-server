import pytest

from asr_server.config import (
    DEFAULT_ENGLISH_MODEL_REVISION,
    DEFAULT_MODEL_REPO,
    DEFAULT_MODEL_REVISION,
    Settings,
)

ENV_VARS = [
    "MODEL_DIR",
    "MODEL_REPO",
    "MODEL_REVISION",
    "MODEL_PATH",
    "MODEL_ID",
    "ENGLISH_MODEL_ENABLED",
    "ENGLISH_MODEL_REPO",
    "ENGLISH_MODEL_REVISION",
    "ENGLISH_MODEL_PATH",
    "DEVICE",
    "TORCH_NUM_THREADS",
    "MAX_UPLOAD_BYTES",
    "DENOISE_ENABLED",
    "API_KEY",
    "LONG_AUDIO_SECONDS",
    "MAX_AUDIO_SECONDS",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_defaults():
    s = Settings.from_env()
    assert s.model.repo == DEFAULT_MODEL_REPO
    assert s.model.revision == DEFAULT_MODEL_REVISION
    assert s.model.path == "/models/parakeet-tdt-0.6b-v3.nemo"
    assert s.model.model_id == DEFAULT_MODEL_REPO
    assert s.english_model is None
    assert s.device == "auto"
    assert s.torch_num_threads is None
    assert s.max_upload_bytes == 200 * 1024 * 1024
    assert s.denoise is True
    assert s.api_key == ""
    assert s.long_audio_seconds == 180
    assert s.max_audio_seconds == 0


def test_english_model_enabled(monkeypatch):
    monkeypatch.setenv("ENGLISH_MODEL_ENABLED", "true")
    monkeypatch.setenv("MODEL_DIR", "/data")
    s = Settings.from_env()
    assert s.english_model.path == "/data/parakeet-tdt-0.6b-v2.nemo"
    assert s.english_model.revision == DEFAULT_ENGLISH_MODEL_REVISION


def test_custom_repo_does_not_inherit_default_revision(monkeypatch):
    monkeypatch.setenv("MODEL_REPO", "someone/custom-parakeet")
    s = Settings.from_env()
    assert s.model.revision is None  # ensure_model then refuses to download an unpinned repo
    assert s.model.path.endswith("/custom-parakeet.nemo")


def test_explicit_path_and_id(monkeypatch):
    monkeypatch.setenv("MODEL_PATH", "/opt/m.nemo")
    monkeypatch.setenv("MODEL_ID", "parakeet")
    s = Settings.from_env()
    assert (s.model.path, s.model.model_id) == ("/opt/m.nemo", "parakeet")


@pytest.mark.parametrize(
    "raw,expected",
    [("0", False), ("false", False), ("OFF", False), ("1", True), ("Yes", True), ("", True), ("  ", True)],
)
def test_bool_parsing(monkeypatch, raw, expected):
    monkeypatch.setenv("DENOISE_ENABLED", raw)
    assert Settings.from_env().denoise is expected


@pytest.mark.parametrize(
    "name,value",
    [
        ("DENOISE_ENABLED", "maybe"),
        ("DEVICE", "tpu"),
        ("MAX_UPLOAD_BYTES", "lots"),
        ("MAX_UPLOAD_BYTES", "0"),
        ("MAX_UPLOAD_BYTES", "-1"),
        ("TORCH_NUM_THREADS", "0"),
        ("TORCH_NUM_THREADS", "1.5"),
        ("LONG_AUDIO_SECONDS", "-5"),
        ("MAX_AUDIO_SECONDS", "-1"),
        ("MAX_AUDIO_SECONDS", "ten"),
    ],
)
def test_invalid_values_fail_fast(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match=name):
        Settings.from_env()


@pytest.mark.parametrize("raw", ["CUDA", " cpu "])
def test_device_is_normalized(monkeypatch, raw):
    monkeypatch.setenv("DEVICE", raw)
    assert Settings.from_env().device == raw.strip().lower()


def test_long_audio_zero_disables(monkeypatch):
    monkeypatch.setenv("LONG_AUDIO_SECONDS", "0")
    assert Settings.from_env().long_audio_seconds == 0
