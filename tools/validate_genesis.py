# RustChain PoA Validator Script (Python)
# Validates genesis.json files from retro machines like PowerMac G4
# Supports both vintage retro-machine and standard blockchain genesis formats

import json
import base64
import hashlib
import datetime
import sys
import logging

logger = logging.getLogger(__name__)

# Example MAC prefixes for Apple (vintage ranges)
VALID_MAC_PREFIXES = ["00:03:93", "00:0a:27", "00:05:02", "00:0d:93"]

# Standard blockchain genesis required fields
REQUIRED_GENESIS_FIELDS = [
    "genesis_time",
    "chain_id",
    "initial_height",
    "app_hash",
]

# Vintage retro genesis required fields
REQUIRED_VINTAGE_FIELDS = [
    "device",
    "timestamp",
    "message",
    "fingerprint",
    "mac_address",
    "cpu",
]


def is_valid_mac(mac):
    prefix = mac.lower()[0:8]
    return any(prefix.startswith(p.lower()) for p in VALID_MAC_PREFIXES)


def is_valid_cpu(cpu):
    return any(kw in cpu.lower() for kw in ["powerpc", "g3", "g4", "7400", "7450"])


def is_reasonable_timestamp(ts):
    """Validate timestamp is historical but not before vintage era (1984)."""
    formats = [
        "%a %b %d %H:%M:%S %Y",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%d %H:%M:%S",
    ]
    for fmt in formats:
        try:
            parsed = datetime.datetime.strptime(ts.strip(), fmt)
            now = datetime.datetime.now()
            if parsed < now and parsed.year >= 1984:
                return True
        except (ValueError, AttributeError) as e:
            logger.debug("Timestamp format %s failed: %s", fmt, e)
            continue
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


def _detect_genesis_format(data):
    """Detect whether this is a vintage retro genesis or standard blockchain genesis."""
    if not isinstance(data, dict):
        return "unknown"
    # Vintage format has device/mac/cpu fields
    if all(f in data for f in ["device", "mac_address", "fingerprint"]):
        return "vintage"
    # Standard blockchain genesis
    if "genesis_time" in data or "chain_id" in data:
        return "blockchain"
    return "unknown"


def validate_vintage_genesis(data):
    """Validate vintage retro-machine genesis.json format."""
    errors = []

    device = _string_field(data, "device")
    timestamp = _string_field(data, "timestamp")
    message = _string_field(data, "message")
    fingerprint = _string_field(data, "fingerprint")
    mac = _string_field(data, "mac_address")
    cpu = _string_field(data, "cpu")

    if not device:
        errors.append("Missing required field: device")
    if not message:
        errors.append("Missing required field: message")
    if not mac:
        errors.append("Missing required field: mac_address")
    elif not is_valid_mac(mac):
        errors.append(f"MAC address {mac} not in known Apple ranges")

    if not cpu:
        errors.append("Missing required field: cpu")
    elif not is_valid_cpu(cpu):
        errors.append(f"CPU string '{cpu}' not recognized as retro PowerPC")

    if not timestamp:
        errors.append("Missing required field: timestamp")
    elif not is_reasonable_timestamp(timestamp):
        errors.append(f"Timestamp '{timestamp}' is invalid, unparseable, or too modern")

    recalculated = recompute_hash(device, timestamp, message)
    if fingerprint != recalculated:
        errors.append(
            f"Fingerprint hash does not match contents: "
            f"got '{fingerprint[:20]}...', expected '{recalculated[:20]}...'"
        )

    return errors


def validate_blockchain_genesis(data):
    """Validate standard RustChain blockchain genesis.json format."""
    errors = []

    for field in REQUIRED_GENESIS_FIELDS:
        if field not in data:
            errors.append(f"Missing required genesis field: {field}")
        elif not isinstance(data[field], (str, int, float)):
            errors.append(f"Field '{field}' must be a string or number, got {type(data[field]).__name__}")

    # Validate consensus params if present
    consensus = data.get("consensus", {})
    if not isinstance(consensus, dict):
        errors.append("'consensus' must be a JSON object")
    elif consensus:
        for param in ["block", "proof", "signing"]:
            if param not in consensus:
                errors.append(f"Missing consensus parameter: {param}")

    # Validate app state if present
    app_state = data.get("app_state", {})
    if not isinstance(app_state, dict):
        errors.append("'app_state' must be a JSON object")

    return errors


def validate_genesis(path):
    with open(path, 'r') as f:
        data = json.load(f)

    print(f"\nValidating genesis.json: {path}")
    errors = []

    if not isinstance(data, dict):
        errors.append("Genesis file must contain a JSON object")
        data = {}

    fmt = _detect_genesis_format(data)
    print(f"  Detected format: {fmt}")

    if fmt == "vintage":
        errors = validate_vintage_genesis(data)
    elif fmt == "blockchain":
        errors = validate_blockchain_genesis(data)
    else:
        errors.append(
            "Unknown genesis format. File must contain either vintage retro "
            "fields (device, mac_address, fingerprint) or standard blockchain "
            "fields (genesis_time, chain_id, initial_height)"
        )

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
    logging.basicConfig(level=logging.WARNING)
    if len(sys.argv) != 2:
        print("Usage: python validate_genesis.py genesis.json")
        print("")
        print("Validates a genesis.json file for either:")
        print("  1. Vintage retro-machine format (PowerMac G4, etc.)")
        print("  2. Standard RustChain blockchain genesis format")
        sys.exit(1)

    result = validate_genesis(sys.argv[1])
    sys.exit(0 if result else 1)