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
                cpu_info['vendor'] = vendor_match.group(1).strip()

            # Extract model name
            model_match = re.search(r'model name\s*:\s*(.+)', content)
            if model_match:
                cpu_info['model'] = model_match.group(1).strip()

            # Extract CPU family
            family_match = re.search(r'cpu family\s*:\s*(\d+)', content)
            if family_match:
                cpu_info['family'] = family_match.group(1)

            # PowerPC specific fields
            if 'powerpc' in self.machine or 'ppc' in self.machine:
                cpu_match = re.search(r'cpu\s*:\s*(.+)', content)
                if cpu_match:
                    cpu_info['model'] = cpu_match.group(1).strip()
                    cpu_info['family'] = 'powerpc'

        except (IOError, OSError):
            pass

        return cpu_info

    def _parse_macos_sysctl(self):
        """Parse macOS system info using sysctl"""
        cpu_info = {'vendor': '', 'model': '', 'family': ''}

        try:
            # Get CPU brand string
            result = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'],
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                cpu_info['model'] = result.stdout.strip().lower()

            # Get CPU vendor
            result = subprocess.run(['sysctl', '-n', 'machdep.cpu.vendor'],
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                cpu_info['vendor'] = result.stdout.strip().lower()

            # Get CPU family
            result = subprocess.run(['sysctl', '-n', 'machdep.cpu.family'],
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                cpu_info['family'] = result.stdout.strip()

        except (subprocess.SubprocessError, subprocess.TimeoutExpired, OSError):
            pass

        return cpu_info

    def _parse_platform_fallback(self):
        """Fallback method using Python's platform module"""
        cpu_info = {
            'vendor': '',
            'model': platform.processor().lower() if platform.processor() else '',
            'family': self.machine
        }

        return cpu_info

    def _classify_hardware(self, cpu_info):
        """Classify detected hardware into Silicon Epochs"""
        model = cpu_info.get('model', '').lower()
        family = cpu_info.get('family', '').lower()
        vendor = cpu_info.get('vendor', '').lower()

        # Normalize common CPU identifiers
        normalized_family = self._normalize_cpu_family(model, family, vendor)

        # Find matching epoch
        detected_epoch = self._find_epoch(normalized_family)

        # Estimate year based on epoch
        year_estimate = self._estimate_year(detected_epoch, normalized_family)

        result = {
            'family': normalized_family,
            'model': model,
            'epoch': detected_epoch,
            'year_estimate': year_estimate,
            'rustchain_multiplier': self.EPOCH_TABLE[detected_epoch]['multiplier']
        }

        return result

    def _normalize_cpu_family(self, model, family, vendor):
        """Normalize CPU family names for classification"""
        combined = f"{model} {family} {vendor}".lower()

        # PowerPC detection
        if any(x in combined for x in ['powerpc', 'ppc', 'power']):
            return 'powerpc'

        # Intel families
        if 'pentium' in combined:
            if any(x in combined for x in ['pro', 'ii', 'iii']):
                if 'pro' in combined:
                    return 'pentium pro'
                elif 'iii' in combined:
                    return 'pentium iii'
                elif 'ii' in combined:
                    return 'pentium ii'
            return 'pentium'

        if any(x in combined for x in ['core', 'i3', 'i5', 'i7', 'i9']):
            return 'core'

        if 'xeon' in combined:
            return 'xeon'

        # AMD families
        if 'athlon' in combined:
            return 'athlon'
        if 'duron' in combined:
            return 'duron'
        if 'opteron' in combined:
            return 'opteron'
        if 'phenom' in combined:
            return 'phenom'
        if any(x in combined for x in ['bulldozer', 'piledriver', 'steamroller', 'excavator']):
            for arch in ['bulldozer', 'piledriver', 'steamroller', 'excavator']:
                if arch in combined:
                    return arch
        if 'zen' in combined:
            return 'zen'

        # Historic Intel
        if any(x in combined for x in ['8086', '8088']):
            return '8086' if '8086' in combined else '8088'
        if '80286' in combined or '286' in combined:
            return '80286'
        if '80386' in combined or '386' in combined:
            return '80386'
        if '80486' in combined or '486' in combined:
            return '80486'

        # Historic others
        if any(x in combined for x in ['6502', '6800', 'z80', '8080', '8085']):
            for cpu in ['6502', '6800', 'z80', '8080', '8085']:
                if cpu in combined:
                    return cpu

        # RISC
        if 'sparc' in combined:
            return 'sparc'
        if 'mips' in combined:
            return 'mips'

        # Motorola 68k series
        if any(x in combined for x in ['68000', '68010', '68020', '68030', '68040']):
            for cpu in ['68000', '68010', '68020', '68030', '68040']:
                if cpu in combined:
                    return cpu

        return 'unknown'

    def _find_epoch(self, normalized_family):
        """Find the Silicon Epoch for a given CPU family"""
        for epoch, data in self.EPOCH_TABLE.items():
            if normalized_family in data['families']:
                return epoch

        # Default to epoch 4 for unknown modern processors
        return 4

    def _estimate_year(self, epoch, family):
        """Estimate manufacturing year based on epoch and specific family"""
        base_range = self.EPOCH_TABLE[epoch]['year_range']

        # More specific year estimates for well-known processors
        specific_years = {
            '8080': 1974,
            '8085': 1976,
            '6502': 1975,
            '6800': 1974,
            'z80': 1976,
            '8086': 1978,
            '8088': 1979,
            '80286': 1982,
            '68000': 1979,
            '68010': 1982,
            '68020': 1984,
            '80386': 1985,
            '80486': 1989,
            '68030': 1987,
            '68040': 1990,
            'pentium': 1993,
            'pentium pro': 1995,
            'pentium ii': 1997,
            'pentium iii': 1999,
            'athlon': 1999,
            'duron': 2000,
            'powerpc': 1992,
            'core': 2006,
            'opteron': 2003,
            'phenom': 2007,
            'zen': 2017
        }

        if family in specific_years:
            return specific_years[family]

        # Return middle of range for unknown families
        return (base_range[0] + base_range[1]) // 2

    def scan_to_json(self):
        """Main public method - returns JSON string of hardware scan"""
        result = self.detect_cpu_info()
        return json.dumps(result, indent=2)


def main():
    scanner = SiliconArchaeologyScanner()
    print(scanner.scan_to_json())


if __name__ == '__main__':
    main()
