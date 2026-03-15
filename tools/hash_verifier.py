#!/usr/bin/env python3
"""RustChain Hash Verifier — Verify block and transaction hashes."""
import hashlib, json, sys
def verify_block_hash(block_data):
    raw = json.dumps(block_data, sort_keys=True).encode()
    computed = hashlib.blake2b(raw, digest_size=32).hexdigest()
    stored = block_data.get("hash", "")
    match = computed == stored
    print(f"Stored:   {stored}")
    print(f"Computed: {computed}")
    print(f"Status:   {'VALID' if match else 'MISMATCH'}")
    return match
if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f: verify_block_hash(json.load(f))
    else: print("Usage: python hash_verifier.py <block.json>")
