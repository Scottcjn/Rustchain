# SPDX-License-Identifier: MIT
"""
The Warthog dual-mining bonus must not reach reward weight unless the operator
explicitly opts in with RC_WARTHOG_BONUS_ENABLED=1.

Every field of the Warthog proof is self-reported by the miner (collected_at is
client-supplied and may be omitted, a NaN hashrate passes `hashrate <= 0`,
wart_address is not bound to one miner), so a "verified" proof proves nothing.
Proofs keep being verified and stored for later server-side checking, but the
multiplier written to miner_attest_recent.warthog_bonus — the value
calculate_epoch_rewards_time_aged() folds into epoch weight — stays 1.0.
"""

import importlib.util
import sqlite3
import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
NODE_DIR = PROJECT_ROOT / "node"
if str(NODE_DIR) not in sys.path:
    sys.path.insert(0, str(NODE_DIR))

import warthog_verification as wv  # noqa: E402

FLAG = "RC_WARTHOG_BONUS_ENABLED"


def _pool_proof(**overrides):
    proof = {
        "enabled": True,
        "wart_address": "wart1qtest123456789",
        "proof_type": "pool",
        "pool": {"url": "https://acc-pool.pw", "hashrate": 150.5},
        "collected_at": int(time.time()),
    }
    proof.update(overrides)
    return proof


def _node_proof():
    return {
        "enabled": True,
        "wart_address": "wart1qtest123456789",
        "proof_type": "own_node",
        "node": {"height": 500000, "synced": True},
        "balance": "42.5",
        "collected_at": int(time.time()),
    }


@pytest.fixture(autouse=True)
def _reset_log_once(monkeypatch):
    monkeypatch.setattr(wv, "_disabled_logged", False)


# --------------------------------------------------------------------------
# Unit: the gate itself
# --------------------------------------------------------------------------

@pytest.mark.parametrize("value", [None, "", "0", "false", "no", "off", "2", "enabled"])
def test_flag_off_or_unrecognised_pins_multiplier_to_one(monkeypatch, value):
    if value is None:
        monkeypatch.delenv(FLAG, raising=False)
    else:
        monkeypatch.setenv(FLAG, value)
    assert not wv.warthog_bonus_enabled()
    assert wv.effective_warthog_bonus(wv.WART_BONUS_NODE) == 1.0
    assert wv.effective_warthog_bonus(wv.WART_BONUS_POOL) == 1.0
    assert wv.effective_warthog_bonus(1.0) == 1.0


@pytest.mark.parametrize("value", ["1", "true", "TRUE", " yes ", "on"])
def test_flag_on_passes_bonus_through_unchanged(monkeypatch, value):
    monkeypatch.setenv(FLAG, value)
    assert wv.warthog_bonus_enabled()
    assert wv.effective_warthog_bonus(wv.WART_BONUS_NODE) == 1.15
    assert wv.effective_warthog_bonus(wv.WART_BONUS_POOL) == 1.1
    assert wv.effective_warthog_bonus(1.0) == 1.0


def test_default_valid_looking_proof_still_verifies_but_earns_nothing(monkeypatch):
    monkeypatch.delenv(FLAG, raising=False)
    for proof, tier in ((_node_proof(), 1.15), (_pool_proof(), 1.1)):
        verified, bonus_tier, _reason = wv.verify_warthog_proof(proof, "m")
        assert verified and bonus_tier == tier  # verification code untouched
        assert wv.effective_warthog_bonus(bonus_tier if verified else 1.0) == 1.0


def test_default_nan_hashrate_and_missing_collected_at_do_not_matter(monkeypatch):
    monkeypatch.delenv(FLAG, raising=False)
    proof = _pool_proof(pool={"url": "https://acc-pool.pw", "hashrate": float("nan")})
    del proof["collected_at"]
    verified, bonus_tier, _ = wv.verify_warthog_proof(proof, "m")
    # The known weakness: this forged proof is "verified" at the pool tier...
    assert verified and bonus_tier == 1.1
    # ...but with the bonus off it cannot change weight.
    assert wv.effective_warthog_bonus(bonus_tier) == 1.0


def test_disabled_notice_is_logged_once_not_per_attestation(monkeypatch, capsys):
    monkeypatch.delenv(FLAG, raising=False)
    for _ in range(5):
        wv.effective_warthog_bonus(1.15)
    out = capsys.readouterr().out
    assert out.count("Dual-mining bonus DISABLED") == 1


def test_enabled_does_not_log_disabled_notice(monkeypatch, capsys):
    monkeypatch.setenv(FLAG, "1")
    wv.effective_warthog_bonus(1.15)
    assert "DISABLED" not in capsys.readouterr().out


# --------------------------------------------------------------------------
# Integration: /attest/submit writes the effective multiplier
# --------------------------------------------------------------------------

def _ratchet_helpers():
    """Reuse the integrated-node harness from node/tests (not run by CI itself)."""
    path = NODE_DIR / "tests" / "test_warthog_bonus_not_ratcheted.py"
    spec = importlib.util.spec_from_file_location("_warthog_ratchet_helpers", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _submit(tmp_path, monkeypatch, flag, proof):
    if flag is None:
        monkeypatch.delenv(FLAG, raising=False)
    else:
        monkeypatch.setenv(FLAG, flag)
    h = _ratchet_helpers()
    db_path = tmp_path / "warthog_gate.sqlite3"
    node = h._load_integrated_node(db_path, warthog_verified=True)
    # Use the REAL verifier and recorder, not the harness stubs.
    node.verify_warthog_proof = wv.verify_warthog_proof
    node.record_warthog_proof = wv.record_warthog_proof
    with sqlite3.connect(db_path) as conn:
        wv.init_warthog_tables(conn)
    h._prepare_db(node, db_path, seeded_bonus=1.0)
    payload = h._payload(with_warthog=False)
    payload["warthog"] = proof
    with node.app.test_client() as client:
        resp = client.post("/attest/submit", json=payload)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    with sqlite3.connect(db_path) as conn:
        stored = conn.execute(
            "SELECT warthog_bonus FROM miner_attest_recent WHERE miner = ?", (h.MINER,)
        ).fetchone()[0]
        proofs = conn.execute(
            "SELECT verified, proof_type FROM warthog_mining_proofs WHERE miner = ?", (h.MINER,)
        ).fetchall()
    return stored, proofs, resp.get_json()


def test_attest_default_off_valid_proof_stores_weight_one_but_keeps_proof(tmp_path, monkeypatch):
    stored, proofs, body = _submit(tmp_path, monkeypatch, None, _node_proof())
    assert stored == 1.0
    assert body.get("warthog_bonus") == 1.0
    assert proofs == [(1, "own_node")], "proof must still be verified and stored"


def test_attest_default_off_forged_nan_proof_stores_weight_one(tmp_path, monkeypatch):
    proof = _pool_proof(pool={"url": "https://x", "hashrate": float("nan")})
    del proof["collected_at"]
    # JSON has no NaN literal in strict mode; Flask's test client emits it anyway.
    stored, _proofs, _ = _submit(tmp_path, monkeypatch, None, proof)
    assert stored == 1.0


def test_attest_flag_on_keeps_previous_behaviour(tmp_path, monkeypatch):
    stored, proofs, body = _submit(tmp_path, monkeypatch, "1", _node_proof())
    assert stored == 1.15
    assert body.get("warthog_bonus") == 1.15
    assert proofs == [(1, "own_node")]
