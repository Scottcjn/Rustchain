#!/usr/bin/env python3
import json
import os
import time
from datetime import datetime

WATCH_FILE = "validator_output.log"  # Redirected QBASIC output file
KEY_PHRASE = "✅ Proof accepted by node network."
PROOF_OUTPUT = "proof_of_listen_qb45.json"


def check_for_proof():
    if not os.path.exists(WATCH_FILE):
        return False

    with open(WATCH_FILE, "r") as f:
        lines = f.readlines()
        for line in lines:
            if KEY_PHRASE in line:
                return True
    return False

def write_proof_json():
    proof = {
        "validator_type": "QuickBASIC 4.5",
        "validator_id": "BASIC-KE5LVX",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "proof_type": "stdout_log_phrase",
        "status": "validated",
        "trigger": KEY_PHRASE,
        "source_file": WATCH_FILE
    }

    with open(PROOF_OUTPUT, "w") as f:
        json.dump(proof, f, indent=4)
    print(f"📜 Proof of listen written to {PROOF_OUTPUT}")


def listen(poll_interval=2):
    print("🕯️ RustChain BASIC Listener Activated")
    print(f"📄 Watching: {WATCH_FILE}")
    print("Waiting for BASIC flame validation...")

    while True:
        if check_for_proof():
            print("🎉 BASIC validation detected!")
            write_proof_json()
            return True
        time.sleep(poll_interval)


if __name__ == "__main__":
    try:
        listen()
    except KeyboardInterrupt:
        print("❌ Listener stopped manually.")
