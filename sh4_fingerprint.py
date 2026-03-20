# SPDX-License-Identifier: MIT
# SH4 Dreamcast Hardware Fingerprinting Module
# Detects unique console characteristics for antiquity multiplier verification

import time
import os
import struct
import hashlib
import subprocess
from typing import Dict, List, Optional, Tuple
import ctypes
import ctypes.util


class SH4Fingerprint:
    """Hardware fingerprinting for Sega Dreamcast SH4 architecture"""

    def __init__(self):
        self.libc = None
        self._load_libc()
        self.cpu_info = self._get_cpu_info()

    def _load_libc(self):
        """Load libc for low-level timing operations"""
        try:
            libc_path = ctypes.util.find_library("c")
            if libc_path:
                self.libc = ctypes.CDLL(libc_path)
        except Exception:
            pass

    def _get_cpu_info(self) -> Dict[str, str]:
        """Extract SH4 CPU information from /proc/cpuinfo"""
        cpu_data = {}
        try:
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if ':' in line:
                        key, value = line.strip().split(':', 1)
                        cpu_data[key.strip()] = value.strip()
        except Exception:
            pass
        return cpu_data

    def detect_sh4_cache_timing(self) -> Dict[str, float]:
        """Measure SH4 cache access patterns - highly unique per console"""
        cache_timings = {}

        # SH4 has 16KB I-cache + 16KB D-cache, 32-byte lines
        cache_sizes = [16384, 32768, 65536]  # Test various sizes

        for size in cache_sizes:
            start_time = time.perf_counter_ns()

            # Allocate memory and perform cache-sensitive operations
            try:
                data = bytearray(size)
                for i in range(0, size, 32):  # 32-byte cache line
                    data[i] = (i & 0xFF)

                # Read pattern that stresses cache hierarchy
                checksum = 0
                for i in range(0, size, 64):
                    checksum ^= data[i]

            except Exception:
                checksum = 0

            end_time = time.perf_counter_ns()
            cache_timings[f'cache_{size}'] = (end_time - start_time) / 1000000.0

        return cache_timings

    def measure_fpu_jitter(self) -> Dict[str, float]:
        """Measure SH4 FPU timing variations - each console has unique patterns"""
        fpu_measurements = {}

        # SH4 has single and double precision FPU
        test_values = [3.14159, 2.71828, 1.41421, 0.57721]
        operations = ['add', 'mul', 'div', 'sqrt']

        for op_name in operations:
            timings = []

            for _ in range(50):  # Multiple samples for jitter analysis
                start = time.perf_counter_ns()

                try:
                    result = 0.0
                    for val in test_values:
                        if op_name == 'add':
                            result += val * 1.23456
                        elif op_name == 'mul':
                            result *= val
                        elif op_name == 'div':
                            result = val / (result + 0.001)
                        elif op_name == 'sqrt':
                            result = val ** 0.5

                except Exception:
                    result = 0.0

                end = time.perf_counter_ns()
                timings.append(end - start)

            # Calculate jitter statistics
            if timings:
                avg_time = sum(timings) / len(timings)
                variance = sum((t - avg_time) ** 2 for t in timings) / len(timings)
                fpu_measurements[f'fpu_{op_name}_avg'] = avg_time / 1000.0  # microseconds
                fpu_measurements[f'fpu_{op_name}_jitter'] = variance ** 0.5 / 1000.0

        return fpu_measurements

    def probe_tmu_timer_behavior(self) -> Dict[str, int]:
        """Probe SH4 Timer Unit behavior - hardware-specific characteristics"""
        tmu_data = {}

        # Try to read SH4-specific timer registers if accessible
        timer_paths = [
            '/sys/devices/system/clocksource/clocksource0/current_clocksource',
            '/proc/timer_stats',
            '/sys/kernel/debug/clocksource'
        ]

        for path in timer_paths:
            try:
                if os.path.exists(path):
                    with open(path, 'r') as f:
                        content = f.read().strip()
                        tmu_data[f'timer_{os.path.basename(path)}'] = hash(content) & 0xFFFFFFFF
            except Exception:
                pass

        # Measure timer resolution and drift
        timer_samples = []
        for _ in range(20):
            t1 = time.time_ns()
            time.sleep(0.001)  # 1ms sleep
            t2 = time.time_ns()
            timer_samples.append(t2 - t1)

        if timer_samples:
            tmu_data['timer_resolution'] = int(min(timer_samples))
            tmu_data['timer_drift'] = int(max(timer_samples) - min(timer_samples))

        return tmu_data

    def extract_broadband_adapter_mac(self) -> Optional[str]:
        """Extract Dreamcast Broadband Adapter MAC address"""
        mac_addresses = []

        # Check network interfaces for Realtek RTL8139 (BBA chipset)
        try:
            result = subprocess.run(['ip', 'link', 'show'],
                                  capture_output=True, text=True, timeout=5)

            for line in result.stdout.split('\n'):
                if 'link/ether' in line:
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part == 'link/ether' and i + 1 < len(parts):
                            mac = parts[i + 1]
                            # BBA typically has specific MAC prefixes
                            if mac.startswith(('00:d0:f1:', '00:04:1f:', '00:a0:cc:')):
                                mac_addresses.append(mac)

        except Exception:
            pass

        # Also try reading from /sys/class/net
        try:
            net_path = '/sys/class/net'
            if os.path.exists(net_path):
                for interface in os.listdir(net_path):
                    addr_file = os.path.join(net_path, interface, 'address')
                    if os.path.exists(addr_file):
                        with open(addr_file, 'r') as f:
                            mac = f.read().strip()
                            if mac != '00:00:00:00:00:00' and len(mac) == 17:
                                mac_addresses.append(mac)
        except Exception:
            pass

        return mac_addresses[0] if mac_addresses else None

    def check_dreamcast_hardware_markers(self) -> Dict[str, bool]:
        """Check for Dreamcast-specific hardware markers"""
        markers = {}

        # Check for SH4 CPU architecture
        markers['is_sh4'] = 'sh4' in self.cpu_info.get('processor', '').lower()
        markers['is_sh7750'] = 'sh7750' in str(self.cpu_info).lower()

        # Check for specific memory layout
        try:
            with open('/proc/meminfo', 'r') as f:
                meminfo = f.read()
                # Dreamcast typically has 16MB main RAM + 8MB video RAM
                total_kb = 0
                for line in meminfo.split('\n'):
                    if line.startswith('MemTotal:'):
                        total_kb = int(line.split()[1])
                        break
                # Allow some variance for kernel overhead
                markers['dreamcast_memory'] = 15000 <= total_kb <= 28000
        except Exception:
            markers['dreamcast_memory'] = False

        # Check for Dreamcast-specific device tree or hardware info
        dt_paths = ['/proc/device-tree/model', '/proc/device-tree/compatible']
        for path in dt_paths:
            try:
                if os.path.exists(path):
                    with open(path, 'r') as f:
                        content = f.read().lower()
                        markers['dreamcast_dt'] = 'dreamcast' in content or 'sega' in content
                        break
            except Exception:
                pass
        else:
            markers['dreamcast_dt'] = False

        return markers

    def generate_fingerprint(self) -> Dict:
        """Generate complete hardware fingerprint"""
        fingerprint = {
            'timestamp': int(time.time()),
            'cpu_info': dict(list(self.cpu_info.items())[:10]),  # Limit size
            'hardware_markers': self.check_dreamcast_hardware_markers(),
            'cache_timing': self.detect_sh4_cache_timing(),
            'fpu_jitter': self.measure_fpu_jitter(),
            'tmu_behavior': self.probe_tmu_timer_behavior(),
            'broadband_mac': self.extract_broadband_adapter_mac()
        }

        # Generate signature hash
        fingerprint_str = str(sorted(fingerprint.items()))
        fingerprint['signature'] = hashlib.sha256(fingerprint_str.encode()).hexdigest()[:32]

        return fingerprint

    def verify_dreamcast_authenticity(self) -> Tuple[bool, float]:
        """Verify this is genuine Dreamcast hardware and calculate confidence score"""
        fp = self.generate_fingerprint()
        confidence = 0.0

        # Check hardware markers
        markers = fp['hardware_markers']
        if markers.get('is_sh4', False):
            confidence += 0.3
        if markers.get('dreamcast_memory', False):
            confidence += 0.2
        if markers.get('dreamcast_dt', False):
            confidence += 0.2

        # Check MAC address
        if fp.get('broadband_mac'):
            confidence += 0.1

        # Analyze timing patterns (simplified heuristics)
        cache_timings = fp.get('cache_timing', {})
        if cache_timings:
            # SH4 @ 200MHz should have specific timing characteristics
            cache_16k = cache_timings.get('cache_16384', 0)
            if 0.1 <= cache_16k <= 10.0:  # Reasonable range for SH4
                confidence += 0.1

        fpu_jitter = fp.get('fpu_jitter', {})
        if fpu_jitter:
            # Real hardware should show some jitter
            total_jitter = sum(v for k, v in fpu_jitter.items() if 'jitter' in k)
            if total_jitter > 0:
                confidence += 0.1

        is_authentic = confidence >= 0.7  # 70% confidence threshold
        return is_authentic, confidence


def get_dreamcast_fingerprint() -> Dict:
    """Main entry point for Dreamcast fingerprinting"""
    fingerprinter = SH4Fingerprint()
    return fingerprinter.generate_fingerprint()


def verify_sh4_hardware() -> Tuple[bool, float, Dict]:
    """Verify SH4/Dreamcast hardware and return authentication info"""
    fingerprinter = SH4Fingerprint()
    is_auth, confidence = fingerprinter.verify_dreamcast_authenticity()
    fingerprint = fingerprinter.generate_fingerprint()

    return is_auth, confidence, fingerprint


if __name__ == '__main__':
    # CLI testing
    print("SH4/Dreamcast Hardware Fingerprinting")
    print("====================================")

    fp = get_dreamcast_fingerprint()
    print(f"Signature: {fp.get('signature', 'N/A')}")
    print(f"Hardware Markers: {fp.get('hardware_markers', {})}")

    is_auth, confidence, _ = verify_sh4_hardware()
    print(f"Authentication: {is_auth} (confidence: {confidence:.2f})")

    if fp.get('broadband_mac'):
        print(f"Broadband Adapter MAC: {fp['broadband_mac']}")
