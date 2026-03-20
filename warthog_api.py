// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import requests
import json
import subprocess
import platform
import time
import psutil
from typing import Dict, List, Optional, Tuple, Union

class WarthogAPI:
    """Warthog API client for node communication and pool verification"""

    def __init__(self, node_host: str = "localhost", node_port: int = 3000):
        self.node_host = node_host
        self.node_port = node_port
        self.node_url = f"http://{node_host}:{node_port}"
        self.session = requests.Session()
        self.session.timeout = 10

        # Pool API endpoints
        self.woolypooly_api = "https://api.woolypooly.com/api/warthog-wtg/"
        self.accpool_api = "https://acc-pool.com/api/warthog/"

    def get_chain_head(self) -> Optional[Dict]:
        """Query Warthog node chain/head endpoint"""
        try:
            response = self.session.get(f"{self.node_url}/chain/head")
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Chain head query failed: {e}")
        return None

    def get_chain_info(self) -> Optional[Dict]:
        """Get comprehensive chain information"""
        try:
            response = self.session.get(f"{self.node_url}/chain/info")
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass
        return None

    def verify_node_connection(self) -> bool:
        """Verify node is reachable and responding"""
        head_data = self.get_chain_head()
        if head_data and 'height' in head_data:
            return True

        # Try alternate port
        if self.node_port == 3000:
            self.node_port = 3001
            self.node_url = f"http://{self.node_host}:{self.node_port}"
            head_data = self.get_chain_head()
            return head_data is not None and 'height' in head_data

        return False

    def get_block_by_height(self, height: int) -> Optional[Dict]:
        """Get block data by height"""
        try:
            response = self.session.get(f"{self.node_url}/block/{height}")
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass
        return None

    def detect_warthog_processes(self) -> List[Dict]:
        """Detect running Warthog mining processes"""
        processes = []
        warthog_names = ['wart-miner', 'warthog-miner', 'janushash', 'warthog']

        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent']):
                proc_name = proc.info['name'].lower()
                cmdline = ' '.join(proc.info['cmdline'] or []).lower()

                for target in warthog_names:
                    if target in proc_name or target in cmdline:
                        processes.append({
                            'pid': proc.info['pid'],
                            'name': proc.info['name'],
                            'cmdline': proc.info['cmdline'],
                            'cpu_percent': proc.info['cpu_percent']
                        })
                        break
        except Exception as e:
            print(f"Process detection error: {e}")

        return processes

    def verify_woolypooly_account(self, wallet_address: str) -> Tuple[bool, Optional[Dict]]:
        """Verify account via WoolyPooly API"""
        try:
            url = f"{self.woolypooly_api}accounts/{wallet_address}"
            response = self.session.get(url)

            if response.status_code == 200:
                data = response.json()
                if data.get('success', False):
                    return True, data.get('result', {})

        except Exception as e:
            print(f"WoolyPooly verification failed: {e}")

        return False, None

    def verify_accpool_account(self, wallet_address: str) -> Tuple[bool, Optional[Dict]]:
        """Verify account via acc-pool API"""
        try:
            url = f"{self.accpool_api}stats/{wallet_address}"
            response = self.session.get(url)

            if response.status_code == 200:
                data = response.json()
                if 'hashrate' in data or 'balance' in data:
                    return True, data

        except Exception as e:
            print(f"Acc-pool verification failed: {e}")

        return False, None

    def verify_pool_account(self, wallet_address: str, pool_type: str = "auto") -> Tuple[bool, Optional[Dict]]:
        """Verify mining pool account with automatic detection"""
        if pool_type == "auto":
            # Try WoolyPooly first
            success, data = self.verify_woolypooly_account(wallet_address)
            if success:
                return True, {'pool': 'woolypooly', 'data': data}

            # Try acc-pool second
            success, data = self.verify_accpool_account(wallet_address)
            if success:
                return True, {'pool': 'acc-pool', 'data': data}

        elif pool_type == "woolypooly":
            success, data = self.verify_woolypooly_account(wallet_address)
            if success:
                return True, {'pool': 'woolypooly', 'data': data}

        elif pool_type == "accpool":
            success, data = self.verify_accpool_account(wallet_address)
            if success:
                return True, {'pool': 'acc-pool', 'data': data}

        return False, None

    def get_mining_stats(self, wallet_address: str) -> Dict:
        """Get comprehensive mining statistics"""
        stats = {
            'node_connected': False,
            'chain_height': 0,
            'processes_detected': [],
            'pool_verified': False,
            'pool_data': None,
            'last_updated': int(time.time())
        }

        # Check node connection
        if self.verify_node_connection():
            stats['node_connected'] = True
            head_data = self.get_chain_head()
            if head_data:
                stats['chain_height'] = head_data.get('height', 0)
                stats['chain_hash'] = head_data.get('hash', '')

        # Detect processes
        stats['processes_detected'] = self.detect_warthog_processes()

        # Verify pool account
        if wallet_address:
            verified, pool_data = self.verify_pool_account(wallet_address)
            stats['pool_verified'] = verified
            stats['pool_data'] = pool_data

        return stats

    def get_network_difficulty(self) -> Optional[float]:
        """Get current network difficulty"""
        try:
            response = self.session.get(f"{self.node_url}/chain/difficulty")
            if response.status_code == 200:
                data = response.json()
                return data.get('difficulty', 0)
        except Exception:
            pass
        return None

    def estimate_janushash_capability(self) -> Dict:
        """Estimate Janushash mining capability"""
        cpu_count = psutil.cpu_count(logical=True)
        cpu_freq = psutil.cpu_freq()

        # Basic estimation - actual hashrate varies significantly
        estimated_hashrate = cpu_count * 100  # Very rough estimate

        return {
            'cpu_cores': cpu_count,
            'cpu_frequency_mhz': cpu_freq.current if cpu_freq else 0,
            'estimated_hashrate': estimated_hashrate,
            'algorithm': 'janushash'
        }

def test_warthog_integration():
    """Test Warthog API integration"""
    client = WarthogAPI()

    print("Testing Warthog integration...")

    # Test node connection
    if client.verify_node_connection():
        print("✓ Node connection successful")
        head = client.get_chain_head()
        if head:
            print(f"  Chain height: {head.get('height', 'unknown')}")
    else:
        print("✗ Node connection failed")

    # Test process detection
    processes = client.detect_warthog_processes()
    if processes:
        print(f"✓ Found {len(processes)} Warthog processes")
        for proc in processes[:3]:  # Show first 3
            print(f"  PID {proc['pid']}: {proc['name']}")
    else:
        print("- No Warthog processes detected")

    # Test capability estimation
    capability = client.estimate_janushash_capability()
    print(f"CPU cores: {capability['cpu_cores']}, Est. hashrate: {capability['estimated_hashrate']}")

if __name__ == "__main__":
    test_warthog_integration()
