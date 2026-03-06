#!/usr/bin/env python3
"""
RustChain Node with Realistic Mining Speed
Slower block times and more realistic difficulty
"""

from flask import Flask, jsonify, request
import json
import time
import hashlib
from datetime import datetime
from threading import Lock, Thread

app = Flask(__name__)

# Blockchain state with thread safety
blockchain_lock = Lock()
blockchain = {
    "blocks": [],
    "pending_proofs": [],  # Collect proofs for current block
    "wallets": {},
    "total_minted": 503458.5,  # Continue from current state
    "mining_pool": 7884149.5,
    "current_block_start": 0,
    "last_difficulty_adjust": 0,
    "network_hashrate": 0,
    "average_block_time": 600  # 10 minutes initially
}

# Load genesis
try:
    with open('genesis.json', 'r') as f:
        genesis = json.load(f)
        blockchain["blocks"].append(genesis)
except:
    genesis = {
        "block_height": 0,
        "hash": "019c177b44a41f78da23caa99314adbc44889be2dcdd5021930f9d991e7e34cf",
        "timestamp": 1719800520,
        "miner": "PowerPC G4 Mirror Door",
        "reward": 503316.0,
        "hardware_age": 22
    }
    blockchain["blocks"].append(genesis)

def calculate_dynamic_block_time():
    """Calculate block time based on network participants"""
    with blockchain_lock:
        miner_count = len(blockchain["pending_proofs"])
        
        # Base block time starts at 10 minutes
        base_time = 600
        
        if miner_count == 0:
            # No miners, very slow blocks
            return 1800  # 30 minutes
        elif miner_count == 1:
            # Single miner, 10 minutes
            return 600
        elif miner_count == 2:
            # Two miners, 8 minutes
            return 480
        elif miner_count >= 3:
            # Multiple miners, 5 minutes minimum
            return 300
        
        return base_time

def adjust_difficulty():
    """Adjust mining difficulty based on block times"""
    with blockchain_lock:
        if len(blockchain["blocks"]) < 10:
            return  # Need history
        
        # Calculate average time of last 10 blocks
        recent_blocks = blockchain["blocks"][-10:]
        time_diffs = []
        
        for i in range(1, len(recent_blocks)):
            diff = recent_blocks[i]["timestamp"] - recent_blocks[i-1]["timestamp"]
            time_diffs.append(diff)
        
        if time_diffs:
            avg_time = sum(time_diffs) / len(time_diffs)
            blockchain["average_block_time"] = avg_time
            
            # Log difficulty adjustment
            print(f"📊 Average block time: {avg_time:.1f}s (target: {calculate_dynamic_block_time()}s)")

def process_block():
    """Process all pending proofs and create new block"""
    with blockchain_lock:
        if not blockchain["pending_proofs"]:
            # No proofs, restart timer
            blockchain["current_block_start"] = time.time()
            return None
            
        # Calculate total multipliers
        total_multipliers = sum(p['multiplier'] for p in blockchain["pending_proofs"])
        
        # Maximum 1.0 RTC per block
        block_reward = 1.0
        
        # Calculate rewards for each miner
        miners = []
        for proof in blockchain["pending_proofs"]:
            miner_share = (proof['multiplier'] / total_multipliers) * block_reward
            miners.append({
                "wallet": proof['wallet'],
                "hardware": proof['hardware'],
                "multiplier": proof['multiplier'],
                "reward": round(miner_share, 6)
            })
            
            # Update wallet balance
            wallet = proof['wallet']
            if wallet not in blockchain["wallets"]:
                blockchain["wallets"][wallet] = {
                    "balance": 0.0,
                    "hardware": proof['hardware']
                }
            blockchain["wallets"][wallet]["balance"] += miner_share
        
        # Calculate actual minted
        actual_minted = min(total_multipliers, 1.0)
        unminted = block_reward - actual_minted
        
        # Create new block
        new_block = {
            "block_height": len(blockchain["blocks"]),
            "timestamp": int(time.time()),
            "miners": miners,
            "total_multipliers": round(total_multipliers, 2),
            "total_reward": round(actual_minted, 6),
            "unminted_returned": round(unminted, 6),
            "previous_hash": blockchain["blocks"][-1]["hash"] if blockchain["blocks"] else "0",
            "difficulty": blockchain["average_block_time"],
            "miner_count": len(miners)
        }
        
        # Calculate hash
        block_str = json.dumps(new_block, sort_keys=True)
        new_block["hash"] = hashlib.sha256(block_str.encode()).hexdigest()
        
        # Update blockchain
        blockchain["blocks"].append(new_block)
        blockchain["total_minted"] += actual_minted
        blockchain["mining_pool"] -= actual_minted
        blockchain["mining_pool"] += unminted
        
        # Clear pending proofs
        blockchain["pending_proofs"] = []
        blockchain["current_block_start"] = time.time()
        
        # Adjust difficulty
        adjust_difficulty()
        
        print(f"⛏️  Block #{new_block['block_height']} mined! {len(miners)} miners, {actual_minted} RTC")
        
        return new_block

