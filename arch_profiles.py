# SPDX-License-Identifier: MIT

import json
from typing import Dict, List, Tuple, Any

# Architecture fingerprint profiles for hardware validation
ARCH_PROFILES = {
    'g4': {
        'cpu_family': 'PowerPC',
        'model_names': ['PowerPC G4', 'PowerPC 74xx', 'PowerPC 7400', 'PowerPC 7450', 'PowerPC 7455'],
        'cache_l1_data': [32768, 65536],  # 32KB-64KB typical
        'cache_l1_instruction': [32768, 65536],
        'cache_l2': [256000, 2097152],  # 256KB-2MB range
        'cache_l3': [0, 0],  # No L3 on G4
        'simd_features': ['altivec'],
        'endianness': 'big',
        'word_size': 32,
        'timing_ranges': {
            'cpu_benchmark': (800, 2500),  # Relative performance
            'memory_latency': (120, 200),  # nanoseconds
            'cache_miss_penalty': (50, 80)
        },
        'thermal_patterns': {
            'idle_temp': (35, 45),
            'load_temp': (55, 70),
            'thermal_throttle': False
        },
        'vintage_multiplier': 8.5,
        'min_year': 1999,
        'max_year': 2004
    },

    'g5': {
        'cpu_family': 'PowerPC',
        'model_names': ['PowerPC G5', 'PowerPC 970', 'PowerPC 970FX', 'PowerPC 970MP'],
        'cache_l1_data': [32768, 65536],
        'cache_l1_instruction': [65536, 65536],
        'cache_l2': [524288, 1048576],  # 512KB-1MB
        'cache_l3': [0, 0],
        'simd_features': ['altivec'],
        'endianness': 'big',
        'word_size': 64,
        'timing_ranges': {
            'cpu_benchmark': (2000, 4500),
            'memory_latency': (100, 160),
            'cache_miss_penalty': (40, 65)
        },
        'thermal_patterns': {
            'idle_temp': (40, 50),
            'load_temp': (65, 85),
            'thermal_throttle': True
        },
        'vintage_multiplier': 7.2,
        'min_year': 2003,
        'max_year': 2006
    },

    'g3': {
        'cpu_family': 'PowerPC',
        'model_names': ['PowerPC G3', 'PowerPC 750', 'PowerPC 740'],
        'cache_l1_data': [32768, 32768],
        'cache_l1_instruction': [32768, 32768],
        'cache_l2': [1048576, 1048576],  # 1MB backside cache
        'cache_l3': [0, 0],
        'simd_features': [],
        'endianness': 'big',
        'word_size': 32,
        'timing_ranges': {
            'cpu_benchmark': (400, 1200),
            'memory_latency': (150, 250),
            'cache_miss_penalty': (80, 120)
        },
        'thermal_patterns': {
            'idle_temp': (30, 40),
            'load_temp': (45, 60),
            'thermal_throttle': False
        },
        'vintage_multiplier': 9.8,
        'min_year': 1997,
        'max_year': 2003
    },

    'modern_x86': {
        'cpu_family': 'x86_64',
        'model_names': ['Intel Core', 'AMD Ryzen', 'Intel Xeon', 'AMD EPYC'],
        'cache_l1_data': [32768, 65536],
        'cache_l1_instruction': [32768, 65536],
        'cache_l2': [262144, 1048576],  # 256KB-1MB
        'cache_l3': [6291456, 67108864],  # 6MB-64MB
        'simd_features': ['sse', 'sse2', 'sse3', 'ssse3', 'sse4_1', 'sse4_2', 'avx', 'avx2', 'avx512'],
        'endianness': 'little',
        'word_size': 64,
        'timing_ranges': {
            'cpu_benchmark': (8000, 35000),
            'memory_latency': (60, 90),
            'cache_miss_penalty': (15, 30)
        },
        'thermal_patterns': {
            'idle_temp': (25, 35),
            'load_temp': (45, 75),
            'thermal_throttle': True
        },
        'vintage_multiplier': 1.0,
        'min_year': 2010,
        'max_year': 2024
    },

    'apple_silicon': {
        'cpu_family': 'ARM64',
        'model_names': ['Apple M1', 'Apple M2', 'Apple M3'],
        'cache_l1_data': [65536, 131072],
        'cache_l1_instruction': [131072, 131072],
        'cache_l2': [4194304, 16777216],  # 4MB-16MB
        'cache_l3': [0, 0],  # Unified memory architecture
        'simd_features': ['neon', 'fp16', 'bf16'],
        'endianness': 'little',
        'word_size': 64,
        'timing_ranges': {
            'cpu_benchmark': (12000, 28000),
            'memory_latency': (70, 100),
            'cache_miss_penalty': (20, 35)
        },
        'thermal_patterns': {
            'idle_temp': (28, 38),
            'load_temp': (40, 65),
            'thermal_throttle': True
        },
        'vintage_multiplier': 0.8,
        'min_year': 2020,
        'max_year': 2024
    },

    'retro_x86': {
        'cpu_family': 'x86',
        'model_names': ['Intel Pentium', 'Intel 486', 'AMD K6', 'Intel Pentium II', 'Intel Pentium III'],
        'cache_l1_data': [8192, 32768],
        'cache_l1_instruction': [8192, 32768],
        'cache_l2': [0, 524288],  # Some had no L2, others up to 512KB
        'cache_l3': [0, 0],
        'simd_features': ['mmx', 'sse'],
        'endianness': 'little',
        'word_size': 32,
        'timing_ranges': {
            'cpu_benchmark': (50, 800),
            'memory_latency': (200, 400),
            'cache_miss_penalty': (100, 200)
        },
        'thermal_patterns': {
            'idle_temp': (35, 50),
            'load_temp': (50, 75),
            'thermal_throttle': False
        },
        'vintage_multiplier': 12.5,
        'min_year': 1990,
        'max_year': 2005
    }
}

