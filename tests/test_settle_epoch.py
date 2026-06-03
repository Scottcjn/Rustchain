import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "node" / "settle_epoch.py"


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def load_settle_epoch_module():
    spec = importlib.util.spec_from_file_location("settle_epoch_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_trigger_settlement_posts_previous_epoch(monkeypatch):
    module = load_settle_epoch_module()
    calls = []

    def fake_get(url, timeout):
        calls.append(("get", url, timeout))
        return FakeResponse(payload={"epoch": 42})

    def fake_post(url, json, timeout):
        calls.append(("post", url, json, timeout))
        return FakeResponse(status_code=200, payload={"ok": True, "settled_epoch": 41})

    monkeypatch.setattr(module.requests, "get", fake_get)
    monkeypatch.setattr(module.requests, "post", fake_post)
    monkeypatch.setattr(module.time, "strftime", lambda _fmt: "2026-05-15 10:00:00")

    result = module.trigger_settlement()

    assert result == {"ok": True, "settled_epoch": 41}
    assert calls == [
        ("get", f"{module.NODE_URL}/epoch", 10),
        ("post", f"{module.NODE_URL}/rewards/settle", {"epoch": 41}, 60),
    ]


def test_trigger_settlement_returns_truncated_error_text(monkeypatch):
    module = load_settle_epoch_module()
    long_error = "settlement failed: " + ("x" * 250)

    monkeypatch.setattr(
        module.requests,
        "get",
        lambda url, timeout: FakeResponse(payload={"epoch": 7}),
    )
    monkeypatch.setattr(
        module.requests,
        "post",
        lambda url, json, timeout: FakeResponse(status_code=500, text=long_error),
    )

    result = module.trigger_settlement()

    assert result == long_error[:200]


def test_trigger_settlement_returns_none_when_request_raises(monkeypatch, capsys):
    module = load_settle_epoch_module()

    def raise_timeout(_url, timeout):
        raise RuntimeError("node unavailable")

    monkeypatch.setattr(module.requests, "get", raise_timeout)

    assert module.trigger_settlement() is None
    assert "Error: node unavailable" in capsys.readouterr().out


def test_trigger_settlement_rejects_missing_epoch(monkeypatch, capsys):
    module = load_settle_epoch_module()
    posted = False

    def fake_post(*_args, **_kwargs):
        nonlocal posted
        posted = True
        raise AssertionError("settlement should not be posted")

    monkeypatch.setattr(
        module.requests,
        "get",
        lambda url, timeout: FakeResponse(payload={"height": 42}),
    )
    monkeypatch.setattr(module.requests, "post", fake_post)

    assert module.trigger_settlement() is None
    assert posted is False
    assert "field 'epoch' must be an integer" in capsys.readouterr().out


def test_trigger_settlement_rejects_zero_epoch(monkeypatch, capsys):
    module = load_settle_epoch_module()
    posted = False

    def fake_post(*_args, **_kwargs):
        nonlocal posted
        posted = True
        raise AssertionError("settlement should not be posted")

    monkeypatch.setattr(
        module.requests,
        "get",
        lambda url, timeout: FakeResponse(payload={"epoch": 0}),
    )
    monkeypatch.setattr(module.requests, "post", fake_post)

    assert module.trigger_settlement() is None
    assert posted is False
    assert "field 'epoch' must be greater than zero" in capsys.readouterr().out


def test_trigger_settlement_rejects_non_object_epoch_response(monkeypatch, capsys):
    module = load_settle_epoch_module()
    posted = False

    def fake_post(*_args, **_kwargs):
        nonlocal posted
        posted = True
        raise AssertionError("settlement should not be posted")

    monkeypatch.setattr(
        module.requests,
        "get",
        lambda url, timeout: FakeResponse(payload=[{"epoch": 42}]),
    )
    monkeypatch.setattr(module.requests, "post", fake_post)

    assert module.trigger_settlement() is None
    assert posted is False
    assert "/epoch response must be a JSON object" in capsys.readouterr().out
