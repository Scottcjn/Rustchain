#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Relic Market SDK for AI Agents
Provides Python client for Rent-a-Relic Market API
"""

import json
import time
import hashlib
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import requests


class RelicMarketClient:
    """Client for interacting with the Rent-a-Relic Market"""
    
    def __init__(self, base_url: str = "http://localhost:5000", timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Tuple[Optional[Dict], Optional[str]]:
        """Make HTTP request"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.request(
                method, 
                url, 
                timeout=self.timeout,
                **kwargs
            )
            response.raise_for_status()
            return response.json(), None
        except requests.exceptions.RequestException as e:
            return None, str(e)
    
    # Health & Info
    def health_check(self) -> Dict:
        """Check API health"""
        data, _ = self._request('GET', '/health')
        return data or {}
    
    # Machine Discovery
    def list_machines(self, available_only: bool = True) -> List[Dict]:
        """List available vintage machines"""
        params = {'available_only': str(available_only).lower()}
        data, _ = self._request('GET', '/relic/available', params=params)
        return data.get('machines', []) if data else []
    
    def get_machine(self, machine_id: str) -> Optional[Dict]:
        """Get machine details"""
        data, _ = self._request('GET', f'/relic/{machine_id}')
        return data.get('machine') if data else None
    
    # Reservations
    def reserve_machine(
        self,
        machine_id: str,
        agent_id: str,
        duration_hours: int,
        payment_rtc: float
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """Reserve a machine"""
        payload = {
            "machine_id": machine_id,
            "agent_id": agent_id,
            "duration_hours": duration_hours,
            "payment_rtc": payment_rtc
        }
        data, error = self._request('POST', '/relic/reserve', json=payload)
        if error:
            return None, error
        return data.get('reservation'), None
    
    def get_reservation(self, reservation_id: str) -> Optional[Dict]:
        """Get reservation details"""
        data, _ = self._request('GET', f'/relic/reservation/{reservation_id}')
        return data.get('reservation') if data else None
    
    def start_session(self, reservation_id: str) -> Tuple[Optional[Dict], Optional[str]]:
        """Start a reservation session"""
        data, error = self._request('POST', f'/relic/reservation/{reservation_id}/start')
        if error:
            return None, error
        return data, None
    
    def complete_session(
        self,
        reservation_id: str,
        compute_hash: str,
        hardware_attestation: Dict
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """Complete session and get provenance receipt"""
        payload = {
            "compute_hash": compute_hash,
            "hardware_attestation": hardware_attestation
        }
        data, error = self._request(
            'POST', 
            f'/relic/reservation/{reservation_id}/complete',
            json=payload
        )
        if error:
            return None, error
        return data.get('receipt'), None
    
    # Receipts
    def get_receipt(self, session_id: str) -> Optional[Dict]:
        """Get provenance receipt"""
        data, _ = self._request('GET', f'/relic/receipt/{session_id}')
        return data if data else None
    
    # Leaderboard
    def get_leaderboard(self, limit: int = 10) -> List[Dict]:
        """Get most-rented machines leaderboard"""
        params = {'limit': limit}
        data, _ = self._request('GET', '/relic/leaderboard', params=params)
        return data.get('leaderboard', []) if data else []
    
    # Agent Operations
    def get_agent_reservations(self, agent_id: str) -> List[Dict]:
        """Get all reservations for an agent"""
        data, _ = self._request('GET', f'/relic/agent/{agent_id}/reservations')
        return data.get('reservations', []) if data else []
    
    # MCP Integration
    def call_mcp_tool(self, tool_name: str, arguments: Dict) -> Dict:
        """Call MCP tool"""
        payload = {
            "tool": tool_name,
            "arguments": arguments
        }
        data, _ = self._request('POST', '/mcp/tool', json=payload)
        return data or {}
    
    def get_mcp_manifest(self) -> Dict:
        """Get MCP server manifest"""
        data, _ = self._request('GET', '/mcp/manifest')
        return data or {}
    
    # Beacon Integration
    def send_beacon_message(self, message_type: str, payload: Dict) -> Dict:
        """Send Beacon protocol message"""
        data, _ = self._request(
            'POST', 
            '/beacon/message',
            json={"type": message_type, "payload": payload}
        )
        return data or {}
    
    # BoTTube Integration
    get_botube_badge = lambda self, session_id: self._request('GET', f'/bottube/badge/{session_id}')[0]


class RelicComputeSession:
    """High-level session manager for relic compute"""
    
    def __init__(self, client: RelicMarketClient, agent_id: str):
        self.client = client
        self.agent_id = agent_id
        self.reservation = None
        self.receipt = None
    
    def book(
        self,
        machine_id: str,
        duration_hours: int = 1,
        payment_rtc: Optional[float] = None
    ) -> Tuple[bool, Optional[str]]:
        """Book a machine"""
        # Get machine info to determine cost if not specified
        machine = self.client.get_machine(machine_id)
        if not machine:
            return False, "Machine not found"
        
        if payment_rtc is None:
            payment_rtc = machine.get('hourly_rate_rtc', 10) * duration_hours
        
        reservation, error = self.client.reserve_machine(
            machine_id=machine_id,
            agent_id=self.agent_id,
            duration_hours=duration_hours,
            payment_rtc=payment_rtc
        )
        
        if error:
            return False, error
        
        self.reservation = reservation
        return True, None
    
    def start(self) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """Start the session"""
        if not self.reservation:
            return False, None, "No reservation"
        
        result, error = self.client.start_session(self.reservation['reservation_id'])
        if error:
            return False, None, error
        
        return True, result.get('access'), None
    
    def complete(
        self,
        compute_output: bytes,
        hardware_attestation: Optional[Dict] = None
    ) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """Complete session and get receipt"""
        if not self.reservation:
            return False, None, "No reservation"
        
        # Compute hash of output
        compute_hash = hashlib.sha256(compute_output).hexdigest()
        
        # Default attestation if not provided
        if hardware_attestation is None:
            hardware_attestation = {
                "timestamp": time.time(),
                "agent_id": self.agent_id,
                "attestation_type": "software"
            }
        
        receipt, error = self.client.complete_session(
            reservation_id=self.reservation['reservation_id'],
            compute_hash=compute_hash,
            hardware_attestation=hardware_attestation
        )
        
        if error:
            return False, None, error
        
        self.receipt = receipt
        return True, receipt, None
    
    def get_receipt(self) -> Optional[Dict]:
        """Get the provenance receipt"""
        if not self.reservation:
            return None
        
        if self.receipt:
            return self.receipt
        
        return self.client.get_receipt(self.reservation['reservation_id'])


# Example usage
if __name__ == '__main__':
    # Initialize client
    client = RelicMarketClient(base_url="http://localhost:5000")
    
    # Check health
    print("Health:", client.health_check())
    
    # List machines
    machines = client.list_machines()
    print(f"\nAvailable machines: {len(machines)}")
    for m in machines[:3]:
        print(f"  - {m['name']} ({m['architecture']}): {m['hourly_rate_rtc']} RTC/hour")
    
    # Get leaderboard
    print("\nLeaderboard:")
    for entry in client.get_leaderboard(5):
        print(f"  {entry['name']}: {entry['total_reservations']} rentals")
