#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Example: MCP Client Integration

Demonstrates how to use the Model Context Protocol (MCP)
to interact with the Rent-a-Relic Market.
"""

import json
import requests


class MCPClient:
    """Simple MCP client for Relic Market"""
    
    def __init__(self, server_url: str = "http://localhost:5000"):
        self.server_url = server_url.rstrip('/')
        self.session = requests.Session()
    
    def get_manifest(self):
        """Get MCP server manifest"""
        response = self.session.get(f"{self.server_url}/mcp/manifest")
        return response.json()
    
    def call_tool(self, tool_name: str, arguments: dict):
        """Call an MCP tool"""
        payload = {
            "tool": tool_name,
            "arguments": arguments
        }
        response = self.session.post(
            f"{self.server_url}/mcp/tool",
            json=payload
        )
        return response.json()


def main():
    print("=" * 60)
    print("MCP Integration Example")
    print("=" * 60)
    
    client = MCPClient("http://localhost:5000")
    
    # Get manifest
    print("\n1. Getting MCP Manifest...")
    manifest = client.get_manifest()
    print(f"   Server: {manifest['name']}")
    print(f"   Version: {manifest['version']}")
    print(f"   Available Tools: {list(manifest['tools'].keys())}")
    
    # Tool 1: List machines
    print("\n2. Calling tool: list_machines")
    print("-" * 60)
    result = client.call_tool("list_machines", {"available_only": True})
    
    for machine in result.get('machines', [])[:3]:
        print(f"\n   • {machine['name']}")
        print(f"     Architecture: {machine['architecture']}")
        print(f"     Rate: {machine['hourly_rate_rtc']} RTC/hr")
    
    # Tool 2: Reserve machine
    print("\n3. Calling tool: reserve_machine")
    print("-" * 60)
    result = client.call_tool("reserve_machine", {
        "machine_id": "vm-001",
        "agent_id": "mcp-agent-example",
        "duration_hours": 1,
        "payment_rtc": 50.0
    })
    
    if 'error' in result:
        print(f"   ERROR: {result['error']}")
    else:
        reservation = result.get('reservation', {})
        print(f"   Reservation ID: {reservation.get('reservation_id')}")
        print(f"   Status: {reservation.get('status')}")
        print(f"   Cost: {reservation.get('total_cost_rtc')} RTC")
        
        reservation_id = reservation.get('reservation_id')
        
        # Tool 3: Get reservation
        print("\n4. Calling tool: get_reservation")
        print("-" * 60)
        result = client.call_tool("get_reservation", {
            "reservation_id": reservation_id
        })
        print(f"   Machine: {result['reservation']['machine_id']}")
        print(f"   Agent: {result['reservation']['agent_id']}")
        print(f"   Duration: {result['reservation']['duration_hours']} hours")
        
        # Tool 4: Start session
        print("\n5. Calling tool: start_session")
        print("-" * 60)
        result = client.call_tool("start_session", {
            "reservation_id": reservation_id
        })
        
        if 'error' in result:
            print(f"   ERROR: {result['error']}")
        else:
            print(f"   Status: Session started")
            
            # Tool 5: Complete session
            print("\n6. Calling tool: complete_session")
            print("-" * 60)
            result = client.call_tool("complete_session", {
                "reservation_id": reservation_id,
                "compute_hash": "abc123def456...",
                "hardware_attestation": {
                    "cpu": "POWER8",
                    "verified": True
                }
            })
            
            if 'error' in result:
                print(f"   ERROR: {result['error']}")
            else:
                receipt = result.get('receipt', {})
                print(f"   Receipt ID: {receipt.get('receipt_id')}")
                print(f"   Signature: {receipt.get('signature', '')[:32]}...")
    
    print("\n" + "=" * 60)
    print("MCP integration example completed!")
    print("=" * 60)


if __name__ == '__main__':
    main()
