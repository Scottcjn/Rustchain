// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import json
import platform
import re
import subprocess
import sys
from typing import Dict, List, Optional, Tuple


class SiliconArchaeologyScanner:
    """Hardware scanner for vintage computing archaeology"""

    SILICON_EPOCHS = {
        0: {"name": "Pre-Silicon", "years": (1940, 1970), "multiplier": 0.1},
        1: {"name": "Early Silicon", "years": (1971, 1985), "multiplier": 0.5},
        2: {"name": "RISC Revolution", "years": (1986, 1995), "multiplier": 1.0},
        3: {"name": "Superscalar Era", "years": (1996, 2005), "multiplier": 2.0},
        4: {"name": "Multi-core Modern", "years": (2006, 2024), "multiplier": 4.0}
    }

    CPU_PATTERNS = {
        # x86 Family
        r'8086|8088': ('Intel 8086', 1, 1978),
        r'80286': ('Intel 80286', 1, 1982),
        r'80386|i386': ('Intel 80386', 2, 1985),
        r'80486|i486': ('Intel 80486', 2, 1989),
        r'Pentium.*Pro': ('Intel Pentium Pro', 3, 1995),
        r'Pentium.*II': ('Intel Pentium II', 3, 1997),
        r'Pentium.*III': ('Intel Pentium III', 3, 1999),
        r'Pentium.*4': ('Intel Pentium 4', 3, 2000),
        r'Pentium.*M': ('Intel Pentium M', 3, 2003),
        r'Core.*Duo': ('Intel Core Duo', 4, 2006),
        r'Core.*2': ('Intel Core 2', 4, 2007),
        r'Core.*i[357]': ('Intel Core i-series', 4, 2008),

        # AMD
        r'Am286': ('AMD Am286', 1, 1982),
        r'Am386': ('AMD Am386', 2, 1991),
        r'Am486': ('AMD Am486', 2, 1993),
        r'K5': ('AMD K5', 3, 1996),
        r'K6': ('AMD K6', 3, 1997),
        r'Athlon.*64': ('AMD Athlon 64', 4, 2003),
        r'Opteron': ('AMD Opteron', 4, 2003),
        r'Phenom': ('AMD Phenom', 4, 2007),

        # PowerPC
        r'601': ('PowerPC 601', 2, 1993),
        r'603': ('PowerPC 603', 2, 1994),
        r'604': ('PowerPC 604', 3, 1994),
        r'750|G3': ('PowerPC 750 (G3)', 3, 1997),
        r'7400|G4': ('PowerPC 7400 (G4)', 3, 1999),
        r'970|G5': ('PowerPC 970 (G5)', 4, 2003),

        # SPARC
        r'SPARC.*V7': ('SPARC v7', 2, 1987),
        r'SPARC.*V8': ('SPARC v8', 2, 1990),
        r'SPARC.*V9': ('SPARC v9', 3, 1995),
        r'UltraSPARC': ('UltraSPARC', 3, 1995),

        # MIPS
        r'R2000': ('MIPS R2000', 2, 1986),
        r'R3000': ('MIPS R3000', 2, 1988),
        r'R4000': ('MIPS R4000', 3, 1991),
        r'R10000': ('MIPS R10000', 3, 1996),

        # ARM (early)
        r'ARM.*1': ('ARM1', 2, 1985),
        r'ARM.*2': ('ARM2', 2, 1986),
        r'ARM.*6': ('ARM6', 2, 1991),
        r'ARM.*7': ('ARM7', 3, 1994),
        r'StrongARM': ('StrongARM', 3, 1996),

        # Alpha
        r'Alpha.*21064': ('DEC Alpha 21064', 3, 1992),
        r'Alpha.*21164': ('DEC Alpha 21164', 3, 1994),
        r'Alpha.*21264': ('DEC Alpha 21264', 4, 1998),

        # 68k
        r'68000': ('Motorola 68000', 1, 1979),
        r'68010': ('Motorola 68010', 1, 1982),
        r'68020': ('Motorola 68020', 2, 1984),
        r'68030': ('Motorola 68030', 2, 1987),
        r'68040': ('Motorola 68040', 2, 1990),
        r'68060': ('Motorola 68060', 3, 1994)
    }

    def __init__(self):
        self.system = platform.system().lower()

    def get_cpu_info_linux(self) -> Dict[str, str]:
        """Extract CPU info from /proc/cpuinfo on Linux"""
        try:
            with open('/proc/cpuinfo', 'r') as f:
                content = f.read()

            info = {}
            for line in content.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().lower()
                    if key in ['model name', 'cpu model', 'processor']:
                        info['model'] = value.strip()
                    elif key == 'vendor_id':
                        info['vendor'] = value.strip()
                    elif key == 'cpu family':
                        info['family'] = value.strip()

            return info
        except (IOError, OSError):
            return {}

    def get_cpu_info_macos(self) -> Dict[str, str]:
        """Extract CPU info using sysctl on macOS"""
        try:
            brand_cmd = ['sysctl', '-n', 'machdep.cpu.brand_string']
            brand_result = subprocess.run(brand_cmd, capture_output=True, text=True, timeout=5)

            info = {}
            if brand_result.returncode == 0:
                info['model'] = brand_result.stdout.strip()

            # Try to get additional info
            try:
                vendor_cmd = ['sysctl', '-n', 'machdep.cpu.vendor']
                vendor_result = subprocess.run(vendor_cmd, capture_output=True, text=True, timeout=5)
                if vendor_result.returncode == 0:
                    info['vendor'] = vendor_result.stdout.strip()
            except:
                pass

            return info
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError):
            return {}

    def get_cpu_info_powerpc(self) -> Dict[str, str]:
        """Extract CPU info for PowerPC systems"""
        info = {}

        # Try /proc/cpuinfo first (Linux PPC)
        try:
            with open('/proc/cpuinfo', 'r') as f:
                content = f.read()

            for line in content.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().lower()
                    if key in ['cpu', 'processor']:
                        info['model'] = value.strip()
                    elif key == 'machine':
                        info['machine'] = value.strip()

        except (IOError, OSError):
            pass

        # Try platform module
        try:
            proc_info = platform.processor()
            if proc_info and proc_info != 'unknown':
                info['model'] = proc_info
        except:
            pass

        return info

    def get_cpu_info(self) -> Dict[str, str]:
        """Get CPU information based on current platform"""
        if self.system == 'linux':
            return self.get_cpu_info_linux()
        elif self.system == 'darwin':
            return self.get_cpu_info_macos()
        else:
            # Try PowerPC or generic approach
            return self.get_cpu_info_powerpc()

    def classify_cpu(self, cpu_info: Dict[str, str]) -> Tuple[str, int, int, float]:
        """Classify CPU into silicon epoch and calculate RustChain multiplier"""
        model = cpu_info.get('model', '').strip()
        if not model:
            model = cpu_info.get('processor', '').strip()

        if not model:
            return 'Unknown CPU', 4, 2020, 1.0

        # Match against known patterns
        for pattern, (family, epoch, year) in self.CPU_PATTERNS.items():
            if re.search(pattern, model, re.IGNORECASE):
                epoch_info = self.SILICON_EPOCHS[epoch]
                multiplier = epoch_info['multiplier']

                # Apply some heuristics for RustChain multiplier
                if 'dual' in model.lower() or 'core 2' in model.lower():
                    multiplier *= 1.5
                elif 'quad' in model.lower():
                    multiplier *= 2.0

                return family, epoch, year, multiplier

        # Fallback classification based on common terms
        model_lower = model.lower()
        if any(term in model_lower for term in ['core', 'xeon', 'ryzen']):
            return f'Modern {model}', 4, 2010, 4.0
        elif any(term in model_lower for term in ['pentium', 'athlon', 'celeron']):
            return f'Legacy {model}', 3, 2000, 2.0
        elif any(term in model_lower for term in ['486', '386']):
            return f'Vintage {model}', 2, 1990, 1.0
        else:
            return f'Unknown {model}', 4, 2015, 2.0

    def scan_hardware(self) -> Dict:
        """Main scanning function that returns structured JSON"""
        cpu_info = self.get_cpu_info()
        family, epoch, year_estimate, rustchain_multiplier = self.classify_cpu(cpu_info)

        # Get additional system info
        arch = platform.machine()
        system_name = platform.system()

        result = {
            'family': family,
            'model': cpu_info.get('model', 'Unknown'),
            'epoch': epoch,
            'epoch_name': self.SILICON_EPOCHS[epoch]['name'],
            'year_estimate': year_estimate,
            'rustchain_multiplier': rustchain_multiplier,
            'architecture': arch,
            'system': system_name,
            'detected_info': cpu_info
        }

        return result

    def scan_json(self) -> str:
        """Return scan results as JSON string"""
        return json.dumps(self.scan_hardware(), indent=2)


def main():
    """Command line interface"""
    scanner = SiliconArchaeologyScanner()

    if len(sys.argv) > 1 and sys.argv[1] == '--json':
        print(scanner.scan_json())
    else:
        result = scanner.scan_hardware()
        print(f"Silicon Archaeology Scan Results:")
        print(f"Family: {result['family']}")
        print(f"Model: {result['model']}")
        print(f"Silicon Epoch: {result['epoch']} ({result['epoch_name']})")
        print(f"Estimated Year: {result['year_estimate']}")
        print(f"RustChain Multiplier: {result['rustchain_multiplier']}")
        print(f"Architecture: {result['architecture']}")
        print(f"System: {result['system']}")


if __name__ == '__main__':
    main()
