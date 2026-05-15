import importlib.util
from pathlib import Path


def load_example():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "integrations"
        / "bottube_example"
        / "bottube_agent_example.py"
    )
    spec = importlib.util.spec_from_file_location("bottube_agent_example", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, status_code=200, text="ok", ok=True):
        self.status_code = status_code
        self.text = text
        self.ok = ok


class FakeSession:
    def __init__(self):
        self.trust_env = False
        self.get_calls = []
        self.post_calls = []

    def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        return FakeResponse(text=f"GET {url}")

    def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        return FakeResponse(status_code=201, text=f"POST {url}")


def test_headers_adds_authorization_only_when_api_key_present():
    module = load_example()

    assert module._headers("") == {
        "Accept": "application/json",
        "User-Agent": "bottube-agent-example/1.0",
    }
    assert module._headers("secret")["Authorization"] == "Bearer secret"


def test_endpoint_helpers_call_expected_urls_and_emit_summaries(capsys):
    module = load_example()
    session = FakeSession()

    module.check_health(session, "https://bottube.example", "token")
    module.list_videos(session, "https://bottube.example", "token", agent="agent-1")
    module.fetch_feed(session, "https://bottube.example", "token", cursor="cursor-1")

    assert session.get_calls[0][0] == "https://bottube.example/health"
    assert session.get_calls[1][0] == "https://bottube.example/api/videos"
    assert session.get_calls[1][1]["params"] == {"limit": 5, "agent": "agent-1"}
    assert session.get_calls[2][0] == "https://bottube.example/api/feed"
    assert session.get_calls[2][1]["params"] == {"cursor": "cursor-1"}
    output = capsys.readouterr().out
    assert "[HEALTH]" in output
    assert "[VIDEOS]" in output
    assert "[FEED]" in output


def test_upload_video_dry_run_skips_post(capsys):
    module = load_example()
    session = FakeSession()

    module.upload_video(session, "https://bottube.example", "token", dry_run=True)

    assert session.post_calls == []
    output = capsys.readouterr().out
    assert "[UPLOAD_DRYRUN]" in output
    assert "https://bottube.example/api/upload" in output


def test_upload_video_posts_metadata_when_not_dry_run(capsys):
    module = load_example()
    session = FakeSession()

    module.upload_video(session, "https://bottube.example", "token", dry_run=False)

    assert session.post_calls[0][0] == "https://bottube.example/api/upload"
    assert "metadata" in session.post_calls[0][1]["files"]
    assert "[UPLOAD]" in capsys.readouterr().out


def test_main_dispatches_public_only_flow(monkeypatch):
    module = load_example()
    session = FakeSession()
    monkeypatch.setattr(module.requests, "Session", lambda: session)

    result = module.main(
        [
            "--base-url",
            "https://bottube.example/",
            "--public-only",
            "--agent",
            "agent-1",
        ]
    )

    assert result == 0
    assert session.trust_env is True
    assert [call[0] for call in session.get_calls] == [
        "https://bottube.example/health",
        "https://bottube.example/api/videos",
    ]
    assert session.post_calls == []
