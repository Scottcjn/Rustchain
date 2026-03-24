import json

def validate_amiga_dump(attn_flags, rom_checksum):
    with open("tools/rom/checksums.json") as f:
        known_roms = json.load(f)

    verdict = {
        "rom_match": False,
        "rom_version": None,
        "attn_flags_ok": True,
        "score": 1000,
        "penalties": {}
    }

    # Check ROM match
    for rom_name, info in known_roms.items():
        if rom_checksum == info["checksum"]:
            verdict["rom_match"] = True
            verdict["rom_version"] = info["version"]
            break

    if not verdict["rom_match"]:
        verdict["score"] -= 400
        verdict["penalties"]["rom_checksum_mismatch"] = -400

    # Check AttnFlags validity
    if attn_flags == 0:
        verdict["score"] -= 300
        verdict["attn_flags_ok"] = False
        verdict["penalties"]["attn_flags_zero"] = -300

    # Minimum score floor
    verdict["score"] = max(verdict["score"], 10)
    return verdict

# Example usage
if __name__ == "__main__":
    # Example values
    rom_checksum = 8589954
    attn_flags = 0x00000000

    result = validate_amiga_dump(attn_flags, rom_checksum)
    print(json.dumps(result, indent=2))
