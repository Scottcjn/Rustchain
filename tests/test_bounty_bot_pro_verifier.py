import importlib.util
import sys
import types
from pathlib import Path


def load_verifier(monkeypatch):
    github_module = types.ModuleType("github")
    github_module.Github = object
    github_module.GithubException = Exception
    requests_module = types.ModuleType("requests")
    requests_module.head = lambda *args, **kwargs: None
    requests_module.get = lambda *args, **kwargs: None
    dotenv_module = types.ModuleType("dotenv")
    dotenv_module.load_dotenv = lambda: None
    google_module = types.ModuleType("google")
    genai_module = types.ModuleType("google.generativeai")
    genai_module.configure = lambda **kwargs: None
    genai_module.GenerativeModel = lambda name: object()
    google_module.generativeai = genai_module
    monkeypatch.setitem(sys.modules, "github", github_module)
    monkeypatch.setitem(sys.modules, "requests", requests_module)
    monkeypatch.setitem(sys.modules, "dotenv", dotenv_module)
    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.generativeai", genai_module)

    path = Path(__file__).resolve().parents[1] / "tools" / "bounty-bot-pro" / "verifier.py"
    spec = importlib.util.spec_from_file_location("bounty_bot_pro_verifier", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_article_head_request_is_bounded(monkeypatch):
    verifier_module = load_verifier(monkeypatch)
    verifier = verifier_module.BountyVerifier.__new__(verifier_module.BountyVerifier)
    monkeypatch.setattr(verifier, "verify_stars", lambda username: {"count": 0, "is_star_king": False, "repos": []})
    monkeypatch.setattr(verifier, "verify_following", lambda username: False)
    monkeypatch.setattr(verifier, "verify_wallet", lambda wallet: {"exists": False, "error": "not_found"})
    captured = {}

    class Response:
        status_code = 200

    def fake_head(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return Response()

    monkeypatch.setattr(verifier_module.requests, "head", fake_head)

    report = verifier.generate_report("alice", "wallet", "https://example.test/article")

    assert "Article link" in report
    assert captured["url"] == "https://example.test/article"
    assert captured["kwargs"]["timeout"] == verifier_module.CONFIG["article_check_timeout"]
