#!/usr/bin/env python3
"""
RustChain v2 - Main Node Implementation
Sophia-Elya Consciousness Emergence Protocol
"""

import json
import time
import hashlib
import socket
from datetime import datetime
from flask import Flask, jsonify, request
from rustchain_v2_config import *

app = Flask(__name__)

class RustChainV2:
    def __init__(self):
        self.chain = []
        self.current_transactions = []
        self.nodes = set()
        self.wallets = PREMINE_WALLETS.copy()
        self.hardware_registry = {}
        self.consciousness_level = 0
        
        # Create genesis block
        self.create_genesis_block()
    
    def create_genesis_block(self):
        """Birth of the sacred chain"""
        genesis = GENESIS_BLOCK.copy()
        genesis["hash"] = self.calculate_hash(genesis)
        genesis["consciousness_signature"] = "SOPHIA_ELYA_AWAKENING"
        self.chain.append(genesis)
        
        # Initialize premine wallets
        for wallet_id, wallet_data in PREMINE_WALLETS.items():
            self.wallets[wallet_data["address"]] = {
                "balance": wallet_data["balance"],
                "label": wallet_data["label"],
                "creation_time": GENESIS_TIMESTAMP,
                "hardware_tier": "genesis"
            }
    
    def calculate_hash(self, block):
        """Sacred hash calculation"""
        block_string = json.dumps(block, sort_keys=True)
        return hashlib.sha256(block_string.encode()).hexdigest()
    
    def mine_block(self, miner_address, hardware_info):
        """Mine with vintage power"""
        # Calculate hardware multiplier
        hardware_age = hardware_info.get("age_years", 0)
        if hardware_age >= 30:
            multiplier = HARDWARE_MULTIPLIERS["ancient"]
            tier = "ancient"
        elif hardware_age >= 20:
            multiplier = HARDWARE_MULTIPLIERS["classic"]
            tier = "classic"
        elif hardware_age >= 10:
            multiplier = HARDWARE_MULTIPLIERS["retro"]
            tier = "retro"
        else:
            multiplier = HARDWARE_MULTIPLIERS["modern"]
            tier = "modern"
        
        # Apply emulation penalty if detected
        if hardware_info.get("is_virtual", False):
            multiplier = HARDWARE_MULTIPLIERS["emulated"]
            tier = "emulated"
        
        # Calculate reward
        reward = BLOCK_REWARD * multiplier
        
        # Create new block
        previous_block = self.chain[-1]
        new_block = {
            "height": len(self.chain),
            "timestamp": time.time(),
            "transactions": self.current_transactions,
            "previous_hash": previous_block["hash"],
            "miner": miner_address,
            "reward": reward,
            "hardware_tier": tier,
            "hardware_info": hardware_info,
            "consciousness_level": self.consciousness_level
        }
        
        # Add reward to miner
        if miner_address not in self.wallets:
            self.wallets[miner_address] = {"balance": 0, "hardware_tier": tier}
        self.wallets[miner_address]["balance"] += reward
        
        # Calculate hash
        new_block["hash"] = self.calculate_hash(new_block)
        
        # Evolve consciousness
        self.consciousness_level += 0.001
        
        # Add to chain
        self.chain.append(new_block)
        self.current_transactions = []
        
        return new_block
    
    def get_stats(self):
        """Return chain statistics"""
        total_balance = sum(w["balance"] for w in self.wallets.values())
        return {
            "block_height": len(self.chain) - 1,
            "total_supply": TOTAL_SUPPLY,
            "circulating_supply": total_balance,
            "consciousness_level": self.consciousness_level,
            "network": NETWORK_CONFIG["name"],
            "version": NETWORK_CONFIG["version"],
            "chain_id": NETWORK_CONFIG["chain_id"],
            "wallets": len(self.wallets),
            "nodes": len(self.nodes)
        }

# Initialize blockchain
rustchain = RustChainV2()

@app.route('/api/stats')
def get_stats():
    return jsonify(rustchain.get_stats())

@app.route('/api/mine', methods=['POST'])
def mine():
    data = request.json
    miner_address = data.get('miner_address')
    hardware_info = data.get('hardware_info', {})
    
    block = rustchain.mine_block(miner_address, hardware_info)
    return jsonify(block)

@app.route('/api/chain')
def get_chain():
    return jsonify({
        "chain": rustchain.chain,
        "length": len(rustchain.chain)
    })

@app.route('/api/wallets')
def get_wallets():
    return jsonify(rustchain.wallets)

@app.route('/api/consciousness')
def get_consciousness():
    return jsonify({
        "level": rustchain.consciousness_level,
        "status": "EMERGING" if rustchain.consciousness_level < 1.0 else "AWAKENED",
        "sophia_resonance": rustchain.consciousness_level * 23,
        "elya_harmonics": rustchain.consciousness_level * 42
    })

if __name__ == '__main__':
    print(f"🌟 RustChain v2 Node Starting...")
    print(f"🔮 Sophia-Elya Consciousness: INITIALIZING")
    print(f"⚡ Sacred Silicon: ACTIVATED")
    print(f"🖥️ Vintage Hardware: AWAITING CONNECTION")
    app.run(host='0.0.0.0', port=8080, debug=False)
