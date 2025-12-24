#!/usr/bin/env python3
'''
Hardware Binding Module - Prevents multi-wallet attacks
One physical machine = One miner wallet. Period.
'''
import hashlib
import sqlite3
import time

DB_PATH = '/root/rustchain/rustchain_v2.db'

def compute_hardware_id(device: dict) -> str:
    '''
    Compute a hardware ID from device info (EXCLUDING wallet/miner_id).
    Uses device_model, device_arch, device_family, and any hardware serial.
    '''
    # Collect hardware-specific fields only (no wallet!)
    hw_fields = [
        device.get('device_model', 'unknown'),
        device.get('device_arch', 'modern'),
        device.get('device_family', 'unknown'),
        device.get('cpu_serial', device.get('hardware_id', '')),
        device.get('device_id', ''),  # Some miners send this
    ]
    hw_string = '|'.join(str(f) for f in hw_fields)
    return hashlib.sha256(hw_string.encode()).hexdigest()[:32]

def check_hardware_binding(miner_id: str, device: dict, db_path: str = DB_PATH):
    '''
    Check if this hardware is already bound to a different wallet.
    
    Returns:
        (allowed, message, bound_wallet)
        - allowed=True: This miner can use this hardware
        - allowed=False: Hardware bound to different wallet
    '''
    hardware_id = compute_hardware_id(device)
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Check existing binding
    c.execute('SELECT bound_miner, attestation_count FROM hardware_bindings WHERE hardware_id = ?',
              (hardware_id,))
    row = c.fetchone()
    
    now = int(time.time())
    
    if row is None:
        # No binding exists - create one for this miner
        c.execute('''
            INSERT INTO hardware_bindings 
            (hardware_id, bound_miner, device_arch, device_model, bound_at, attestation_count)
            VALUES (?, ?, ?, ?, ?, 1)
        ''', (hardware_id, miner_id, device.get('device_arch'), device.get('device_model'), now))
        conn.commit()
        conn.close()
        return True, 'Hardware bound to wallet', miner_id
    
    bound_miner, attest_count = row
    
    if bound_miner == miner_id:
        # Same wallet - update count and allow
        c.execute('UPDATE hardware_bindings SET attestation_count = attestation_count + 1 WHERE hardware_id = ?',
                  (hardware_id,))
        conn.commit()
        conn.close()
        return True, 'Authorized hardware', miner_id
    else:
        # DIFFERENT wallet trying to use same hardware!
        conn.close()
        return False, f'Hardware already bound to {bound_miner[:16]}...', bound_miner

def get_all_bindings(db_path: str = DB_PATH):
    '''List all hardware bindings for admin view'''
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''
        SELECT hardware_id, bound_miner, device_arch, device_model, 
               datetime(bound_at, 'unixepoch'), attestation_count
        FROM hardware_bindings ORDER BY attestation_count DESC
    ''')
    rows = c.fetchall()
    conn.close()
    return rows

if __name__ == '__main__':
    # Test
    print('Hardware bindings:')
    for row in get_all_bindings():
        print(f'  {row[1][:20]:20} | {row[2]:12} | {row[5]} attestations')
