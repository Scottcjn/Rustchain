# RustChain PoA Validator Script (Python)
# Validates genesis.json files from retro machines like PowerMac G4

import json
import base64
import hashlib
import datetime
import re

# Example MAC prefixes for Apple (vintage ranges)
VALID_MAC_PREFIXES = ["00:03:93", "00:0a:27", "00:05:02", "00:0d:93"]

def is_valid_mac(mac):
    prefix = mac.lower()[0:8]
    return any(prefix.startswith(p.lower()) for p in VALID_MAC_PREFIXES)

def is_valid_cpu(cpu):
    return any(kw in cpu.lower() for kw in ["powerpc", "g3", "g4", "7400", "7450"])

def is_reasonable_timestamp(ts):
    try:
        parsed = datetime.datetime.strptime(ts.strip(), "%a %b %d %H:%M:%S %Y")
        now = datetime.datetime.now()
        if parsed < now and parsed.year >= 1984:
            return True
    except Exception:
        pass
    return False

def recompute_hash(device, timestamp, message):
    joined = f"{device}|{timestamp}|{message}"
    sha1 = hashlib.sha1(joined.encode('utf-8')).digest()
    return base64.b64encode(sha1).decode('utf-8')

def validate_genesis(path):
    with open(path, 'r') as f:
        data = json.load(f)

    device = data.get("device", "").strip()
    timestamp = data.get("timestamp", "").strip()
    message = data.get("message", "").strip()
    fingerprint = data.get("fingerprint", "").strip()
    mac = data.get("mac_address", "").strip()
    cpu = data.get("cpu", "").strip()

    print("\nValidating genesis.json...")
    errors = []

    if not is_valid_mac(mac):
        errors.append("MAC address not in known Apple ranges")

    if not is_valid_cpu(cpu):
        errors.append("CPU string not recognized as retro PowerPC")

    if not is_reasonable_timestamp(timestamp):
        errors.append("Timestamp is invalid or too modern")

    recalculated = recompute_hash(device, timestamp, message)
    if fingerprint != recalculated:
        errors.append("Fingerprint hash does not match contents")

    if errors:
        print("❌ Validation Failed:")
        for err in errors:
            print(" -", err)
        return False
    else:
        print("✅ Genesis is verified and authentic.")
        return True

# Example usage
if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python validate_genesis.py genesis.json")
    else:
        validate_genesis(sys.argv[1])

