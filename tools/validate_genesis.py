# RustChain PoA Validator Script (Python)
# Validates genesis.json files from retro machines like PowerMac G4
#
# Validation checks:
# 1. MAC address matches known Apple vintage hardware prefixes
# 2. CPU string indicates PowerPC-era processor (G3/G4)
# 3. Timestamp is in valid format and predates current date (>= 1984)
# 4. SHA1 fingerprint hash matches recomputed value from contents

import json
import base64
import hashlib
import datetime
import re

# Known Apple MAC address OUI prefixes for vintage hardware:
# - 00:03:93: Apple PowerMac G4 (2000-2003)
# - 00:0a:27: Apple PowerMac G5 (2003-2005)
# - 00:05:02: Apple iBook/PowerBook G4
# - 00:0d:93: Apple eMac/PowerMac G4
VALID_MAC_PREFIXES = ["00:03:93", "00:0a:27", "00:05:02", "00:0d:93"]


def is_valid_mac(mac: str) -> bool:
    """Check if MAC address matches known Apple vintage hardware prefixes.
    
    Args:
        mac: MAC address string (e.g., "00:03:93:xx:xx:xx")
        
    Returns:
        True if MAC prefix matches known Apple OUI, False otherwise
    """
    prefix = mac.lower()[0:8]
    return any(prefix.startswith(p.lower()) for p in VALID_MAC_PREFIXES)


def is_valid_cpu(cpu: str) -> bool:
    """Check if CPU string indicates a retro PowerPC processor.
    
    Looks for keywords associated with PowerPC-era Apple hardware:
    - PowerPC architecture
    - G3/G4 processor generations
    - 7400/7450 processor models (G4 variants)
    
    Args:
        cpu: CPU description string
        
    Returns:
        True if CPU matches retro PowerPC patterns, False otherwise
    """
    return any(kw in cpu.lower() for kw in ["powerpc", "g3", "g4", "7400", "7450"])


def is_reasonable_timestamp(ts: str) -> bool:
    """Validate timestamp format and ensure it's not from the future.
    
    Expected format: "Day Mon DD HH:MM:SS YYYY" (e.g., "Fri Jan 15 14:30:00 2021")
    
    Validation rules:
    - Must parse successfully in expected format
    - Must be before current time (not future-dated)
    - Must be year 1984 or later (Macintosh era)
    
    Args:
        ts: Timestamp string to validate
        
    Returns:
        True if timestamp is valid and reasonable, False otherwise
    """
    try:
        parsed = datetime.datetime.strptime(ts.strip(), "%a %b %d %H:%M:%S %Y")
        now = datetime.datetime.now()
        if parsed < now and parsed.year >= 1984:
            return True
    except Exception:
        pass
    return False

def recompute_hash(device: str, timestamp: str, message: str) -> str:
    """Recompute the SHA1 fingerprint hash for genesis validation.
    
    The hash is computed as:
    SHA1(device|timestamp|message) encoded in base64
    
    The pipe-delimited format ensures consistent hashing across platforms.
    
    Args:
        device: Device identifier string
        timestamp: Timestamp string from genesis
        message: Message content string
        
    Returns:
        Base64-encoded SHA1 hash of the concatenated fields
    """
    joined = f"{device}|{timestamp}|{message}"
    sha1 = hashlib.sha1(joined.encode('utf-8')).digest()
    return base64.b64encode(sha1).decode('utf-8')


def validate_genesis(path: str) -> bool:
    """Validate a genesis.json file against all authenticity checks.
    
    Performs 4 validation checks:
    1. MAC address matches Apple vintage hardware
    2. CPU string indicates PowerPC-era processor
    3. Timestamp is valid format and not future-dated
    4. Fingerprint hash matches recomputed value
    
    Args:
        path: Path to genesis.json file
        
    Returns:
        True if all checks pass, False if any validation fails
    """
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
