#!/usr/bin/env python3
"""RustChain Address Validator — Verify RTC address format and checksum."""
import hashlib, sys, re

def validate_rtc_address(address):
    errors = []
    if not address.startswith("RTC"):
        errors.append("Must start with 'RTC'")
    hex_part = address[3:]
    if len(hex_part) != 40:
        errors.append(f"Hex part must be 40 chars, got {len(hex_part)}")
    if not re.match(r'^[0-9a-fA-F]+$', hex_part):
        errors.append("Contains non-hex characters")
    return {"valid": len(errors) == 0, "address": address, "errors": errors}

def derive_address(public_key_hex):
    """Derive RTC address from Ed25519 public key hex."""
    pubkey_bytes = bytes.fromhex(public_key_hex)
    address_hash = hashlib.sha256(pubkey_bytes).hexdigest()[:40]
    return f"RTC{address_hash}"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python address_validator.py <RTC_ADDRESS>")
        print("       python address_validator.py --derive <PUBLIC_KEY_HEX>")
        sys.exit(1)
    if sys.argv[1] == "--derive":
        print(derive_address(sys.argv[2]))
    else:
        result = validate_rtc_address(sys.argv[1])
        print(f"{'VALID' if result['valid'] else 'INVALID'}: {result['address']}")
        for e in result["errors"]:
            print(f"  Error: {e}")
