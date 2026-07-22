import platform
import subprocess
import os
import hashlib
from typing import Dict, Any

def get_system_info() -> Dict[str, Any]:
    """Get basic system information."""
    return {
        'system': platform.system(),
        'node': platform.node(),
        'release': platform.release(),
        'version': platform.version(),
        'machine': platform.machine(),
        'processor': platform.processor()
    }

def get_cpu_info() -> Dict[str, Any]:
    """Get detailed CPU information."""
    cpu_info = {}
    try:
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if ':' in line:
                    key, value = line.strip().split(':', 1)
                    cpu_info[key.strip()] = value.strip()
    except FileNotFoundError:
        pass
    return cpu_info

def get_sparc_fingerprint() -> Dict[str, Any]:
    """Get fingerprint for SPARC architecture."""
    fingerprint = get_system_info()
    fingerprint.update(get_cpu_info())

    # SPARC-specific checks
    try:
        result = subprocess.run(['isainfo', '-v'], capture_output=True, text=True)
        fingerprint['isa_info'] = result.stdout.strip()
    except FileNotFoundError:
        pass

    return fingerprint

def get_mips_fingerprint() -> Dict[str, Any]:
    """Get fingerprint for MIPS architecture."""
    fingerprint = get_system_info()
    fingerprint.update(get_cpu_info())

    # MIPS-specific checks
    try:
        result = subprocess.run(['cat', '/proc/cpuinfo'], capture_output=True, text=True)
        fingerprint['mips_info'] = result.stdout.strip()
    except FileNotFoundError:
        pass

    return fingerprint

def get_riscv_fingerprint() -> Dict[str, Any]:
    """Get fingerprint for RISC-V architecture."""
    fingerprint = get_system_info()
    fingerprint.update(get_cpu_info())

    # RISC-V-specific checks
    try:
        result = subprocess.run(['cat', '/proc/cpuinfo'], capture_output=True, text=True)
        fingerprint['riscv_info'] = result.stdout.strip()
    except FileNotFoundError:
        pass

    return fingerprint

def get_arm_sbc_fingerprint() -> Dict[str, Any]:
    """Get fingerprint for ARM SBC architecture."""
    fingerprint = get_system_info()
    fingerprint.update(get_cpu_info())

    # ARM SBC-specific checks
    try:
        result = subprocess.run(['cat', '/proc/cpuinfo'], capture_output=True, text=True)
        fingerprint['arm_info'] = result.stdout.strip()
    except FileNotFoundError:
        pass

    return fingerprint

def get_old_x86_fingerprint() -> Dict[str, Any]:
    """Get fingerprint for old x86 architecture."""
    fingerprint = get_system_info()
    fingerprint.update(get_cpu_info())

    # Old x86-specific checks
    try:
        result = subprocess.run(['cat', '/proc/cpuinfo'], capture_output=True, text=True)
        fingerprint['x86_info'] = result.stdout.strip()
    except FileNotFoundError:
        pass

    return fingerprint

def get_fingerprint() -> Dict[str, Any]:
    """Get hardware fingerprint based on architecture."""
    machine = platform.machine().lower()

    if 'sparc' in machine:
        return get_sparc_fingerprint()
    elif 'mips' in machine:
        return get_mips_fingerprint()
    elif 'riscv' in machine or 'risc-v' in machine:
        return get_riscv_fingerprint()
    elif 'arm' in machine or 'aarch64' in machine:
        return get_arm_sbc_fingerprint()
    elif 'x86' in machine or 'i386' in machine or 'i686' in machine:
        return get_old_x86_fingerprint()
    else:
        return get_system_info()

def generate_fingerprint_hash(fingerprint: Dict[str, Any]) -> str:
    """Generate a hash of the fingerprint data."""
    fingerprint_str = str(fingerprint).encode('utf-8')
    return hashlib.sha256(fingerprint_str).hexdigest()

if __name__ == '__main__':
    fingerprint = get_fingerprint()
    print("Hardware Fingerprint:")
    print(fingerprint)
    print("\nFingerprint Hash:")
    print(generate_fingerprint_hash(fingerprint))