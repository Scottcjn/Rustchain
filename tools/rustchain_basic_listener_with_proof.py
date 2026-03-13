#!/usr/bin/env python3
"""RustChain BASIC Listener - Watches for QBASIC validator output."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Dict, Any

WATCH_FILE: str = "validator_output.log"
KEY_PHRASE: str = "✅ Proof accepted by node network."
PROOF_OUTPUT: str = "proof_of_listen_qb45.json"


def check_for_proof() -> bool:
    """Check if proof phrase exists in watch file.
    
    Returns:
        True if proof phrase found, False otherwise
    """
    if not os.path.exists(WATCH_FILE):
        return False

    with open(WATCH_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
        for line in lines:
            if KEY_PHRASE in line:
                return True
    return False


def write_proof_json() -> None:
    """Write proof data to JSON file."""
    proof: Dict[str, Any] = {
        "validator_type": "QuickBASIC 4.5",
        "validator_id": "BASIC-KE5LVX",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "proof_type": "stdout_log_phrase",
        "status": "validated",
        "trigger": KEY_PHRASE,
        "source_file": WATCH_FILE
    }

    with open(PROOF_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(proof, f, indent=4)
    print(f"📜 Proof of listen written to {PROOF_OUTPUT}")


def main() -> None:
    """Main entry point for BASIC listener."""
    print("🕯️ RustChain BASIC Listener Activated")
    print(f"📄 Watching: {WATCH_FILE}")
    print("Waiting for BASIC flame validation...")

    try:
        while True:
            if check_for_proof():
                print("🎉 BASIC validation detected!")
                write_proof_json()
                break
            time.sleep(2)
    except KeyboardInterrupt:
        print("❌ Listener stopped manually.")


if __name__ == "__main__":
    main()
