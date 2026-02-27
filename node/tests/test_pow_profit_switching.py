from node.pow_proof import validate_pow_proof_payload


def test_profit_switching_ok():
    proof = {
        "proof_type": "process_detection",
        "chain": "nicehash",
        "provider": "nicehash",
        "worker": "rig-a",
        "nonce": "n1",
        "expires_at": 4102444800,
        "runtime": {"algorithm": "randomx", "coin": "xmr", "observed_at": 1700000000},
    }
    ok, meta = validate_pow_proof_payload(proof, nonce="n1", now_ts=1700000100)
    assert ok is True
    assert meta["reason"] == "ok"


def test_profit_switching_stale():
    proof = {
        "proof_type": "process_detection",
        "chain": "nicehash",
        "provider": "nicehash",
        "worker": "rig-a",
        "nonce": "n1",
        "expires_at": 4102444800,
        "runtime": {"algorithm": "randomx", "coin": "xmr", "observed_at": 1699990000},
    }
    ok, meta = validate_pow_proof_payload(proof, nonce="n1", now_ts=1700000100)
    assert ok is False
    assert meta["reason"] == "stale_profit_switching_runtime"
