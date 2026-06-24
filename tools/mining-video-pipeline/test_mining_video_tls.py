import importlib.util
from pathlib import Path


def load_pipeline_module():
    module_path = Path(__file__).with_name("mining_video_pipeline.py")
    spec = importlib.util.spec_from_file_location("mining_video_pipeline", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_fetch_miners_verifies_tls_by_default(monkeypatch):
    pipeline = load_pipeline_module()
    calls = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"miners": []}

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.delenv("RUSTCHAIN_VIDEO_PIPELINE_INSECURE_TLS", raising=False)
    monkeypatch.setattr(pipeline.requests, "get", fake_get)

    assert pipeline.fetch_miners() == []
    assert calls[0][1]["verify"] is True


def test_fetch_epoch_allows_explicit_insecure_tls(monkeypatch):
    pipeline = load_pipeline_module()
    calls = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"epoch": 1}

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(pipeline.requests, "get", fake_get)

    assert pipeline.fetch_epoch(insecure_tls=True) == {"epoch": 1}
    assert calls[0][1]["verify"] is False


def test_env_can_opt_into_insecure_tls(monkeypatch):
    pipeline = load_pipeline_module()

    monkeypatch.setenv("RUSTCHAIN_VIDEO_PIPELINE_INSECURE_TLS", "true")

    assert pipeline._verify_tls() is False
