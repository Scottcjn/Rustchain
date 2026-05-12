import importlib.util
from pathlib import Path


def load_uploader_module():
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "vintage_ai_video_pipeline" / "bottube_uploader.py"
    spec = importlib.util.spec_from_file_location("bottube_uploader", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return b'{"ok": true}'


def test_json_post_uses_urllib_request(monkeypatch):
    module = load_uploader_module()
    captured = {}

    def fake_urlopen(req, context=None, timeout=None):
        captured["request"] = req
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)
    uploader = module.BoTTubeUploader(api_key=None, base_url="https://example.test")

    result = uploader._request("POST", "/api/videos", data={"title": "demo"})

    assert result == {"ok": True}
    assert captured["request"].full_url == "https://example.test/api/videos"
    assert captured["request"].data == b'{"title": "demo"}'
    assert captured["request"].headers["Content-type"] == "application/json"
