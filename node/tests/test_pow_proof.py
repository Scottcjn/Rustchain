from node.pow_proof import validate_pow_proof_payload


def test_ergo_pow_proof_ok():
    proof = {
        "proof_type": "node_rpc",
        "chain": "ergo",
        "algorithm": "autolykos2",
        "worker": "rig-01",
        "nonce": "n-123",
        "expires_at": 4102444800,
        "proof_blob": {
            "share_tx": "ab" * 16,
            "header_hash": "cd" * 16,
        },
    }
    ok, meta = validate_pow_proof_payload(proof, nonce="n-123", now_ts=1700000000)
    assert ok is True
    assert meta["reason"] == "ok"


def test_ergo_pow_proof_bad_algo():
    proof = {
        "proof_type": "node_rpc",
        "chain": "ergo",
        "algorithm": "sha256",
        "worker": "rig-01",
        "nonce": "n-123",
        "expires_at": 4102444800,
        "proof_blob": {
            "share_tx": "ab" * 16,
            "header_hash": "cd" * 16,
        },
    }
    ok, meta = validate_pow_proof_payload(proof, nonce="n-123", now_ts=1700000000)
    assert ok is False
    assert str(meta["reason"]).startswith("chain_adapter_failed")
