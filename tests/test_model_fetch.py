import sys
import types

import pytest

from asr_server.config import ModelSpec
from asr_server.model_fetch import ensure_model


@pytest.fixture()
def hf_stub(monkeypatch):
    calls = []

    def fake_download(repo_id, filename, revision=None, local_dir=None):
        calls.append({"repo_id": repo_id, "filename": filename, "revision": revision, "local_dir": local_dir})
        path = f"{local_dir}/{filename}"
        with open(path, "wb") as f:
            f.write(b"weights")
        return path

    stub = types.ModuleType("huggingface_hub")
    stub.hf_hub_download = fake_download
    monkeypatch.setitem(sys.modules, "huggingface_hub", stub)
    return calls


def _spec(path, repo="nvidia/parakeet-tdt-0.6b-v3", revision="7c35754d"):
    return ModelSpec(model_id=repo or "m", path=str(path), repo=repo, revision=revision)


def test_existing_file_short_circuits_without_download(tmp_path, hf_stub):
    path = tmp_path / "model.nemo"
    path.write_bytes(b"cached")
    assert ensure_model(_spec(path)) == str(path)
    assert hf_stub == []


def test_missing_file_downloads_pinned_revision(tmp_path, hf_stub):
    path = tmp_path / "cache" / "parakeet-tdt-0.6b-v3.nemo"  # directory does not exist yet
    assert ensure_model(_spec(path)) == str(path)
    assert hf_stub == [
        {
            "repo_id": "nvidia/parakeet-tdt-0.6b-v3",
            "filename": "parakeet-tdt-0.6b-v3.nemo",
            "revision": "7c35754d",
            "local_dir": str(path.parent),
        }
    ]


@pytest.mark.parametrize(
    "repo,revision", [(None, None), ("nvidia/x", None), (None, "abc"), ("", ""), ("nvidia/x", "")]
)
def test_unpinned_or_unconfigured_download_refused(tmp_path, hf_stub, repo, revision):
    # Revision pin is mandatory — never track a moving branch at runtime.
    with pytest.raises(RuntimeError, match="pinned"):
        ensure_model(_spec(tmp_path / "absent.nemo", repo=repo, revision=revision))
    assert hf_stub == []
