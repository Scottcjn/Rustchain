# SPDX-License-Identifier: MIT
import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "miner_score.py"
spec = importlib.util.spec_from_file_location("miner_score", MODULE_PATH)
miner_score = importlib.util.module_from_spec(spec)
spec.loader.exec_module(miner_score)


def test_score_handles_list_payload_and_assigns_grades(monkeypatch, capsys):
    miners = [
        {
            "miner_id": "miner-s-tier-long-id",
            "blocks_mined": 1000,
            "antiquity_multiplier": 1.0,
            "uptime": 100,
        },
        {
            "miner_id": "miner-c-tier",
            "blocks_mined": 100,
            "antiquity_multiplier": 1.0,
            "uptime": 40,
        },
    ]
    monkeypatch.setattr(miner_score, "api", lambda path: miners)

    miner_score.score()

    output = capsys.readouterr().out
    assert "miner-s-tier-lo" in output
    assert "Score: 550" in output
    assert "Grade: S" in output
    assert "miner-c-tier" in output
    assert "Score: 70" in output
    assert "Grade: C" in output


def test_score_handles_dict_payload_filters_by_id_and_fallback_fields(monkeypatch, capsys):
    payload = {
        "miners": [
            {"id": "skip-me", "total_blocks": 999, "multiplier": 9, "uptime_pct": 99},
            {"id": "target", "total_blocks": 220, "multiplier": 2, "uptime_pct": 80},
        ]
    }
    monkeypatch.setattr(miner_score, "api", lambda path: payload)

    miner_score.score("target")

    output = capsys.readouterr().out
    assert "target" in output
    assert "Score: 260" in output
    assert "Grade: A" in output
    assert "skip-me" not in output


def test_score_defaults_missing_metrics_and_ids(monkeypatch, capsys):
    monkeypatch.setattr(miner_score, "api", lambda path: {"miners": [{}]})

    miner_score.score()

    output = capsys.readouterr().out
    assert "?" in output
    assert "Score: 25" in output
    assert "Grade: D" in output
    assert "blocks:0 mult:1.0 uptime:50%" in output


def test_score_handles_empty_or_failed_api_payload(monkeypatch, capsys):
    monkeypatch.setattr(miner_score, "api", lambda path: {})

    miner_score.score()

    assert capsys.readouterr().out == ""


def test_api_uses_configured_node_timeout_and_ssl_context(monkeypatch):
    calls = []
    contexts = []

    class DummyContext:
        check_hostname = True
        verify_mode = None

    class DummyResponse:
        def read(self):
            return b'{"miners": []}'

    def fake_context():
        context = DummyContext()
        contexts.append(context)
        return context

    def fake_urlopen(*args, **kwargs):
        calls.append((args, kwargs))
        return DummyResponse()

    monkeypatch.setattr(miner_score, "NODE", "https://node.example")
    monkeypatch.setattr(miner_score.ssl, "create_default_context", fake_context)
    monkeypatch.setattr(miner_score.urllib.request, "urlopen", fake_urlopen)

    assert miner_score.api("/api/miners") == {"miners": []}
    assert calls == [(("https://node.example/api/miners",), {"timeout": 10, "context": contexts[0]})]
    assert contexts[0].check_hostname is False
    assert contexts[0].verify_mode == miner_score.ssl.CERT_NONE


def test_api_returns_empty_dict_on_request_error(monkeypatch):
    def failing_urlopen(*_args, **_kwargs):
        raise OSError("offline")

    monkeypatch.setattr(miner_score.urllib.request, "urlopen", failing_urlopen)

    assert miner_score.api("/api/miners") == {}
