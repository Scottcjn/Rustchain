#!/usr/bin/env python3
"""Focused PoW proof validation entrypoint."""

from __future__ import annotations

from typing import Dict, Any, Tuple

from pow_adapters import (
    verify_ergo_node_rpc, verify_ergo_pool,
    verify_warthog_node_rpc, verify_warthog_pool,
)


def validate_pow_proof(pow_proof: Dict[str, Any], miner_id: str = "") -> Tuple[bool, Dict[str, Any], str]:
    if not isinstance(pow_proof, dict):
        return False, {}, "invalid_pow_proof_payload"

    coin = (pow_proof.get("coin") or "").strip().lower()
    proof_type = (pow_proof.get("proof_type") or "").strip().lower()
    evidence = pow_proof.get("evidence") if isinstance(pow_proof.get("evidence"), dict) else pow_proof

    if not coin:
        return False, {}, "missing_coin"
    if not proof_type:
        return False, {}, "missing_proof_type"

    if coin == "ergo":
        if proof_type == "node_rpc":
            ok, details, err = verify_ergo_node_rpc(evidence)
        elif proof_type == "pool":
            ok, details, err = verify_ergo_pool(evidence)
        else:
            return False, {}, f"unsupported_proof_type:{proof_type}"
    elif coin == "warthog":
        if proof_type == "node_rpc":
            ok, details, err = verify_warthog_node_rpc(evidence)
        elif proof_type == "pool":
            ok, details, err = verify_warthog_pool(evidence)
        else:
            return False, {}, f"unsupported_proof_type:{proof_type}"
    else:
        return False, {}, f"unsupported_coin:{coin}"

    if not ok:
        return False, details, err

    result = {
        "coin": coin,
        "proof_type": proof_type,
        "verified": True,
        "details": details,
        "miner_id": miner_id,
    }
    return True, result, ""
