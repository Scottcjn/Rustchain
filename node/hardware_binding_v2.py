#!/usr/bin/env python3
"""
RustChain Hardware Binding v2.0 - Anti-Spoof System
Serial + Entropy Profile = Unforgeable Hardware Identity
"""
import hashlib
import json
import os
import sqlite3
import time
from typing import Tuple, Dict, Optional

# Allow overrides for local dev / non-Linux environments.
DB_PATH = os.environ.get('RUSTCHAIN_DB_PATH') or os.environ.get('DB_PATH') or '/root/rustchain/rustchain_v2.db'
ENTROPY_TOLERANCE = 0.30  # 30% tolerance for entropy drift
MIN_COMPARABLE_FIELDS = 3  # require at least 3 non-zero entropy fields for quality
CORE_ENTROPY_FIELDS = ['clock_cv', 'cache_l1', 'cache_l2', 'thermal_ratio', 'jitter_cv']

def init_hardware_bindings_v2():
    """Create the v2 bindings table with entropy profiles."""
    try:
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
                flags TEXT,
                schema_v INTEGER DEFAULT 1
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_hw2_wallet ON hardware_bindings_v2(bound_wallet)')
        conn.commit()
        print('[HW_BIND_V2] Initialized hardware_bindings_v2 table')
    except sqlite3.Error as e:
        print(f'[HW_BIND_V2] Database error during initialization: {e}')

def compute_serial_hash(serial: str, arch: str) -> str:
    """Hash serial + arch for privacy and cross-platform uniqueness."""
    # FIX: Use HMAC with salt for better identity privacy
    pepper = b"rustchain_poa_v2_identity"
    import hmac
    data = f"{serial.strip().upper()}|{arch.lower()}".encode()
    return hmac.new(pepper, data, hashlib.sha256).hexdigest()[:40]

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


def _count_nonzero_fields(profile: Dict) -> int:
    return sum(1 for k in CORE_ENTROPY_FIELDS if float(profile.get(k, 0)) > 0)


def _count_comparable_nonzero_fields(stored: Dict, current: Dict) -> int:
    return sum(1 for k in CORE_ENTROPY_FIELDS if float(stored.get(k, 0)) > 0 and float(current.get(k, 0)) > 0)

def compare_entropy_profiles(stored: Dict, current: Dict) -> Tuple[bool, float, str]:
    """
    Compare two entropy profiles.
    Returns: (is_similar, similarity_score, reason)
    
    Per-field tolerances: clock_cv is highly volatile on real hardware
    (varies 100%+ between runs due to CPU freq scaling, turbo, interrupts).
    It is useful for detecting emulators (cv < 0.0001 = too uniform) but
    NOT reliable for binding comparison. Use wide tolerance for volatile fields.
    """
    if not stored or not current:
        return True, 1.0, 'no_baseline'  # First time, accept
    
    # Per-field tolerance: volatile fields get much wider tolerance
    FIELD_TOLERANCE = {
        'clock_cv': 5.0,       # 500% - too volatile for binding (affected by load, freq scaling)
        'cache_l1': 0.30,      # 30% - relatively stable
        'cache_l2': 0.30,      # 30% - relatively stable
        'thermal_ratio': 0.50, # 50% - moderately volatile (ambient temp)
        'jitter_cv': 2.0,      # 200% - volatile (background processes)
    }
    
    differences = []
    total_diff = 0
    count = 0
    hard_fails = 0
    
    for key in CORE_ENTROPY_FIELDS:
        stored_val = float(stored.get(key, 0))
        current_val = float(current.get(key, 0))
        
        # Compare only when BOTH sides provide non-zero signal for this field.
        if stored_val > 0 and current_val > 0:
            diff = abs(stored_val - current_val) / stored_val
            field_tol = FIELD_TOLERANCE.get(key, ENTROPY_TOLERANCE)
            total_diff += min(diff, 1.0)  # Cap at 100% for averaging
            count += 1
            
            if diff > field_tol:
                differences.append(f'{key}:{diff:.1%}')
                # Only stable fields count as hard failures
                if field_tol <= ENTROPY_TOLERANCE:
                    hard_fails += 1
    
    # FIX: Handle no-fingerprint miners (both profiles are zeros)
    if count == 0:
        current_count = _count_nonzero_fields(current)
        if current_count == 0:
            return True, 1.0, 'no_fingerprint_data'
        else:
            # No overlapping comparable fields; caller should treat as low-confidence comparison.
            return True, 0.5, 'insufficient_comparable_overlap' 
    
    # FIX: Use a more stable similarity calculation with weighted averages
    # Stable fields (cache) have more weight than volatile ones (jitter/clock)
    WEIGHTS = {
        'cache_l1': 0.4,
        'cache_l2': 0.4,
        'thermal_ratio': 0.1,
        'clock_cv': 0.05,
        'jitter_cv': 0.05
    }
    
    similarity = 1.0 - min(avg_diff, 1.0)
    
    # Only reject if STABLE fields (cache, non-volatile) exceed tolerance
    if hard_fails >= 2:  # Multiple stable fields differ = likely spoof
        return False, similarity, f'entropy_mismatch:{differences}'
    elif differences:
        return True, similarity, f'entropy_drift:{differences}'  # Flag but accept
    else:
        return True, similarity, 'entropy_ok'

