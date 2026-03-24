#!/usr/bin/env python3
"""
RustChain Node for 50.28.86.131
Modified Ergo node to accept Proof of Antiquity mining
"""

from flask import Flask, jsonify, request
import json
import time
import hashlib
from datetime import datetime

app = Flask(__name__)

# Blockchain state
blockchain = {
    "blocks": [],
    "pending_proofs": [],
    "wallets": {
        "98ad7c5973eb4a3173090b9e66011a6b7b8c42cf9RTC": {
            "balance": 0.0,
            "hardware": "PowerBook6,8",
            "tier": "VINTAGE_GOLD"
        }
    },
    "total_minted": 503429.5,
    "mining_pool": 7884178.5  # Remaining supply
}

# Load genesis if exists
try:
    with open('genesis.json', 'r') as f:
        genesis = json.load(f)
        blockchain["blocks"].append(genesis)
except:
    # Create genesis
    genesis = {
        "block_height": 0,
        "hash": "019c177b44a41f78da23caa99314adbc44889be2dcdd5021930f9d991e7e34cf",
        "timestamp": 1719800520,
        "miner": "PowerPC G4 Mirror Door",
        "reward": 503316.0,
        "hardware_age": 22
    }
    blockchain["blocks"].append(genesis)

@app.route('/api/mine', methods=['POST'])
def mine_block():
    """Accept mining proof from vintage hardware"""
    try:
        proof = request.json
        
        # Validate proof
        required_fields = ['wallet', 'hardware', 'age_years', 'multiplier', 'anti_emulation']
        for field in required_fields:
            if field not in proof:
                return jsonify({"success": False, "error": f"Missing field: {field}"}), 400
        
        # Verify anti-emulation
        anti_emulation = proof.get('anti_emulation', {})
        if not anti_emulation.get('darwin_ppc') or not anti_emulation.get('altivec'):
            return jsonify({"success": False, "error": "Anti-emulation check failed"}), 403
        
        # Calculate reward
        multiplier = min(proof['multiplier'], 3.5)  # Cap at ancient tier
        base_reward = 1.0
        actual_reward = min(base_reward * multiplier, 1.0)  # Cap at 1 RTC per block
        
        # Check if enough time passed (2 minutes between blocks)
        if blockchain["blocks"]:
            last_block = blockchain["blocks"][-1]
            if time.time() - last_block.get("timestamp", 0) < 120:
                return jsonify({
                    "success": False, 
                    "error": "Too soon, wait for next block",
                    "next_block_in": 120 - (time.time() - last_block.get("timestamp", 0))
                }), 429
        
        # Create new block
        new_block = {
            "block_height": len(blockchain["blocks"]),
            "timestamp": int(time.time()),
            "miner": proof["wallet"],
            "hardware": proof["hardware"],
            "age_years": proof["age_years"],
            "multiplier": multiplier,
            "reward": actual_reward,
            "previous_hash": blockchain["blocks"][-1]["hash"] if blockchain["blocks"] else "0"
        }
        
        # Calculate hash
        block_str = json.dumps(new_block, sort_keys=True)
        new_block["hash"] = hashlib.sha256(block_str.encode()).hexdigest()
        
        # Add block
        blockchain["blocks"].append(new_block)
        
        # Update wallet balance
        wallet = proof["wallet"]
        if wallet not in blockchain["wallets"]:
            blockchain["wallets"][wallet] = {"balance": 0.0}
        blockchain["wallets"][wallet]["balance"] += actual_reward
        blockchain["total_minted"] += actual_reward
        blockchain["mining_pool"] -= actual_reward
        
        return jsonify({
            "success": True,
            "block": new_block,
            "reward": actual_reward,
            "new_balance": blockchain["wallets"][wallet]["balance"]
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/stats')
def get_stats():
    """Get blockchain statistics"""
    return jsonify({
        "chain_id": 2718,
        "blocks": len(blockchain["blocks"]),
        "total_minted": blockchain["total_minted"],
        "mining_pool": blockchain["mining_pool"],
        "wallets": len(blockchain["wallets"]),
        "latest_block": blockchain["blocks"][-1] if blockchain["blocks"] else None
    })

@app.route('/api/blocks')
def get_blocks():
    """Get recent blocks"""
    return jsonify({
        "blocks": blockchain["blocks"][-10:],  # Last 10 blocks
        "total": len(blockchain["blocks"])
    })

@app.route('/api/wallet/<address>')
def get_wallet(address):
    """Get wallet balance"""
    if address in blockchain["wallets"]:
        return jsonify({
            "address": address,
            "balance": blockchain["wallets"][address]["balance"],
            "hardware": blockchain["wallets"][address].get("hardware", "Unknown")
        })
    else:
        return jsonify({"address": address, "balance": 0.0})

@app.route('/')
def index():
    """Simple status page"""
    return f"""
    <h1>RustChain Node - Proof of Antiquity</h1>
    <p>Chain ID: 2718</p>
    <p>Blocks: {len(blockchain["blocks"])}</p>
    <p>Total Minted: {blockchain["total_minted"]} RTC</p>
    <p>Mining Pool: {blockchain["mining_pool"]} RTC</p>
    <p>API Endpoints:</p>
    <ul>
        <li>POST /api/mine - Submit mining proof</li>
        <li>GET /api/stats - Blockchain statistics</li>
        <li>GET /api/blocks - Recent blocks</li>
        <li>GET /api/wallet/[address] - Wallet balance</li>
    </ul>
    """

if __name__ == '__main__':
    print("🔥 RustChain Node - Proof of Antiquity")
    print("📍 Chain ID: 2718")
    print("🌐 Starting on port 8085...")
    app.run(host='0.0.0.0', port=8085, debug=False)