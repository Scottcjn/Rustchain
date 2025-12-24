def validate_fingerprint_data(fingerprint: dict) -> tuple:
    """
    Server-side validation of miner fingerprint check results.
    Returns: (passed: bool, reason: str)

    Handles BOTH formats:
    - New Python format: {"checks": {"clock_drift": {"passed": true, "data": {...}}}}
    - C miner format: {"checks": {"clock_drift": true}}
    """
    if not fingerprint:
        return True, "no_fingerprint_data_legacy"

    checks = fingerprint.get("checks", {})

    def get_check_status(check_data):
        """Handle both bool and dict formats for check results"""
        if check_data is None:
            return True, {}  # Not provided = OK (legacy)
        if isinstance(check_data, bool):
            return check_data, {}  # C miner simple bool format
        if isinstance(check_data, dict):
            return check_data.get("passed", True), check_data.get("data", {})
        return True, {}  # Unknown format = OK (permissive)

    # 1. Anti-emulation check (CRITICAL)
    anti_emu_passed, anti_emu_data = get_check_status(checks.get("anti_emulation"))
    if anti_emu_passed == False:
        vm_indicators = anti_emu_data.get("vm_indicators", [])
        return False, f"vm_detected:{vm_indicators}"

    # 2. Clock drift - reject synthetic timing
    clock_passed, clock_data = get_check_status(checks.get("clock_drift"))
    if clock_passed == False:
        fail_reason = clock_data.get("fail_reason", "unknown")
        return False, f"clock_drift_failed:{fail_reason}"

    cv = clock_data.get("cv", 0)
    if cv < 0.0001 and cv != 0:
        return False, "timing_too_uniform"

    # 3. ROM fingerprint (retro platforms)
    rom_passed, rom_data = get_check_status(checks.get("rom_fingerprint"))
    if rom_passed == False:
        fail_reason = rom_data.get("fail_reason", "unknown")
        return False, f"rom_check_failed:{fail_reason}"

    if rom_data.get("emulator_detected"):
        details = rom_data.get("detection_details", [])
        return False, f"known_emulator_rom:{details}"

    # 4. Check all_passed flag
    if fingerprint.get("all_passed") == False:
        failed_checks = []
        for k, v in checks.items():
            passed, _ = get_check_status(v)
            if not passed:
                failed_checks.append(k)
        return False, f"checks_failed:{failed_checks}"

    return True, "valid"
