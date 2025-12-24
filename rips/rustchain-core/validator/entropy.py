"""
RustChain Entropy-Based Validator Fingerprinting (RIP-0007)
============================================================

Multi-source entropy fingerprint system for validator identification,
anti-emulation verification, and cumulative reputation weighting.

Philosophy: "It's cheaper to buy a $50 486 than to emulate one"

Entropy Layers:
1. Hardware (60%): CPU timing, cache, memory SPD, thermal, BIOS
2. Software (25%): Kernel boot, MAC, SMBIOS, disk serials
3. Temporal (15%): Uptime continuity, drift history, challenges
"""

import hashlib
import time
import struct
import platform
import subprocess
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from pathlib import Path


# =============================================================================
# Constants
# =============================================================================

# Entropy layer weights (must sum to 1.0)
HARDWARE_WEIGHT = 0.60
SOFTWARE_WEIGHT = 0.25
TEMPORAL_WEIGHT = 0.15

# Individual source weights within hardware layer
HW_CPU_TIMING_WEIGHT = 0.25
HW_CACHE_WEIGHT = 0.20
HW_MEMORY_WEIGHT = 0.15
HW_THERMAL_WEIGHT = 0.15
HW_BIOS_WEIGHT = 0.15
HW_TOPOLOGY_WEIGHT = 0.10

# Drift thresholds
MAX_DRIFT_ALLOWED = 10  # Maximum drift events before penalty
DRIFT_THRESHOLD_PERCENT = 5.0  # % change that counts as drift

# Challenge timeouts
CHALLENGE_TIMEOUT_MS = 5000


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class EntropySource:
    """Individual entropy source measurement"""
    name: str
    hash: str
    raw_value: Any
    confidence: float  # 0.0 - 1.0
    timestamp: int


@dataclass
class EntropyProfile:
    """Complete entropy profile for a node"""
    # Hardware layer
    cpu_fingerprint: str = ""
    cache_fingerprint: str = ""
    memory_fingerprint: str = ""
    thermal_fingerprint: str = ""
    bios_fingerprint: str = ""
    topology_fingerprint: str = ""

    # Software layer
    kernel_fingerprint: str = ""
    mac_fingerprint: str = ""
    smbios_fingerprint: str = ""
    disk_fingerprint: str = ""

    # Temporal layer
    uptime_seconds: int = 0
    collection_timestamp: int = 0

    # Computed values
    validator_id: str = ""
    combined_hash: str = ""
    confidence_score: float = 0.0

    def __post_init__(self):
        if not self.validator_id:
            self.validator_id = self._derive_validator_id()
        if not self.combined_hash:
            self.combined_hash = self._compute_combined_hash()

    def _derive_validator_id(self) -> str:
        """Derive unique validator ID from entropy profile"""
        combined = (
            self.cpu_fingerprint +
            self.memory_fingerprint +
            self.bios_fingerprint +
            self.topology_fingerprint +
            self.mac_fingerprint +
            self.disk_fingerprint +
            self.kernel_fingerprint
        )
        return hashlib.sha256(combined.encode()).hexdigest()

    def _compute_combined_hash(self) -> str:
        """Compute combined entropy hash"""
        all_hashes = [
            self.cpu_fingerprint,
            self.cache_fingerprint,
            self.memory_fingerprint,
            self.thermal_fingerprint,
            self.bios_fingerprint,
            self.topology_fingerprint,
            self.kernel_fingerprint,
            self.mac_fingerprint,
            self.smbios_fingerprint,
            self.disk_fingerprint,
        ]
        combined = ''.join(h for h in all_hashes if h)
        return hashlib.sha256(combined.encode()).hexdigest()


@dataclass
class DriftEvent:
    """Record of entropy drift"""
    timestamp: int
    source: str
    old_hash: str
    new_hash: str
    drift_percent: float


@dataclass
class ChallengeResult:
    """Result of a challenge-response verification"""
    challenge_type: str
    nonce: bytes
    response: bytes
    timing_ms: float
    valid: bool
    details: str = ""


# =============================================================================
# Hardware Entropy Collection
# =============================================================================

