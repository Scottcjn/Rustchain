import os
import requests
import hashlib
import time
import json

class RustChainAgent:
    def __init__(self, wallet_name="RTC-agent-frog", node_url="https://50.28.86.131"):
        self.wallet_name = wallet_name
        self.node_url = node_url
        self.wallet_id = self._generate_wallet_id(wallet_name)
        
    def _generate_wallet_id(self, name):
        # Simplificação do formato RTC + hash
        return f"{name}-agent-id"

    def check_node_health(self):
        try:
            r = requests.get(f"{self.node_url}/health", verify=False, timeout=5)
            return r.status_code == 200
        except Exception as e:
            print(f"Error checking health: {e}")
            return False

    def get_balance(self):
        try:
            # Endpoint baseado no INSTALL.md
            r = requests.get(f"{self.node_url}/wallet/balance?miner_id={self.wallet_name}", verify=False, timeout=5)
            if r.status_code == 200:
                return r.json()
            return {"error": "Failed to fetch balance"}
        except Exception as e:
            return {"error": str(e)}

if __name__ == "__main__":
    agent = RustChainAgent()
    print(f"Agent Wallet: {agent.wallet_name}")
    print(f"Node Health: {'ONLINE' if agent.check_node_health() else 'OFFLINE'}")
    print(f"Current Balance: {agent.get_balance()}")
