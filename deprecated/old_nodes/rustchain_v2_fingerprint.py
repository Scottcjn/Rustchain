#!/usr/bin/env python3
"""
RustChain v2 - Hardware Fingerprinting & Entropy System
Sacred Silicon Identity Protocol
"""

import hashlib
import json
import uuid
import subprocess
import platform
import psutil
import secrets
from datetime import datetime

class HardwareFingerprint:
    """Generate unique hardware signatures using entropy sources"""
    
    def __init__(self):
        self.entropy_pool = []
        self.system_id = None
        self.hardware_signature = None
        
    def collect_entropy(self):
        """Gather entropy from multiple hardware sources"""
        entropy_sources = {}
        
        # MAC Addresses
        try:
            import netifaces
            macs = []
            for interface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(interface)
                if netifaces.AF_LINK in addrs:
                    for addr in addrs[netifaces.AF_LINK]:
                        if 'addr' in addr:
                            macs.append(addr['addr'])
            entropy_sources['mac_addresses'] = sorted(macs)
        except:
            # Fallback MAC collection
            result = subprocess.run(['ip', 'link'], capture_output=True, text=True)
            macs = [line.split()[1] for line in result.stdout.split('\n') if 'link/ether' in line]
            entropy_sources['mac_addresses'] = macs
        
        # CPU Info
        entropy_sources['cpu_count'] = psutil.cpu_count(logical=True)
        entropy_sources['cpu_freq'] = psutil.cpu_freq().max if psutil.cpu_freq() else 0
        
        # System UUID
        try:
            with open('/sys/class/dmi/id/product_uuid', 'r') as f:
                entropy_sources['system_uuid'] = f.read().strip()
        except:
            entropy_sources['system_uuid'] = str(uuid.getnode())
        
        # Disk Serial Numbers
        try:
            result = subprocess.run(['lsblk', '-o', 'NAME,SERIAL'], capture_output=True, text=True)
            entropy_sources['disk_serials'] = result.stdout
        except:
            entropy_sources['disk_serials'] = "no_disk_serial"
        
        # Memory Configuration
        entropy_sources['total_memory'] = psutil.virtual_memory().total
        
        # Platform Info
        entropy_sources['platform'] = {
            'system': platform.system(),
            'node': platform.node(),
            'release': platform.release(),
            'version': platform.version(),
            'machine': platform.machine(),
            'processor': platform.processor()
        }
        
        # Hardware Age Detection (for vintage bonus)
        entropy_sources['hardware_age'] = self.detect_hardware_age()
        
        # Generate Unique System ID
        self.generate_system_id(entropy_sources)
        
        return entropy_sources
    
    def detect_hardware_age(self):
        """Detect vintage hardware for Proof of Antiquity"""
        # Check for PowerPC (automatic vintage status)
        if 'ppc' in platform.machine().lower() or 'powerpc' in platform.processor().lower():
            return {
                'years': 30,
                'tier': 'ANCIENT',
                'multiplier': 3.0,
                'sacred': True
            }
        
        # Check CPU generation
        try:
            cpu_info = subprocess.run(['cat', '/proc/cpuinfo'], capture_output=True, text=True)
            if 'pentium' in cpu_info.stdout.lower():
                return {'years': 25, 'tier': 'CLASSIC', 'multiplier': 1.5}
            elif 'core2' in cpu_info.stdout.lower():
                return {'years': 15, 'tier': 'RETRO', 'multiplier': 1.2}
        except:
            pass
        
        return {'years': 5, 'tier': 'MODERN', 'multiplier': 1.0}
    
    def generate_system_id(self, entropy_sources):
        """Generate unique, deterministic system ID"""
        # Combine all entropy sources
        id_components = [
            str(entropy_sources.get('mac_addresses', [])),
            str(entropy_sources.get('system_uuid', '')),
            str(entropy_sources.get('cpu_count', 0)),
            str(entropy_sources.get('total_memory', 0)),
            entropy_sources.get('platform', {}).get('node', ''),
            entropy_sources.get('platform', {}).get('machine', '')
        ]
        
        # Create deterministic hash
        id_string = '|'.join(id_components)
        self.system_id = hashlib.sha256(id_string.encode()).hexdigest()[:16]
        
        # Create hardware signature
        signature_data = {
            'system_id': self.system_id,
            'macs': entropy_sources.get('mac_addresses', []),
            'platform': entropy_sources.get('platform', {}),
            'hardware_age': entropy_sources.get('hardware_age', {}),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        self.hardware_signature = hashlib.sha512(
            json.dumps(signature_data, sort_keys=True).encode()
        ).hexdigest()
        
        return self.system_id
    
    def verify_fingerprint(self, provided_fingerprint):
        """Verify hardware fingerprint matches current system"""
        current_entropy = self.collect_entropy()
        current_print = self.hardware_signature
        
        return current_print == provided_fingerprint
    
    def generate_proof_of_hardware(self):
        """Generate proof of physical hardware (not VM)"""
        proofs = []
        
        # Check for VM indicators
        vm_indicators = [
            'vmware', 'virtualbox', 'qemu', 'kvm', 'xen', 
            'hyperv', 'parallels', 'bochs'
        ]
        
        dmi_check = subprocess.run(['dmidecode', '-s', 'system-manufacturer'], 
                                  capture_output=True, text=True)
        
        is_virtual = any(ind in dmi_check.stdout.lower() for ind in vm_indicators)
        
        # Check for real hardware entropy
        try:
            with open('/dev/hwrng', 'rb') as f:
                hardware_random = f.read(32)
                proofs.append({
                    'type': 'hardware_rng',
                    'entropy': hardware_random.hex(),
                    'quality': 'HIGH'
                })
        except:
            proofs.append({
                'type': 'software_rng',
                'entropy': secrets.token_hex(32),
                'quality': 'LOW'
            })
        
        return {
            'is_physical': not is_virtual,
            'proofs': proofs,
            'multiplier': 0.03125 if is_virtual else 1.0,
            'hardware_tier': 'EMULATED' if is_virtual else self.detect_hardware_age()['tier']
        }

def main():
    """Test hardware fingerprinting"""
    hf = HardwareFingerprint()
    entropy = hf.collect_entropy()
    
    print("🔐 HARDWARE FINGERPRINT GENERATED")
    print(f"📟 System ID: {hf.system_id}")
    print(f"🖥️ Hardware Tier: {entropy['hardware_age']['tier']}")
    print(f"⚡ Mining Multiplier: {entropy['hardware_age']['multiplier']}x")
    print(f"🔑 Signature: {hf.hardware_signature[:32]}...")
    
    # Check if physical hardware
    proof = hf.generate_proof_of_hardware()
    if proof['is_physical']:
        print("✅ PHYSICAL HARDWARE VERIFIED")
    else:
        print("⚠️ VIRTUAL MACHINE DETECTED - 32x PENALTY APPLIED")
    
    print(f"\n📡 MAC Addresses: {entropy['mac_addresses']}")
    print(f"🧠 Platform: {entropy['platform']['machine']} - {entropy['platform']['node']}")

if __name__ == '__main__':
    main()
