import importlib.util
from pathlib import Path


def load_validator():
    module_path = Path(__file__).resolve().parents[1] / "validate_web_explorer.py"
    spec = importlib.util.spec_from_file_location("validate_web_explorer", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_check_server_returns_true_for_http_200(monkeypatch):
    module = load_validator()
    calls = []

    class Response:
        status_code = 200

    def fake_get(url, timeout):
        calls.append((url, timeout))
        return Response()

    monkeypatch.setattr(module.requests, "get", fake_get)

    assert module.check_server("https://keeper.example") is True
    assert calls == [("https://keeper.example", 5)]


def test_check_server_returns_false_for_non_200(monkeypatch):
    module = load_validator()

    class Response:
        status_code = 503

    monkeypatch.setattr(module.requests, "get", lambda url, timeout: Response())

    assert module.check_server("https://keeper.example") is False


def test_check_server_returns_false_when_request_fails(monkeypatch):
    module = load_validator()

    def raise_error(url, timeout):
        raise module.requests.RequestException("offline")

    monkeypatch.setattr(module.requests, "get", raise_error)

    assert module.check_server("https://keeper.example") is False


def test_main_returns_error_when_keeper_explorer_is_missing(monkeypatch, tmp_path):
    module = load_validator()
    monkeypatch.chdir(tmp_path)

    assert module.main() == 1


def test_main_accepts_keeper_explorer_with_required_features(
    monkeypatch,
    tmp_path,
    capsys,
):
    module = load_validator()
    monkeypatch.chdir(tmp_path)
    (tmp_path / "keeper_explorer.py").write_text(
        "\n".join(
            [
                "FONT = 'VT323'",
                "scanlines = True",
                "faucet_drip()",
                "NODE_API = proxy_api",
                "HALL_OF_RUST = []",
                "import sqlite3",
            ]
        ),
        encoding="utf-8",
    )

    assert module.main() == 0

    assert "BOUNTY COMPLIANCE VERIFIED" in capsys.readouterr().out