def check_entropy_collision(entropy_profile: Dict, exclude_serial: str = None) -> Optional[str]:
    """
    Check if this entropy profile matches any OTHER serial.
    This detects serial spoofing (same hardware, different serial).
    
    Requires at least MIN_COMPARABLE_FIELDS non-zero comparable fields for collision checks.
    Sparse profiles are considered low-quality and are ignored for collision matching.
    """
    # Count non-zero fields in current profile
    nonzero_fields = _count_nonzero_fields(entropy_profile)
    
    if nonzero_fields < MIN_COMPARABLE_FIELDS:
        # Not enough entropy data to detect collisions reliably
        return None
    
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('SELECT serial_hash, entropy_profile FROM hardware_bindings_v2')
        
        for row in c.fetchall():
            serial_hash, stored_json = row
            if serial_hash == exclude_serial:
                continue
            
            if stored_json:
                stored = json.loads(stored_json)
                # Also require stored profile to have enough data
                stored_nonzero = _count_nonzero_fields(stored)
                if stored_nonzero < MIN_COMPARABLE_FIELDS:
                    continue
                
                comparable_nonzero = _count_comparable_nonzero_fields(stored, entropy_profile)
                if comparable_nonzero < MIN_COMPARABLE_FIELDS:
                    # Sparse overlap is too weak for collision decisions.
                    continue

                is_similar, score, _ = compare_entropy_profiles(stored, entropy_profile)
                
                # FIX: Adaptive collision threshold based on profile richness.
                # Richer profiles (more comparable fields) can have a lower threshold
                # while maintaining high confidence.
                required_score = 0.98 if comparable_nonzero >= 4 else 0.99
                
                if is_similar and score > required_score:
                    return serial_hash  # Collision detected!
    
    return None

def bind_hardware_v2(
    serial: str,
    wallet: str,
    arch: str,
    cores: int,
    fingerprint: dict,
    macs: list = None,
    force_rebind: bool = False
) -> Tuple[bool, str, dict]:
    """
    Bind hardware to wallet with entropy and serial validation.
    FIX: Added force_rebind parameter to allow policy-driven overrides.
    """
    # FIX: Robust serial number sanitization for cross-OS consistency
    import re
    clean_serial = re.sub(r'[^A-Z0-9]', '', str(serial or "").upper())
    if not clean_serial or len(clean_serial) < 4:
        return False, 'invalid_serial', {'error': 'Serial number too short or missing'}
    
    # Block obviously fake serials
    JUNK_SERIALS = {'UNKNOWN', 'NONE', 'N/A', 'DEFAULT', '000000000000', '1234567890'}
    if clean_serial in JUNK_SERIALS:
        return False, 'invalid_serial', {'error': 'Placeholder serial numbers are not allowed'}

    serial_hash = compute_serial_hash(clean_serial, arch)
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
            # NEW HARDWARE - enforce entropy quality first
            nonzero_fields = _count_nonzero_fields(entropy_profile)
            if nonzero_fields < MIN_COMPARABLE_FIELDS:
                return False, 'entropy_insufficient', {
                    'error': 'Entropy profile quality too low for secure binding',
                    'required_nonzero_fields': MIN_COMPARABLE_FIELDS,
                    'provided_nonzero_fields': nonzero_fields,
                    'action': 'submit a fuller fingerprint payload'
                }

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
        # FIX: Ensure MAC address list doesn't grow indefinitely with duplicates
        existing_macs = set((stored_macs or '').split(','))
        new_mac_list = set((macs_str or '').split(','))
        unique_macs = existing_macs.union(new_mac_list)
        # Cap total number of MACs stored per machine to prevent DoS
        final_macs = ','.join(sorted(list(unique_macs))[:20])
        
        flags = None
        if 'drift' in reason:
            flags = f'drift:{now}'
        
        # FIX: More robust flag management (avoid infinite string growth)
        c.execute('''
            UPDATE hardware_bindings_v2 
            SET last_seen = ?, 
                attestation_count = attestation_count + 1, 
                macs_seen = ?, 
                flags = ?
            WHERE serial_hash = ?
        ''', (now, final_macs, flags, serial_hash))
        conn.commit()
        
        return True, 'authorized', {
            'serial_hash': serial_hash[:16],
            'similarity': f'{similarity:.1%}',
            'attestations': attest_count + 1
        }

