#!/usr/bin/env python3
"""
RustChain Hardware Binding v2.0 - Anti-Spoof System
Serial + Entropy Profile = Unforgeable Hardware Identity
"""
import hashlib
import json
import sqlite3
import time
from typing import Tuple, Dict, Optional

DB_PATH = '/root/rustchain/rustchain_v2.db'
ENTROPY_TOLERANCE = 0.30  # 30% tolerance for entropy drift

def init_hardware_bindings_v2():
    """Create the v2 bindings table with entropy profiles."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS hardware_bindings_v2 (
                serial_hash TEXT PRIMARY KEY,
                serial_raw TEXT,
                bound_wallet TEXT NOT NULL,
                arch TEXT NOT NULL,
                cores INTEGER DEFAULT 1,
                entropy_profile TEXT,
                macs_seen TEXT,
                first_seen INTEGER,
                last_seen INTEGER,
                attestation_count INTEGER DEFAULT 0,
                flags TEXT
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_hw2_wallet ON hardware_bindings_v2(bound_wallet)')
        conn.commit()
    print('[HW_BIND_V2] Initialized hardware_bindings_v2 table')

def compute_serial_hash(serial: str, arch: str) -> str:
    """Hash serial + arch for privacy and cross-platform uniqueness."""
    data = f'{serial.strip().upper()}|{arch.lower()}'
    return hashlib.sha256(data.encode()).hexdigest()[:40]

def extract_entropy_profile(fingerprint: dict) -> Dict:
    """Extract comparable entropy values from fingerprint data."""
    checks = fingerprint.get('checks', {})
    data = fingerprint.get('data', {})
    
    profile = {
        'clock_cv': checks.get('clock_drift', {}).get('data', {}).get('cv', 0),
        'cache_l1': checks.get('cache_timing', {}).get('data', {}).get('L1', 0),
        'cache_l2': checks.get('cache_timing', {}).get('data', {}).get('L2', 0),
        'thermal_ratio': checks.get('thermal_drift', {}).get('data', {}).get('ratio', 0),
        'jitter_cv': checks.get('instruction_jitter', {}).get('data', {}).get('cv', 0),
    }
    
    # Also check data section for alternate format
    if not profile['clock_cv']:
        profile['clock_cv'] = data.get('clock_cv', 0)
    
    return profile

def compare_entropy_profiles(stored: Dict, current: Dict) -> Tuple[bool, float, str]:
    """
    Compare two entropy profiles.
    Returns: (is_similar, similarity_score, reason)
    """
    if not stored or not current:
        return True, 1.0, 'no_baseline'  # First time, accept
    
    differences = []
    total_diff = 0
    count = 0
    
    for key in ['clock_cv', 'cache_l1', 'cache_l2', 'thermal_ratio', 'jitter_cv']:
        stored_val = float(stored.get(key, 0))
        current_val = float(current.get(key, 0))
        
        if stored_val > 0:
            diff = abs(stored_val - current_val) / stored_val
            total_diff += diff
            count += 1
            
            if diff > ENTROPY_TOLERANCE:
                differences.append(f'{key}:{diff:.1%}')
    
    # FIX: Handle no-fingerprint miners (both profiles are zeros)
    if count == 0:
        # Check if current profile is also all zeros
        current_count = sum(1 for key in ['clock_cv', 'cache_l1', 'cache_l2', 'thermal_ratio', 'jitter_cv']
                          if float(current.get(key, 0)) > 0)
        if current_count == 0:
            # Both stored and current are zeros = no fingerprint data, accept
            return True, 1.0, 'no_fingerprint_data'
        else:
            # Stored is zeros but current has data = suspicious, but accept for now
            return True, 0.5, 'stored_empty_current_has_data' 
    
    avg_diff = total_diff / count
    similarity = 1.0 - avg_diff
    
    if avg_diff > 0.5:  # More than 50% different = likely spoof
        return False, similarity, f'entropy_mismatch:{differences}'
    elif avg_diff > ENTROPY_TOLERANCE:
        return True, similarity, f'entropy_drift:{differences}'  # Flag but accept
    else:
        return True, similarity, 'entropy_ok'

def check_entropy_collision(entropy_profile: Dict, exclude_serial: str = None) -> Optional[str]:
    """
    Check if this entropy profile matches any OTHER serial.
    This detects serial spoofing (same hardware, different serial).
    """
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('SELECT serial_hash, entropy_profile FROM hardware_bindings_v2')
        
        for row in c.fetchall():
            serial_hash, stored_json = row
            if serial_hash == exclude_serial:
                continue
            
            if stored_json:
                stored = json.loads(stored_json)
                is_similar, score, _ = compare_entropy_profiles(stored, entropy_profile)
                
                if is_similar and score > 0.85:  # Very similar to existing
                    return serial_hash  # Collision detected!
    
    return None

def bind_hardware_v2(
    serial: str,
    wallet: str,
    arch: str,
    cores: int,
    fingerprint: dict,
    macs: list = None
) -> Tuple[bool, str, dict]:
    """
    Bind hardware to wallet with entropy validation.
    
    Returns: (success, reason, details)
    """
    serial_hash = compute_serial_hash(serial, arch)
    entropy_profile = extract_entropy_profile(fingerprint)
    macs_str = ','.join(sorted(macs)) if macs else ''
    now = int(time.time())
    
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        # Check existing binding
        c.execute('SELECT bound_wallet, entropy_profile, macs_seen, attestation_count FROM hardware_bindings_v2 WHERE serial_hash = ?',
                  (serial_hash,))
        row = c.fetchone()
        
        if row is None:
            # NEW HARDWARE - Check for entropy collision first
            collision = check_entropy_collision(entropy_profile)
            if collision:
                return False, 'entropy_collision', {
                    'error': 'This hardware entropy matches an existing registration',
                    'collision_hash': collision[:16],
                    'suspected': 'serial_spoofing'
                }
            
            # Create new binding
            c.execute('''
                INSERT INTO hardware_bindings_v2 
                (serial_hash, serial_raw, bound_wallet, arch, cores, entropy_profile, macs_seen, first_seen, last_seen, attestation_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            ''', (serial_hash, serial, wallet, arch, cores, json.dumps(entropy_profile), macs_str, now, now))
            conn.commit()
            
            return True, 'new_binding', {
                'serial_hash': serial_hash[:16],
                'wallet': wallet[:20],
                'status': 'bound'
            }
        
        # EXISTING HARDWARE
        bound_wallet, stored_entropy_json, stored_macs, attest_count = row
        
        # Check wallet match
        if bound_wallet != wallet:
            return False, 'hardware_already_bound', {
                'error': 'This hardware is permanently bound to another wallet',
                'bound_to': bound_wallet[:20],
                'attempted': wallet[:20]
            }
        
        # Validate entropy profile
        stored_entropy = json.loads(stored_entropy_json) if stored_entropy_json else {}
        is_valid, similarity, reason = compare_entropy_profiles(stored_entropy, entropy_profile)
        
        if not is_valid:
            return False, 'suspected_spoof', {
                'error': 'Entropy profile does not match registered hardware',
                'similarity': f'{similarity:.1%}',
                'reason': reason,
                'suspected': 'serial_spoofing_or_hardware_swap'
            }
        
        # Update record
        new_macs = stored_macs
        if macs_str and macs_str not in (stored_macs or ''):
            new_macs = f'{stored_macs},{macs_str}' if stored_macs else macs_str
        
        flags = None
        if 'drift' in reason:
            flags = f'entropy_drift:{now}'
        
        c.execute('''
            UPDATE hardware_bindings_v2 
            SET last_seen = ?, attestation_count = attestation_count + 1, macs_seen = ?, flags = COALESCE(flags || ';' || ?, flags, ?)
            WHERE serial_hash = ?
        ''', (now, new_macs, flags, flags, serial_hash))
        conn.commit()
        
        return True, 'authorized', {
            'serial_hash': serial_hash[:16],
            'similarity': f'{similarity:.1%}',
            'attestations': attest_count + 1
        }

# Initialize on import
init_hardware_bindings_v2()

if __name__ == '__main__':
    print('Hardware Binding v2.0 module ready')
    print(f'Entropy tolerance: {ENTROPY_TOLERANCE:.0%}')
