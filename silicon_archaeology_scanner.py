# SPDX-License-Identifier: MIT

import json
import os
import platform
import re
import subprocess
import sys


class SiliconArchaeologyScanner:

    EPOCH_TABLE = {
        0: {
            'families': ['8080', '8085', '6502', '6800', 'z80'],
            'year_range': (1970, 1979),
            'multiplier': 0.1
        },
        1: {
            'families': ['8086', '8088', '80286', '68000', '68010', '68020'],
            'year_range': (1980, 1989),
            'multiplier': 0.3
        },
        2: {
            'families': ['80386', '80486', '68030', '68040', 'sparc', 'mips'],
            'year_range': (1990, 1999),
            'multiplier': 0.6
        },
        3: {
            'families': ['pentium', 'pentium pro', 'pentium ii', 'pentium iii', 'athlon', 'duron', 'powerpc'],
            'year_range': (2000, 2009),
            'multiplier': 1.0
        },
        4: {
            'families': ['core', 'xeon', 'opteron', 'phenom', 'bulldozer', 'piledriver', 'steamroller', 'excavator', 'zen'],
            'year_range': (2010, 2024),
            'multiplier': 2.5
        }
    }

    def __init__(self):
        self.system = platform.system().lower()
        self.machine = platform.machine().lower()

    def detect_cpu_info(self):
        """Main detection method that tries different approaches based on OS"""
        cpu_info = {}

        if self.system == 'linux' or os.path.exists('/proc/cpuinfo'):
            cpu_info = self._parse_proc_cpuinfo()
        elif self.system == 'darwin':
            cpu_info = self._parse_macos_sysctl()
        else:
            cpu_info = self._parse_platform_fallback()

        return self._classify_hardware(cpu_info)

    def _parse_proc_cpuinfo(self):
        """Parse /proc/cpuinfo on Linux systems"""
        cpu_info = {'vendor': '', 'model': '', 'family': ''}

        try:
            with open('/proc/cpuinfo', 'r') as f:
                content = f.read().lower()

            # Extract vendor
            vendor_match = re.search(r'vendor_id\s*:\s*(.+)', content)
            if vendor_match:
                vendor = vendor_match.group(1).strip()
                if 'intel' in vendor:
                    cpu_info['vendor'] = 'Intel'
                elif 'amd' in vendor:
                    cpu_info['vendor'] = 'AMD'
                else:
                    cpu_info['vendor'] = vendor

            # Extract model name
            model_match = re.search(r'model name\s*:\s*(.+)', content)
            if model_match:
                cpu_info['model'] = model_match.group(1).strip()

            # Extract CPU family
            family_match = re.search(r'cpu family\s*:\s*(\d+)', content)
            if family_match:
                cpu_info['family'] = family_match.group(1)

        except (FileNotFoundError, IOError):
            pass

        return cpu_info

    def _parse_macos_sysctl(self):
        """Parse macOS system information using sysctl"""
        cpu_info = {'vendor': '', 'model': '', 'family': ''}

        try:
            # Get CPU brand string
            result = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'],
                                  capture_output=True, text=True)
            if result.returncode == 0:
                brand = result.stdout.strip()
                cpu_info['model'] = brand
                if 'intel' in brand.lower():
                    cpu_info['vendor'] = 'Intel'
                elif 'amd' in brand.lower():
                    cpu_info['vendor'] = 'AMD'
                elif 'apple' in brand.lower() or 'm1' in brand.lower() or 'm2' in brand.lower():
                    cpu_info['vendor'] = 'Apple'

            # Get CPU family
            result = subprocess.run(['sysctl', '-n', 'machdep.cpu.family'],
                                  capture_output=True, text=True)
            if result.returncode == 0:
                cpu_info['family'] = result.stdout.strip()

        except (subprocess.SubprocessError, FileNotFoundError):
            pass

        return cpu_info

    def _parse_platform_fallback(self):
        """Fallback method using platform module"""
        cpu_info = {
            'vendor': platform.processor() or 'Unknown',
            'model': platform.machine() or 'Unknown',
            'family': 'Unknown'
        }
        return cpu_info

    def _classify_hardware(self, cpu_info):
        """Classify hardware into historical epochs based on CPU information"""
        model = cpu_info.get('model', '').lower()
        vendor = cpu_info.get('vendor', '').lower()

        # Determine epoch based on CPU family/model
        epoch = 4  # Default to modern era

        for ep, data in self.EPOCH_TABLE.items():
            for family in data['families']:
                if family in model or family in vendor:
                    epoch = ep
                    break
            if epoch != 4:
                break

        # Calculate RTC (Retro Technology Credits)
        rtc_base = 10
        epoch_multiplier = self.EPOCH_TABLE[epoch]['multiplier']
        rtc_value = int(rtc_base * epoch_multiplier)

        return {
            'cpu_info': cpu_info,
            'epoch': epoch,
            'epoch_range': self.EPOCH_TABLE[epoch]['year_range'],
            'rtc_value': rtc_value,
            'classification': f"Epoch {epoch} ({self.EPOCH_TABLE[epoch]['year_range'][0]}-{self.EPOCH_TABLE[epoch]['year_range'][1]})"
        }

    def scan_hardware(self):
        """Public method to perform full hardware scan"""
        return self.detect_cpu_info()


def scan_system():
    """Convenience function for quick system scan"""
    scanner = SiliconArchaeologyScanner()
    return scanner.scan_hardware()


if __name__ == '__main__':
    # CLI interface
    scanner = SiliconArchaeologyScanner()
    result = scanner.scan_hardware()
    print(json.dumps(result, indent=2))