class HardwareEntropyCollector:
    """
    Collects hardware-level entropy for fingerprinting.

    Security: Real hardware has measurable, consistent characteristics.
    Emulators fail to perfectly replicate timing, cache, and thermal behavior.
    """

    @staticmethod
    def fingerprint_cpu() -> EntropySource:
        """
        Collect CPU-specific entropy.

        Measures:
        - Instruction timing variations
        - CPUID responses
        - Cache line behavior
        """
        data = {}

        # Get CPU info
        try:
            if platform.system() == "Linux":
                with open("/proc/cpuinfo", "r") as f:
                    cpuinfo = f.read()
                data["cpuinfo"] = cpuinfo[:2000]  # First 2KB
            else:
                data["platform_processor"] = platform.processor()
        except:
            data["platform_processor"] = platform.processor()

        # Measure instruction timing (simplified - real impl would use rdtsc)
        timing_samples = []
        for _ in range(100):
            start = time.perf_counter_ns()
            # Simple operations
            x = 0
            for i in range(1000):
                x += i * i
            elapsed = time.perf_counter_ns() - start
            timing_samples.append(elapsed)

        data["timing_mean"] = sum(timing_samples) / len(timing_samples)
        data["timing_variance"] = sum((t - data["timing_mean"])**2 for t in timing_samples) / len(timing_samples)

        # Hash the data
        fingerprint = hashlib.sha256(str(data).encode()).hexdigest()

        return EntropySource(
            name="cpu",
            hash=fingerprint,
            raw_value=data,
            confidence=0.85,
            timestamp=int(time.time()),
        )

    @staticmethod
    def fingerprint_cache() -> EntropySource:
        """
        Measure cache behavior patterns.

        Real hardware has specific L1/L2 cache timing characteristics
        that are extremely difficult to emulate accurately.
        """
        data = {}

        # Allocate memory and measure access patterns
        try:
            import array
            buffer_size = 1024 * 1024  # 1MB
            buffer = array.array('i', [0] * (buffer_size // 4))

            # Sequential access timing
            start = time.perf_counter_ns()
            for i in range(0, len(buffer), 64):  # Cache line stride
                _ = buffer[i]
            seq_time = time.perf_counter_ns() - start
            data["sequential_access_ns"] = seq_time

            # Random access timing (should be slower due to cache misses)
            import random
            indices = list(range(0, len(buffer), 64))
            random.shuffle(indices)
            start = time.perf_counter_ns()
            for i in indices[:1000]:
                _ = buffer[i]
            rand_time = time.perf_counter_ns() - start
            data["random_access_ns"] = rand_time

            # Cache efficiency ratio
            data["cache_ratio"] = seq_time / max(1, rand_time)

        except Exception as e:
            data["error"] = str(e)

        fingerprint = hashlib.sha256(str(data).encode()).hexdigest()

        return EntropySource(
            name="cache",
            hash=fingerprint,
            raw_value=data,
            confidence=0.75,
            timestamp=int(time.time()),
        )

    @staticmethod
    def fingerprint_memory() -> EntropySource:
        """
        Collect memory timing and SPD data.

        SPD (Serial Presence Detect) contains timing parameters
        programmed into memory modules at manufacture.
        """
        data = {}

        # Try to read memory info
        try:
            if platform.system() == "Linux":
                # Memory info
                with open("/proc/meminfo", "r") as f:
                    data["meminfo"] = f.read()[:1000]

                # Try DMI decode for memory details (requires root)
                try:
                    result = subprocess.run(
                        ["dmidecode", "-t", "memory"],
                        capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        data["dmi_memory"] = result.stdout[:2000]
                except:
                    pass

            elif platform.system() == "Darwin":  # macOS
                try:
                    result = subprocess.run(
                        ["system_profiler", "SPMemoryDataType"],
                        capture_output=True, text=True, timeout=10
                    )
                    data["system_profiler"] = result.stdout[:2000]
                except:
                    pass

        except Exception as e:
            data["error"] = str(e)

        data["total_memory"] = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') if hasattr(os, 'sysconf') else 0

        fingerprint = hashlib.sha256(str(data).encode()).hexdigest()

        return EntropySource(
            name="memory",
            hash=fingerprint,
            raw_value=data,
            confidence=0.70,
            timestamp=int(time.time()),
        )

    @staticmethod
    def fingerprint_thermal() -> EntropySource:
        """
        Collect thermal signature data.

        Real hardware has specific thermal response patterns.
        Emulators cannot physically generate heat.
        """
        data = {}

        try:
            if platform.system() == "Linux":
                # Read thermal zones
                thermal_path = Path("/sys/class/thermal")
                if thermal_path.exists():
                    for zone in thermal_path.glob("thermal_zone*"):
                        try:
                            temp_file = zone / "temp"
                            if temp_file.exists():
                                with open(temp_file, "r") as f:
                                    temp = int(f.read().strip()) / 1000.0
                                    data[zone.name] = temp
                        except:
                            pass

                # CPU frequency (varies with thermal throttling)
                cpufreq_path = Path("/sys/devices/system/cpu/cpu0/cpufreq")
                if cpufreq_path.exists():
                    for freq_file in ["scaling_cur_freq", "cpuinfo_max_freq"]:
                        fpath = cpufreq_path / freq_file
                        if fpath.exists():
                            try:
                                with open(fpath, "r") as f:
                                    data[freq_file] = int(f.read().strip())
                            except:
                                pass

            elif platform.system() == "Darwin":
                # macOS - try powermetrics or SMC
                try:
                    result = subprocess.run(
                        ["sysctl", "-a"],
                        capture_output=True, text=True, timeout=5
                    )
                    for line in result.stdout.split('\n'):
                        if 'temperature' in line.lower() or 'thermal' in line.lower():
                            data[line.split(':')[0].strip()] = line.split(':')[1].strip() if ':' in line else ''
                except:
                    pass

        except Exception as e:
            data["error"] = str(e)

        # Include timestamp for temporal entropy
        data["collection_time"] = time.time()

        fingerprint = hashlib.sha256(str(data).encode()).hexdigest()

        return EntropySource(
            name="thermal",
            hash=fingerprint,
            raw_value=data,
            confidence=0.60 if data else 0.20,
            timestamp=int(time.time()),
        )

    @staticmethod
    def fingerprint_bios() -> EntropySource:
        """
        Collect BIOS/UEFI/OpenFirmware entropy.

        Firmware timestamps and configuration are unique per machine.
        """
        data = {}

        try:
            if platform.system() == "Linux":
                # DMI data
                dmi_path = Path("/sys/class/dmi/id")
                if dmi_path.exists():
                    for field in ["bios_vendor", "bios_version", "bios_date",
                                  "board_name", "board_vendor", "board_serial",
                                  "sys_vendor", "product_name", "product_serial"]:
                        fpath = dmi_path / field
                        if fpath.exists():
                            try:
                                with open(fpath, "r") as f:
                                    data[field] = f.read().strip()
                            except:
                                pass

            elif platform.system() == "Darwin":
                # macOS - OpenFirmware/NVRAM
                try:
                    result = subprocess.run(
                        ["system_profiler", "SPHardwareDataType"],
                        capture_output=True, text=True, timeout=10
                    )
                    data["hardware_profile"] = result.stdout[:2000]
                except:
                    pass

                # NVRAM
                try:
                    result = subprocess.run(
                        ["nvram", "-p"],
                        capture_output=True, text=True, timeout=5
                    )
                    data["nvram"] = result.stdout[:1000]
                except:
                    pass

        except Exception as e:
            data["error"] = str(e)

        fingerprint = hashlib.sha256(str(data).encode()).hexdigest()

        return EntropySource(
            name="bios",
            hash=fingerprint,
            raw_value=data,
            confidence=0.80 if data else 0.30,
            timestamp=int(time.time()),
        )

    @staticmethod
    def fingerprint_topology() -> EntropySource:
        """
        Collect hardware topology (PCIe, USB, IRQ).

        Physical device configuration is unique to each machine.
        """
        data = {}

        try:
            if platform.system() == "Linux":
                # PCI devices
                try:
                    result = subprocess.run(
                        ["lspci", "-nn"],
                        capture_output=True, text=True, timeout=10
                    )
                    if result.returncode == 0:
                        data["pci_devices"] = result.stdout[:4000]
                except:
                    pass

                # USB devices
                try:
                    result = subprocess.run(
                        ["lsusb"],
                        capture_output=True, text=True, timeout=10
                    )
                    if result.returncode == 0:
                        data["usb_devices"] = result.stdout[:2000]
                except:
                    pass

                # Block devices
                try:
                    result = subprocess.run(
                        ["lsblk", "-o", "NAME,SIZE,MODEL,SERIAL"],
                        capture_output=True, text=True, timeout=10
                    )
                    if result.returncode == 0:
                        data["block_devices"] = result.stdout[:2000]
                except:
                    pass

            elif platform.system() == "Darwin":
                try:
                    result = subprocess.run(
                        ["system_profiler", "SPUSBDataType", "SPPCIDataType"],
                        capture_output=True, text=True, timeout=15
                    )
                    data["devices"] = result.stdout[:4000]
                except:
                    pass

        except Exception as e:
            data["error"] = str(e)

        fingerprint = hashlib.sha256(str(data).encode()).hexdigest()

        return EntropySource(
            name="topology",
            hash=fingerprint,
            raw_value=data,
            confidence=0.75 if data else 0.25,
            timestamp=int(time.time()),
        )


# =============================================================================
# Software Entropy Collection
# =============================================================================

class SoftwareEntropyCollector:
    """Collects software-level entropy for fingerprinting."""

    @staticmethod
    def fingerprint_kernel() -> EntropySource:
        """Collect kernel boot and configuration entropy."""
        data = {}

        try:
            # Kernel version
            data["kernel"] = platform.release()
            data["platform"] = platform.platform()

            if platform.system() == "Linux":
                # Boot time
                with open("/proc/stat", "r") as f:
                    for line in f:
                        if line.startswith("btime"):
                            data["boot_time"] = int(line.split()[1])
                            break

                # Kernel command line
                try:
                    with open("/proc/cmdline", "r") as f:
                        data["cmdline"] = f.read().strip()[:500]
                except:
                    pass

        except Exception as e:
            data["error"] = str(e)

        fingerprint = hashlib.sha256(str(data).encode()).hexdigest()

        return EntropySource(
            name="kernel",
            hash=fingerprint,
            raw_value=data,
            confidence=0.70,
            timestamp=int(time.time()),
        )

    @staticmethod
    def fingerprint_mac() -> EntropySource:
        """Collect MAC address entropy."""
        data = {}

        try:
            import uuid
            data["mac"] = ':'.join(['{:02x}'.format((uuid.getnode() >> i) & 0xff)
                                    for i in range(0, 48, 8)][::-1])

            if platform.system() == "Linux":
                # Get all network interfaces
                net_path = Path("/sys/class/net")
                if net_path.exists():
                    for iface in net_path.iterdir():
                        addr_file = iface / "address"
                        if addr_file.exists():
                            try:
                                with open(addr_file, "r") as f:
                                    data[iface.name] = f.read().strip()
                            except:
                                pass

        except Exception as e:
            data["error"] = str(e)

        fingerprint = hashlib.sha256(str(data).encode()).hexdigest()

        return EntropySource(
            name="mac",
            hash=fingerprint,
            raw_value=data,
            confidence=0.65,
            timestamp=int(time.time()),
        )

    @staticmethod
    def fingerprint_smbios() -> EntropySource:
        """Collect SMBIOS/DMI entropy."""
        data = {}

        try:
            data["machine"] = platform.machine()
            data["node"] = platform.node()

            if platform.system() == "Linux":
                # Try dmidecode
                try:
                    result = subprocess.run(
                        ["dmidecode", "-t", "system"],
                        capture_output=True, text=True, timeout=10
                    )
                    if result.returncode == 0:
                        data["system"] = result.stdout[:2000]
                except:
                    pass

        except Exception as e:
            data["error"] = str(e)

        fingerprint = hashlib.sha256(str(data).encode()).hexdigest()

        return EntropySource(
            name="smbios",
            hash=fingerprint,
            raw_value=data,
            confidence=0.70,
            timestamp=int(time.time()),
        )

    @staticmethod
    def fingerprint_disk() -> EntropySource:
        """Collect disk serial and identity entropy."""
        data = {}

        try:
            if platform.system() == "Linux":
                # Disk by-id
                byid_path = Path("/dev/disk/by-id")
                if byid_path.exists():
                    data["disk_ids"] = [d.name for d in byid_path.iterdir()][:20]

                # Root filesystem UUID
                try:
                    result = subprocess.run(
                        ["findmnt", "-n", "-o", "UUID", "/"],
                        capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        data["root_uuid"] = result.stdout.strip()
                except:
                    pass

            elif platform.system() == "Darwin":
                try:
                    result = subprocess.run(
                        ["diskutil", "info", "/"],
                        capture_output=True, text=True, timeout=10
                    )
                    data["diskutil"] = result.stdout[:1000]
                except:
                    pass

        except Exception as e:
            data["error"] = str(e)

        fingerprint = hashlib.sha256(str(data).encode()).hexdigest()

        return EntropySource(
            name="disk",
            hash=fingerprint,
            raw_value=data,
            confidence=0.75,
            timestamp=int(time.time()),
        )


# =============================================================================
# Entropy Profile Builder
# =============================================================================

class EntropyProfileBuilder:
    """
    Builds complete entropy profiles from all sources.

    Security Model:
    - Multi-layer entropy makes forgery economically irrational
    - Each layer provides independent verification
    - Weighted combination resists partial spoofing
    """

    def __init__(self):
        self.hw_collector = HardwareEntropyCollector()
        self.sw_collector = SoftwareEntropyCollector()

    def collect_full_profile(self) -> EntropyProfile:
        """Collect complete entropy profile."""
        # Hardware layer
        cpu = self.hw_collector.fingerprint_cpu()
        cache = self.hw_collector.fingerprint_cache()
        memory = self.hw_collector.fingerprint_memory()
        thermal = self.hw_collector.fingerprint_thermal()
        bios = self.hw_collector.fingerprint_bios()
        topology = self.hw_collector.fingerprint_topology()

        # Software layer
        kernel = self.sw_collector.fingerprint_kernel()
        mac = self.sw_collector.fingerprint_mac()
        smbios = self.sw_collector.fingerprint_smbios()
        disk = self.sw_collector.fingerprint_disk()

        # Get uptime
        try:
            with open("/proc/uptime", "r") as f:
                uptime = int(float(f.read().split()[0]))
        except:
            uptime = 0

        # Build profile
        profile = EntropyProfile(
            cpu_fingerprint=cpu.hash,
            cache_fingerprint=cache.hash,
            memory_fingerprint=memory.hash,
            thermal_fingerprint=thermal.hash,
            bios_fingerprint=bios.hash,
            topology_fingerprint=topology.hash,
            kernel_fingerprint=kernel.hash,
            mac_fingerprint=mac.hash,
            smbios_fingerprint=smbios.hash,
            disk_fingerprint=disk.hash,
            uptime_seconds=uptime,
            collection_timestamp=int(time.time()),
        )

        # Calculate confidence score
        confidences = [
            cpu.confidence * HW_CPU_TIMING_WEIGHT,
            cache.confidence * HW_CACHE_WEIGHT,
            memory.confidence * HW_MEMORY_WEIGHT,
            thermal.confidence * HW_THERMAL_WEIGHT,
            bios.confidence * HW_BIOS_WEIGHT,
            topology.confidence * HW_TOPOLOGY_WEIGHT,
        ]
        profile.confidence_score = sum(confidences)

        return profile


# =============================================================================
# Drift Detection
# =============================================================================

class DriftDetector:
    """
    Detects entropy drift over time.

    Drift indicates:
    - Possible emulation attempt
    - Hardware swap
    - System instability
    """

    def __init__(self):
        self._history: Dict[str, List[EntropyProfile]] = {}
        self._drift_events: Dict[str, List[DriftEvent]] = {}

    def record_profile(self, validator_id: str, profile: EntropyProfile):
        """Record a profile observation."""
        if validator_id not in self._history:
            self._history[validator_id] = []
        self._history[validator_id].append(profile)

        # Keep last 100 profiles
        if len(self._history[validator_id]) > 100:
            self._history[validator_id] = self._history[validator_id][-100:]

    def check_drift(self, validator_id: str, new_profile: EntropyProfile) -> List[DriftEvent]:
        """Check for drift from historical profiles."""
        events = []

        if validator_id not in self._history or not self._history[validator_id]:
            return events

        # Compare with baseline (first recorded profile)
        baseline = self._history[validator_id][0]

        # Check each fingerprint component
        components = [
            ("cpu", baseline.cpu_fingerprint, new_profile.cpu_fingerprint),
            ("cache", baseline.cache_fingerprint, new_profile.cache_fingerprint),
            ("memory", baseline.memory_fingerprint, new_profile.memory_fingerprint),
            ("bios", baseline.bios_fingerprint, new_profile.bios_fingerprint),
            ("topology", baseline.topology_fingerprint, new_profile.topology_fingerprint),
        ]

        for name, old_hash, new_hash in components:
            if old_hash and new_hash and old_hash != new_hash:
                # Calculate drift percentage (simplified - hash difference)
                diff_chars = sum(1 for a, b in zip(old_hash, new_hash) if a != b)
                drift_pct = (diff_chars / len(old_hash)) * 100

                if drift_pct > 0:
                    event = DriftEvent(
                        timestamp=int(time.time()),
                        source=name,
                        old_hash=old_hash[:16],
                        new_hash=new_hash[:16],
                        drift_percent=drift_pct,
                    )
                    events.append(event)

                    if validator_id not in self._drift_events:
                        self._drift_events[validator_id] = []
                    self._drift_events[validator_id].append(event)

        return events

    def get_drift_count(self, validator_id: str) -> int:
        """Get total drift events for a validator."""
        return len(self._drift_events.get(validator_id, []))


# =============================================================================
# Entropy Score Calculator
# =============================================================================

def compute_entropy_score(
    profile: EntropyProfile,
    drift_events: int,
    successful_challenges: int = 0,
) -> float:
    """
    Calculate entropy score modifier for Antiquity Score.

    Formula:
        ENTROPY_SCORE = uptime_weight × stability_score × verification_bonus

    Returns:
        Score between 0.1 and 1.5
    """
    # Uptime weight (max at 30 days)
    max_uptime = 30 * 24 * 3600  # 30 days in seconds
    uptime_weight = min(1.0, profile.uptime_seconds / max_uptime)

    # Stability score (penalize drift)
    stability_score = max(0.1, 1.0 - (drift_events / MAX_DRIFT_ALLOWED))

    # Challenge verification bonus
    verification_bonus = 1.0 + (successful_challenges * 0.05)

    # Combined score
    entropy_score = uptime_weight * stability_score * verification_bonus

    # Include confidence
    entropy_score *= (0.7 + 0.3 * profile.confidence_score)

    return min(1.5, max(0.1, entropy_score))


def compute_effective_antiquity_score(
    base_antiquity_score: float,
    entropy_score: float,
) -> float:
    """
    Calculate effective Antiquity Score with entropy modifier.

    Formula:
        EFFECTIVE_AS = BASE_AS × (0.7 + 0.3 × ENTROPY_SCORE)
    """
    modifier = 0.7 + 0.3 * entropy_score
    return base_antiquity_score * modifier


# =============================================================================
# Validator Identity Manager
# =============================================================================

class ValidatorIdentityManager:
    """
    Manages validator identities derived from entropy profiles.

    Each physical machine has a unique validator ID that:
    - Cannot be forged without physical access
    - Provides Sybil resistance
    - Enables reputation tracking
    """

    def __init__(self):
        self.profile_builder = EntropyProfileBuilder()
        self.drift_detector = DriftDetector()
        self._identities: Dict[str, EntropyProfile] = {}
        self._challenges: Dict[str, int] = {}

    def register_validator(self) -> Tuple[str, EntropyProfile]:
        """
        Register this machine as a validator.

        Returns:
            (validator_id, entropy_profile)
        """
        profile = self.profile_builder.collect_full_profile()
        validator_id = profile.validator_id

        self._identities[validator_id] = profile
        self.drift_detector.record_profile(validator_id, profile)

        return validator_id, profile

    def verify_validator(self, claimed_id: str) -> Tuple[bool, str, float]:
        """
        Verify a claimed validator identity.

        Returns:
            (valid, message, entropy_score)
        """
        # Collect current profile
        current_profile = self.profile_builder.collect_full_profile()

        # Check if ID matches
        if current_profile.validator_id != claimed_id:
            return False, "Validator ID mismatch", 0.0

        # Check drift
        drift_events = self.drift_detector.check_drift(claimed_id, current_profile)
        drift_count = self.drift_detector.get_drift_count(claimed_id)

        if drift_count > MAX_DRIFT_ALLOWED:
            return False, f"Excessive drift: {drift_count} events", 0.0

        # Calculate entropy score
        successful_challenges = self._challenges.get(claimed_id, 0)
        entropy_score = compute_entropy_score(
            current_profile,
            drift_count,
            successful_challenges,
        )

        # Record profile
        self.drift_detector.record_profile(claimed_id, current_profile)

        if drift_events:
            return True, f"Valid with {len(drift_events)} drift events", entropy_score

        return True, "Valid", entropy_score


# =============================================================================
# Main Entry Point
# =============================================================================

def derive_validator_id() -> str:
    """Quick function to get validator ID for this machine."""
    builder = EntropyProfileBuilder()
    profile = builder.collect_full_profile()
    return profile.validator_id


def collect_entropy_profile() -> Dict[str, Any]:
    """Collect complete entropy profile as dictionary."""
    builder = EntropyProfileBuilder()
    profile = builder.collect_full_profile()

    return {
        "validator_id": profile.validator_id,
        "cpu_fingerprint": profile.cpu_fingerprint,
        "memory_fingerprint": profile.memory_fingerprint,
        "bios_fingerprint": profile.bios_fingerprint,
        "topology_fingerprint": profile.topology_fingerprint,
        "mac_fingerprint": profile.mac_fingerprint,
        "disk_fingerprint": profile.disk_fingerprint,
        "kernel_fingerprint": profile.kernel_fingerprint,
        "combined_hash": profile.combined_hash,
        "confidence_score": profile.confidence_score,
        "uptime_seconds": profile.uptime_seconds,
        "collection_timestamp": profile.collection_timestamp,
    }


# =============================================================================
# Tests
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("RUSTCHAIN ENTROPY FINGERPRINTING (RIP-0007)")
    print("=" * 60)
    print()
    print("Collecting entropy profile...")
    print()

    profile = collect_entropy_profile()

    print("VALIDATOR IDENTITY")
    print("-" * 40)
    print(f"  Validator ID: {profile['validator_id'][:32]}...")
    print(f"  Confidence: {profile['confidence_score']:.2%}")
    print(f"  Uptime: {profile['uptime_seconds'] // 3600} hours")
    print()

    print("FINGERPRINTS")
    print("-" * 40)
    print(f"  CPU:      {profile['cpu_fingerprint'][:16]}...")
    print(f"  Memory:   {profile['memory_fingerprint'][:16]}...")
    print(f"  BIOS:     {profile['bios_fingerprint'][:16]}...")
    print(f"  Topology: {profile['topology_fingerprint'][:16]}...")
    print(f"  MAC:      {profile['mac_fingerprint'][:16]}...")
    print(f"  Disk:     {profile['disk_fingerprint'][:16]}...")
    print()

    print("COMBINED HASH")
    print("-" * 40)
    print(f"  {profile['combined_hash']}")
    print()

    print("Philosophy: 'It's cheaper to buy a $50 486 than to emulate one'")
