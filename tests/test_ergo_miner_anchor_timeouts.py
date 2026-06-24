from node import ergo_miner_anchor


class FakeResponse:
    def __init__(self, payload, status_code=200, text=""):
        self._payload = payload
        self.status_code = status_code
        self.text = text

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, *, get_responses=None, post_responses=None):
        self.headers = {}
        self.get_responses = list(get_responses or [])
        self.post_responses = list(post_responses or [])
        self.get_calls = []
        self.post_calls = []

    def get(self, *args, **kwargs):
        self.get_calls.append((args, kwargs))
        return self.get_responses.pop(0)

    def post(self, *args, **kwargs):
        self.post_calls.append((args, kwargs))
        return self.post_responses.pop(0)


def test_unlock_wallet_uses_timeout_for_status_check():
    anchor = ergo_miner_anchor.ErgoMinerAnchor()
    anchor.session = FakeSession(get_responses=[FakeResponse({"isUnlocked": True})])

    assert anchor.unlock_wallet() is True
    assert anchor.session.get_calls[0][1]["timeout"] == ergo_miner_anchor.REQUEST_TIMEOUT


def test_unlock_wallet_uses_timeout_for_unlock_post(monkeypatch):
    monkeypatch.setattr(ergo_miner_anchor, "ERGO_WALLET_PASSWORD", "secret")
    anchor = ergo_miner_anchor.ErgoMinerAnchor()
    anchor.session = FakeSession(
        get_responses=[FakeResponse({"isUnlocked": False})],
        post_responses=[FakeResponse({"ok": True})],
    )

    assert anchor.unlock_wallet() is True
    assert anchor.session.get_calls[0][1]["timeout"] == ergo_miner_anchor.REQUEST_TIMEOUT
    assert anchor.session.post_calls[0][1]["timeout"] == ergo_miner_anchor.REQUEST_TIMEOUT


def test_create_anchor_tx_uses_timeout_for_node_requests(monkeypatch):
    monkeypatch.setattr(ergo_miner_anchor, "ERGO_API_KEY", "ergo-api-key")
    anchor = ergo_miner_anchor.ErgoMinerAnchor()
    anchor.session = FakeSession(
        get_responses=[
            FakeResponse({"isUnlocked": True}),
            FakeResponse([{"box": {"value": 3_000_000, "boxId": "box-1", "ergoTree": "tree"}}]),
            FakeResponse({"bytes": "raw-box"}),
            FakeResponse({"fullHeight": 100}),
        ],
        post_responses=[
            FakeResponse({"id": "signed-tx"}),
            FakeResponse({"error": "node unavailable"}, status_code=500, text="node unavailable"),
        ],
    )
    monkeypatch.setattr(anchor, "get_rc_slot", lambda: 42)

    result = anchor.create_anchor_tx([{"miner": "alice", "device_arch": "x86", "ts_ok": 1}])

    assert result == {"success": False, "error": "node unavailable"}
    assert [call[1]["timeout"] for call in anchor.session.get_calls] == [
        ergo_miner_anchor.REQUEST_TIMEOUT,
        ergo_miner_anchor.REQUEST_TIMEOUT,
        ergo_miner_anchor.REQUEST_TIMEOUT,
        ergo_miner_anchor.REQUEST_TIMEOUT,
    ]
    assert [call[1]["timeout"] for call in anchor.session.post_calls] == [
        ergo_miner_anchor.REQUEST_TIMEOUT,
        ergo_miner_anchor.REQUEST_TIMEOUT,
    ]