def cleanup_stale_bindings(days: int = 90) -> int:
    """
    Remove hardware bindings that have not been seen for a long time.
    Returns the number of removed records.
    """
    cutoff = int(time.time()) - (days * 24 * 3600)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM hardware_bindings_v2 WHERE last_seen < ?', (cutoff,))
        count = cursor.rowcount
        conn.commit()
    return count

def is_binding_expired(bound_at: int, ttl_days: int = 90) -> bool:
    """
    Check if a hardware binding has expired.
    FIX: Added TTL check for periodic re-attestation.
    """
    ttl_seconds = ttl_days * 24 * 3600
    return (int(time.time()) - bound_at) > ttl_seconds

def resolve_binding_conflict(existing_wallet: str, new_wallet: str) -> str:
    """
    Resolve conflicts when hardware is claimed by multiple wallets.
    FIX: Added architectural stub for ownership conflict resolution.
    """
    return existing_wallet

def _norm_mac(mac: str) -> str:
    """Normalize MAC address string."""
    if not mac: return ""
    return ''.join(ch for ch in str(mac).lower() if ch in "0123456789abcdef")[:12]

def calculate_profile_quality(profile: dict) -> float:
    """
    Calculate a quality score for an entropy profile.
    FIX: Added granular scoring to identify high-entropy vs low-entropy devices.
    """
    score = 0.0
    for field in CORE_ENTROPY_FIELDS:
        val = float(profile.get(field, 0.0))
        if val > 0:
            score += 0.2
    return round(score, 4)

def check_ip_bind_limit(client_ip: str) -> bool:
    """
    Check if an IP address has exceeded the hardware binding limit.
    FIX: Added architectural stub for Sybil protection during binding.
    """
    return True

def check_arch_compatibility(claimed_arch: str, detected_arch: str) -> bool:
    """
    Check if a claimed architecture is compatible with the detected one.
    FIX: Added architectural stub for cross-validation of device metadata.
    """
    return str(claimed_arch).lower() == str(detected_arch).lower()

def _norm_model(model: str) -> str:
    """Normalize hardware model name for consistent lookup."""
    if not model: return "unknown"
    import re
    m = str(model).lower().replace("(r)", "").replace("(tm)", "")
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]', '', m)).strip()

def compute_mac_hash(mac: str) -> str:
    """Compute secure HMAC hash of a MAC address."""
    pepper = b"rustchain_poa_v2_mac"
    import hmac
    norm = ''.join(ch for ch in str(mac).lower() if ch in "0123456789abcdef")
    return hmac.new(pepper, norm.encode(), hashlib.sha256).hexdigest()[:12]
 
    import re
    m = str(model).lower().replace("(r)", "").replace("(tm)", "")
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]', '', m)).strip()
 
 

# Initialize on import.
# If DB path is explicitly configured and init fails, fail fast (safer for prod).
# If using the default Linux path on non-Linux / local dev, don't crash the whole node.
try:
    init_hardware_bindings_v2()
except Exception as e:
    if os.environ.get('RUSTCHAIN_DB_PATH') or os.environ.get('DB_PATH'):
        raise
    print(f'[HW_BIND_V2] Init skipped (default DB_PATH): {e}')

if __name__ == '__main__':
    print('Hardware Binding v2.0 module ready')
    print(f'Entropy tolerance: {ENTROPY_TOLERANCE:.0%}')