def block_processor_thread():
    """Background thread that processes blocks with dynamic timing"""
    while True:
        time.sleep(30)  # Check every 30 seconds
        
        current_time = time.time()
        dynamic_block_time = calculate_dynamic_block_time()
        
        with blockchain_lock:
            block_age = current_time - blockchain["current_block_start"]
            
        if block_age >= dynamic_block_time:
            print(f"⏰ Block time reached ({block_age:.0f}s >= {dynamic_block_time}s), processing...")
            process_block()

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
        
        # Cap multiplier
        proof['multiplier'] = min(proof['multiplier'], 3.5)
        
        with blockchain_lock:
            current_time = time.time()
            dynamic_block_time = calculate_dynamic_block_time()
            block_age = current_time - blockchain["current_block_start"]
            
            # Check if already submitted
            existing = [p for p in blockchain["pending_proofs"] if p['wallet'] == proof['wallet']]
            if existing:
                return jsonify({
                    "success": False, 
                    "error": "Already submitted proof for this block",
                    "next_block_in": max(0, dynamic_block_time - block_age)
                }), 429
            
            # Add proof to pending
            blockchain["pending_proofs"].append({
                "wallet": proof['wallet'],
                "hardware": proof['hardware'],
                "multiplier": proof['multiplier'],
                "timestamp": current_time
            })
            
            print(f"✅ Proof accepted from {proof['hardware']} ({proof['multiplier']}x)")
            
            return jsonify({
                "success": True,
                "message": "Proof accepted, waiting for block completion",
                "pending_miners": len(blockchain["pending_proofs"]),
                "your_multiplier": proof['multiplier'],
                "block_completes_in": max(0, dynamic_block_time - block_age),
                "estimated_block_time": f"{dynamic_block_time//60}m {dynamic_block_time%60:.0f}s"
            })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/stats')
def get_stats():
    """Get blockchain statistics"""
    with blockchain_lock:
        current_time = time.time()
        dynamic_block_time = calculate_dynamic_block_time()
        block_age = current_time - blockchain["current_block_start"]
        
        return jsonify({
            "chain_id": 2718,
            "blocks": len(blockchain["blocks"]),
            "total_minted": round(blockchain["total_minted"], 2),
            "mining_pool": round(blockchain["mining_pool"], 2),
            "wallets": len(blockchain["wallets"]),
            "pending_proofs": len(blockchain["pending_proofs"]),
            "current_block_age": int(block_age),
            "next_block_in": max(0, int(dynamic_block_time - block_age)),
            "estimated_block_time": f"{dynamic_block_time//60:.0f}m {dynamic_block_time%60:.0f}s",
            "average_block_time": round(blockchain["average_block_time"], 1),
            "latest_block": blockchain["blocks"][-1] if blockchain["blocks"] else None
        })

@app.route('/api/network_info')
def get_network_info():
    """Get detailed network information"""
    with blockchain_lock:
        return jsonify({
            "node_version": "1.2.0-slow",
            "consensus": "Proof of Antiquity",
            "max_supply": 8388608,
            "current_supply": round(blockchain["total_minted"], 2),
            "inflation_rate": "Decreasing",
            "block_time_target": "5-30 minutes (dynamic)",
            "active_miners": len(blockchain["pending_proofs"]),
            "total_miners": len(blockchain["wallets"]),
            "difficulty_adjustment": "Every block",
            "anti_emulation": "Active"
        })

@app.route('/')
def index():
    """Status page"""
    with blockchain_lock:
        pending_details = ""
        if blockchain["pending_proofs"]:
            pending_details = "<h3>Pending Miners:</h3><ul>"
            for p in blockchain["pending_proofs"]:
                pending_details += f"<li>{p['hardware']} ({p['multiplier']}x)</li>"
            pending_details += "</ul>"
        
        current_time = time.time()
        dynamic_block_time = calculate_dynamic_block_time()
        block_age = current_time - blockchain["current_block_start"]
        
        return f"""
        <h1>RustChain Node - Proof of Antiquity (Slow Mining)</h1>
        <h2>Realistic Block Times for Vintage Hardware</h2>
        <p>Chain ID: 2718</p>
        <p>Blocks: {len(blockchain["blocks"])}</p>
        <p>Total Minted: {round(blockchain["total_minted"], 2)} RTC</p>
        <p>Mining Pool: {round(blockchain["mining_pool"], 2)} RTC</p>
        <p>Pending Proofs: {len(blockchain["pending_proofs"])}</p>
        <p>Current Block Age: {int(block_age)}s / {dynamic_block_time}s</p>
        <p>Next Block In: {max(0, int(dynamic_block_time - block_age))}s</p>
        <p>Average Block Time: {blockchain["average_block_time"]:.1f}s</p>
        {pending_details}
        <h3>Dynamic Block Times:</h3>
        <ul>
            <li>No miners: 30 minutes</li>
            <li>1 miner: 10 minutes</li>
            <li>2 miners: 8 minutes</li>
            <li>3+ miners: 5 minutes</li>
        </ul>
        <h3>Network Info:</h3>
        <ul>
            <li>API: /api/stats, /api/network_info</li>
            <li>Mining: /api/mine (POST)</li>
        </ul>
        """

# Initialize
blockchain["current_block_start"] = time.time()

# Start block processor thread
processor = Thread(target=block_processor_thread, daemon=True)
processor.start()

if __name__ == '__main__':
    print("🔥 RustChain Node - Slow Mining Edition")
    print("⏰ Dynamic block times: 5-30 minutes")
    print("🎯 Realistic mining for vintage hardware")
    print("🌐 Starting on port 8085...")
    app.run(host='0.0.0.0', port=8085, debug=False)