#!/usr/bin/env python3
"""
Universal Hardware Serial Detection
Works on: Mac (PPC/Intel/ARM), Linux, Windows
"""
import subprocess
import platform
import os
import hashlib

def run_cmd(cmd):
    try:
        if isinstance(cmd, str):
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        else:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return result.stdout.strip()
    except:
        return ''

def get_mac_serial():
    """Get serial from Mac (works on PPC, Intel, and Apple Silicon)."""
    # Method 1: ioreg (fastest, works on all Macs)
    output = run_cmd("ioreg -l | grep IOPlatformSerialNumber")
    if output:
        # Parse: "IOPlatformSerialNumber" = "ABC123"
        if '=' in output:
            serial = output.split('=')[1].strip().strip('"')
            if serial and len(serial) >= 8:
                return serial
    
    # Method 2: system_profiler (slower but reliable)
    output = run_cmd("system_profiler SPHardwareDataType | grep 'Serial Number'")
    if output:
        serial = output.split(':')[1].strip() if ':' in output else ''
        if serial and len(serial) >= 8:
            return serial
    
    return None

def get_linux_serial():
    """Get serial from Linux system."""
    # Method 1: DMI product serial
    paths = [
        '/sys/class/dmi/id/product_serial',
        '/sys/class/dmi/id/product_uuid',
        '/sys/class/dmi/id/board_serial',
    ]
    for path in paths:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    serial = f.read().strip()
                    if serial and serial not in ['', 'None', 'To Be Filled']:
                        return serial
            except:
                pass
    
    # Method 2: dmidecode (requires root)
    output = run_cmd('dmidecode -s system-serial-number 2>/dev/null')
    if output and output not in ['', 'None', 'To Be Filled']:
        return output
    
    # Method 3: For PPC Linux, try /proc/device-tree
    if os.path.exists('/proc/device-tree/serial-number'):
        try:
            with open('/proc/device-tree/serial-number', 'rb') as f:
                serial = f.read().decode('utf-8', errors='ignore').strip('\x00')
                if serial:
                    return serial
        except:
            pass
    
    return None

def get_windows_serial():
    """Get serial from Windows."""
    # BIOS serial
    output = run_cmd('wmic bios get serialnumber')
    lines = [l.strip() for l in output.split('\n') if l.strip() and 'SerialNumber' not in l]
    if lines and lines[0] not in ['', 'None', 'To Be Filled']:
        return lines[0]
    
    # Product UUID
    output = run_cmd('wmic csproduct get uuid')
    lines = [l.strip() for l in output.split('\n') if l.strip() and 'UUID' not in l]
    if lines and lines[0] not in ['', 'None']:
        return lines[0]
    
    return None

def get_hardware_serial():
    """Get hardware serial for current platform."""
    system = platform.system().lower()
    
    if system == 'darwin':
        return get_mac_serial()
    elif system == 'linux':
        return get_linux_serial()
    elif system == 'windows':
        return get_windows_serial()
    
    return None

def get_serial_with_fallback():
    """
    Get serial, with fallback to generated ID if no hardware serial available.
    The fallback should be stable (based on stable hardware info).
    """
    serial = get_hardware_serial()
    
    if serial:
        return serial, 'hardware'
    
    # Fallback: Generate from MAC addresses (stable across reboots)
    macs = []
    try:
        if platform.system() == 'Darwin':
            output = run_cmd('ifconfig | grep ether')
            for line in output.split('\n'):
                if 'ether' in line:
                    mac = line.split()[1] if len(line.split()) > 1 else ''
                    if mac and mac != '00:00:00:00:00:00':
                        macs.append(mac)
        else:
            output = run_cmd('ip -o link show | grep ether')
            for line in output.split('\n'):
                parts = line.split()
                for i, p in enumerate(parts):
                    if p == 'link/ether' and i+1 < len(parts):
                        mac = parts[i+1]
                        if mac != '00:00:00:00:00:00':
                            macs.append(mac)
    except:
        pass
    
    if macs:
        # Use first MAC as stable ID
        fallback = hashlib.sha256(sorted(macs)[0].encode()).hexdigest()[:20]
        return f'MAC-{fallback}', 'mac_derived'
    
    return None, 'none'

if __name__ == '__main__':
    serial, source = get_serial_with_fallback()
    print(f'Platform: {platform.system()} {platform.machine()}')
    print(f'Serial: {serial}')
    print(f'Source: {source}')