VM_SIGNATURES = {
    'virtualbox': {
        'dmi_patterns': ['VirtualBox', 'Oracle Corporation', 'innotek GmbH'],
        'mac_oui': ['08:00:27'],
        'pci_devices': ['80ee:beef', '80ee:cafe'],
        'cpu_flags_missing': ['hypervisor'],
        'timing_anomalies': True
    },
    'vmware': {
        'dmi_patterns': ['VMware', 'VMware, Inc.'],
        'mac_oui': ['00:50:56', '00:0c:29', '00:05:69'],
        'pci_devices': ['15ad:0405', '15ad:0790'],
        'cpu_flags_missing': ['hypervisor'],
        'timing_anomalies': True
    },
    'qemu_kvm': {
        'dmi_patterns': ['QEMU', 'Bochs', 'SeaBIOS'],
        'mac_oui': ['52:54:00'],
        'pci_devices': ['1af4:1000', '1b36:0001'],
        'cpu_flags_missing': ['hypervisor'],
        'timing_anomalies': True
    },
    'parallels': {
        'dmi_patterns': ['Parallels', 'Parallels Software'],
        'mac_oui': ['00:1c:42'],
        'pci_devices': ['1ab8:4000'],
        'cpu_flags_missing': ['hypervisor'],
        'timing_anomalies': True
    }
}

def get_arch_profile(arch_type: str) -> Dict[str, Any]:
    """Get architecture profile by type."""
    return ARCH_PROFILES.get(arch_type, {})

def get_vintage_multiplier(arch_type: str) -> float:
    """Get mining multiplier for architecture type."""
    profile = get_arch_profile(arch_type)
    return profile.get('vintage_multiplier', 1.0)

