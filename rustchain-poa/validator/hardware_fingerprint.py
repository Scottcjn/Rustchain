import platform, subprocess, re, json, hashlib, os

def detect_unique_hardware_signature():
    """
    Generate a cryptographic fingerprint of the physical hardware.

    This function is critical for RustChain's Proof-of-Antiquity consensus because:
    1. It prevents Sybil attacks by binding one wallet to one physical machine
    2. It detects virtual machines (which receive 1 billionth of normal rewards)
    3. It enables antiquity multipliers based on authentic hardware age

    The hardware signature must be:
    - Stable across reboots (same hardware = same signature)
    - Unique per physical device (different hardware = different signature)
    - Difficult to spoof or emulate (real silicon has unique characteristics)

    Returns:
        tuple: (hardware_signature: str, unique_markers: dict)
            - hardware_signature: SHA256 hash of all collected markers
            - unique_markers: Raw hardware identifiers used to generate signature
    """
    unique_markers = {}

    try:
        # Platform-specific hardware identification
        # We use different tools per OS because hardware access APIs vary significantly

        if platform.system() == 'Darwin':
            # macOS: Use system_profiler to get Hardware UUID
            # This UUID is burned into the Mac's logic board at manufacture time
            # and persists across OS reinstalls, making it ideal for hardware binding
            output = subprocess.check_output(['system_profiler', 'SPHardwareDataType']).decode()
            hw_uuid = re.search(r'Hardware UUID: (.*)', output)
            if hw_uuid:
                unique_markers['hardware_uuid'] = hw_uuid.group(1).strip()

        elif platform.system() == 'Windows':
            # Windows: Combine motherboard serial + CPU ID
            # We use both because:
            # - Motherboard serial alone can be spoofed in VMs
            # - CPU ID alone changes if the CPU is replaced
            # - Together they create a strong hardware binding
            mb_serial = subprocess.check_output(['wmic', 'baseboard', 'get', 'serialnumber']).decode().strip().split('\n')[1].strip()
            cpu_id = subprocess.check_output(['wmic', 'cpu', 'get', 'processorid']).decode().strip().split('\n')[1].strip()
            unique_markers['mb_serial'] = mb_serial
            unique_markers['cpu_id'] = cpu_id

        elif platform.system() == 'Linux':
            # Linux: Use dmidecode to read DMI/SMBIOS data
            # We collect multiple markers because:
            # - Some VMs fake individual DMI fields but rarely fake all of them
            # - Different hardware vendors populate different fields
            # - Multiple markers increase fingerprint uniqueness
            for tag in ['system-serial-number', 'bios-version', 'baseboard-product-name']:
                try:
                    out = subprocess.check_output(['dmidecode', '-s', tag]).decode().strip()
                    unique_markers[tag] = out
                except:
                    # dmidecode requires root on some systems, or the field may not exist
                    # We continue collecting other markers rather than failing completely
                    continue

    except Exception as e:
        # If hardware detection fails, we record the error but don't crash
        # This allows the node to continue operating (though attestation will fail)
        # The error will be logged and the miner can troubleshoot
        unique_markers['error'] = str(e)

    # Generate deterministic signature from collected markers
    # We use JSON with sort_keys=True to ensure consistent ordering across runs
    # This is critical because the same hardware must always produce the same signature
    sig_data = json.dumps(unique_markers, sort_keys=True).encode()

    # SHA256 provides:
    # - Collision resistance (two different machines won't have the same signature)
    # - One-way function (can't reverse engineer hardware from signature)
    # - Fixed length output (256 bits regardless of input size)
    hardware_signature = hashlib.sha256(sig_data).hexdigest()

    return hardware_signature, unique_markers
