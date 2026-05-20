# RustChain PoA Validator Script (Python)
# Validates genesis.json files from retro machines like PowerMac G4

import json
import base64
import hashlib
import datetime

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

def _string_field(data, name):
    value = data.get(name, "")
    if not isinstance(value, str):
        return ""
    return value.strip()

def validate_genesis(path):
    with open(path, 'r') as f:
        data = json.load(f)

    print("\nValidating genesis.json...")
    errors = []

    if not isinstance(data, dict):
        errors.append("Genesis file must contain a JSON object")
        data = {}

    device = _string_field(data, "device")
    timestamp = _string_field(data, "timestamp")
    message = _string_field(data, "message")
    fingerprint = _string_field(data, "fingerprint")
    mac = _string_field(data, "mac_address")
    cpu = _string_field(data, "cpu")

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
