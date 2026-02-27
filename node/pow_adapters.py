"""Chain-specific PoW proof adapters (initial: Ergo/Autolykos2)."""
from __future__ import annotations
from typing import Dict, Any, Tuple


def _is_hex(s: str, min_len: int = 8) -> bool:
    if not isinstance(s, str) or len(s) < min_len:
        return False
    try:
        int(s, 16)
        return True
    except Exception:
        return False


def validate_ergo_autolykos2(proof: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate minimal Ergo PoW proof schema (offline scaffold)."""
    if (proof.get("chain") or "").lower() != "ergo":
        return False, "chain_mismatch"

    algo = (proof.get("algorithm") or "").lower()
    if algo not in {"autolykos2", "autolykos"}:
        return False, "unsupported_algorithm"

    worker = proof.get("worker")
    if not isinstance(worker, str) or len(worker.strip()) < 2:
        return False, "missing_worker"

    proof_blob = proof.get("proof_blob") or {}
    if not isinstance(proof_blob, dict):
        return False, "invalid_proof_blob"

    tx = proof_blob.get("share_tx")
    hdr = proof_blob.get("header_hash")
    if not _is_hex(str(tx or ""), min_len=16):
        return False, "invalid_share_tx"
    if not _is_hex(str(hdr or ""), min_len=16):
        return False, "invalid_header_hash"

    return True, "ok"


def validate_chain_proof(proof: Dict[str, Any]) -> Tuple[bool, str]:
    chain = (proof.get("chain") or "").lower()
    if chain == "ergo":
        return validate_ergo_autolykos2(proof)
    return True, "no_chain_adapter"