def validate_cache_sizes(fingerprint: Dict[str, Any], arch_type: str) -> bool:
    """Validate cache sizes against architecture profile."""
    profile = get_arch_profile(arch_type)
    if not profile:
        return False

    cache_info = fingerprint.get('hardware_info', {}).get('cache_info', {})

    # Check L1 data cache
    l1d = cache_info.get('l1_data_cache', 0)
    if l1d and not (profile['cache_l1_data'][0] <= l1d <= profile['cache_l1_data'][1]):
        return False

    # Check L1 instruction cache
    l1i = cache_info.get('l1_instruction_cache', 0)
    if l1i and not (profile['cache_l1_instruction'][0] <= l1i <= profile['cache_l1_instruction'][1]):
        return False

    # Check L2 cache
    l2 = cache_info.get('l2_cache', 0)
    if l2 and not (profile['cache_l2'][0] <= l2 <= profile['cache_l2'][1]):
        return False

    return True

def validate_simd_features(fingerprint: Dict[str, Any], arch_type: str) -> bool:
    """Validate SIMD capabilities against architecture profile."""
    profile = get_arch_profile(arch_type)
    if not profile:
        return False

    cpu_features = fingerprint.get('hardware_info', {}).get('cpu_features', [])
    expected_simd = profile.get('simd_features', [])

    if not expected_simd:  # No SIMD expected
        return True

    # At least one expected SIMD feature should be present
    return any(feature in cpu_features for feature in expected_simd)

def validate_timing_characteristics(fingerprint: Dict[str, Any], arch_type: str) -> bool:
    """Validate timing patterns against architecture profile."""
    profile = get_arch_profile(arch_type)
    if not profile:
        return False

    timing_info = fingerprint.get('timing_info', {})
    expected_ranges = profile.get('timing_ranges', {})

    for metric, expected_range in expected_ranges.items():
        actual_value = timing_info.get(metric)
        if actual_value and not (expected_range[0] <= actual_value <= expected_range[1]):
            return False

    return True

def detect_vm_signatures(fingerprint: Dict[str, Any]) -> List[str]:
    """Detect virtualization signatures in fingerprint."""
    detected_vms = []

    system_info = fingerprint.get('system_info', {})
    dmi_info = system_info.get('dmi_info', {})
    network_info = fingerprint.get('network_info', {})

    for vm_type, signatures in VM_SIGNATURES.items():
        # Check DMI patterns
        for pattern in signatures['dmi_patterns']:
            if any(pattern.lower() in str(value).lower()
                   for value in dmi_info.values() if value):
                detected_vms.append(vm_type)
                break

        # Check MAC OUI patterns
        mac_address = network_info.get('mac_address', '')
        if any(mac_address.upper().startswith(oui)
               for oui in signatures['mac_oui']):
            detected_vms.append(vm_type)

    return list(set(detected_vms))

def calculate_authenticity_score(fingerprint: Dict[str, Any], claimed_arch: str) -> float:
    """Calculate hardware authenticity score (0.0 to 1.0)."""
    score = 1.0

    # Check for VM signatures (major penalty)
    vm_signatures = detect_vm_signatures(fingerprint)
    if vm_signatures:
        score *= 0.1

    # Validate architecture-specific characteristics
    if not validate_cache_sizes(fingerprint, claimed_arch):
        score *= 0.7

    if not validate_simd_features(fingerprint, claimed_arch):
        score *= 0.8

    if not validate_timing_characteristics(fingerprint, claimed_arch):
        score *= 0.6

    # Check for hypervisor flag (strong VM indicator)
    cpu_features = fingerprint.get('hardware_info', {}).get('cpu_features', [])
    if 'hypervisor' in cpu_features:
        score *= 0.2

    return max(0.0, min(1.0, score))

def get_supported_architectures() -> List[str]:
    """Get list of supported architecture types."""
    return list(ARCH_PROFILES.keys())

def export_profiles_json() -> str:
    """Export architecture profiles as JSON string."""
    return json.dumps(ARCH_PROFILES, indent=2)
