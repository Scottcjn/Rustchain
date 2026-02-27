from node.pow_proof import validate_pow_proof_payload


def test_dero_pow_proof_ok():
    proof = {
        "proof_type": "pool_account",
        "chain": "dero",
        "algorithm": "astrobwt",
        "worker": "dero-rig-1",
        "nonce": "n-dero-1",
        "expires_at": 4102444800,
        "proof_blob": {
            "block_hash": "ab" * 16,
            "share_hash": "cd" * 16,
        },
    }
    ok, meta = validate_pow_proof_payload(proof, nonce="n-dero-1", now_ts=1700000000)
    assert ok is True
    assert meta["reason"] == "ok"


def test_dero_pow_proof_bad_algo():
    proof = {
        "proof_type": "pool_account",
        "chain": "dero",
        "algorithm": "sha256",
        "worker": "dero-rig-1",
        "nonce": "n-dero-1",
        "expires_at": 4102444800,
        "proof_blob": {
            "block_hash": "ab" * 16,
            "share_hash": "cd" * 16,
        },
    }
    ok, meta = validate_pow_proof_payload(proof, nonce="n-dero-1", now_ts=1700000000)
    assert ok is False
    assert str(meta["reason"]).startswith("chain_adapter_failed")
