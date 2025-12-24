#!/usr/bin/env python3
"""
RustChain Node with Proper Reward Splitting
Implements multi-miner block rewards with automatic block processing
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
    "total_minted": 503429.5,
    "mining_pool": 7884178.5,
    "current_block_start": 0
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

def process_block():
    """Process all pending proofs and create new block"""
    with blockchain_lock:
        if not blockchain["pending_proofs"]:
            # No proofs, start new block period
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
        
        # Calculate actual minted (might be less than 1.0 if low multipliers)
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
            "previous_hash": blockchain["blocks"][-1]["hash"] if blockchain["blocks"] else "0"
        }
        
        # Calculate hash
        block_str = json.dumps(new_block, sort_keys=True)
        new_block["hash"] = hashlib.sha256(block_str.encode()).hexdigest()
        
        # Update blockchain
        blockchain["blocks"].append(new_block)
        blockchain["total_minted"] += actual_minted
        blockchain["mining_pool"] -= actual_minted
        blockchain["mining_pool"] += unminted  # Return unminted to pool
        
        # Clear pending proofs
        blockchain["pending_proofs"] = []
        blockchain["current_block_start"] = time.time()
        
        print(f"⛏️  Block #{new_block['block_height']} mined! Reward: {actual_minted} RTC split among {len(miners)} miners")
        
        return new_block

def block_processor_thread():
    """Background thread that processes blocks every 120 seconds"""
    while True:
        time.sleep(10)  # Check every 10 seconds
        current_time = time.time()
        
        with blockchain_lock:
            block_age = current_time - blockchain["current_block_start"]
            
        if block_age >= 120:
            print(f"⏰ Block time reached ({block_age:.0f}s), processing block...")
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
        
        # Cap multiplier at ancient tier
        proof['multiplier'] = min(proof['multiplier'], 3.5)
        
        with blockchain_lock:
            # Check if new block period (2 minutes)
            current_time = time.time()
            block_age = current_time - blockchain["current_block_start"]
            
            if block_age >= 120:
                # Process previous block if any proofs
                process_block()
            
            # Check if miner already submitted for this block
            existing = [p for p in blockchain["pending_proofs"] if p['wallet'] == proof['wallet']]
            if existing:
                return jsonify({
                    "success": False, 
                    "error": "Already submitted proof for this block",
                    "next_block_in": 120 - block_age
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
                "block_completes_in": max(0, 120 - block_age)
            })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/force_block', methods=['POST'])
def force_block():
    """Force process current block (for testing)"""
    block = process_block()
    if block:
        return jsonify({"success": True, "block": block})
    else:
        return jsonify({"success": False, "error": "No pending proofs"})

@app.route('/api/stats')
def get_stats():
    """Get blockchain statistics"""
    with blockchain_lock:
        return jsonify({
            "chain_id": 2718,
            "blocks": len(blockchain["blocks"]),
            "total_minted": round(blockchain["total_minted"], 2),
            "mining_pool": round(blockchain["mining_pool"], 2),
            "wallets": len(blockchain["wallets"]),
            "pending_proofs": len(blockchain["pending_proofs"]),
            "current_block_age": int(time.time() - blockchain["current_block_start"]),
            "next_block_in": max(0, 120 - int(time.time() - blockchain["current_block_start"])),
            "latest_block": blockchain["blocks"][-1] if blockchain["blocks"] else None
        })

@app.route('/api/blocks')
def get_blocks():
    """Get recent blocks"""
    with blockchain_lock:
        return jsonify({
            "blocks": blockchain["blocks"][-10:],
            "total": len(blockchain["blocks"])
        })

@app.route('/api/wallet/<address>')
def get_wallet(address):
    """Get wallet balance"""
    with blockchain_lock:
        if address in blockchain["wallets"]:
            return jsonify({
                "address": address,
                "balance": round(blockchain["wallets"][address]["balance"], 6),
                "hardware": blockchain["wallets"][address].get("hardware", "Unknown")
            })
        else:
            return jsonify({"address": address, "balance": 0.0})

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
        
        block_age = int(time.time() - blockchain["current_block_start"])
        
        return f"""
        <h1>RustChain Node - Proof of Antiquity</h1>
        <h2>With Automatic Block Processing!</h2>
        <p>Chain ID: 2718</p>
        <p>Blocks: {len(blockchain["blocks"])}</p>
        <p>Total Minted: {round(blockchain["total_minted"], 2)} RTC</p>
        <p>Mining Pool: {round(blockchain["mining_pool"], 2)} RTC</p>
        <p>Pending Proofs: {len(blockchain["pending_proofs"])}</p>
        <p>Current Block Age: {block_age}s / 120s</p>
        <p>Next Block In: {max(0, 120 - block_age)}s</p>
        {pending_details}
        <h3>How it works:</h3>
        <ul>
            <li>Miners submit proofs during 120-second window</li>
            <li>Block automatically completes after 120 seconds</li>
            <li>Total reward: 1.0 RTC max per block</li>
            <li>Rewards split proportionally by multipliers</li>
            <li>Example: G4 (1.8x) + 486 (3.5x) = G4 gets 0.34, 486 gets 0.66</li>
        </ul>
        <h3>API Endpoints:</h3>
        <ul>
            <li>/api/stats - Network statistics</li>
            <li>/api/blocks - Recent blocks</li>
            <li>/api/wallet/&lt;address&gt; - Wallet balance</li>
            <li>/api/mine - Submit mining proof (POST)</li>
        </ul>
        """

# Initialize block timer
blockchain["current_block_start"] = time.time()

# Start block processor thread
processor = Thread(target=block_processor_thread, daemon=True)
processor.start()

if __name__ == '__main__':
    print("🔥 RustChain Node - Proof of Antiquity")
    print("⚡ WITH AUTOMATIC BLOCK PROCESSING!")
    print("📍 Chain ID: 2718")
    print("⏰ Blocks process every 120 seconds")
    print("🌐 Starting on port 8085...")
    app.run(host='0.0.0.0', port=8085, debug=False)