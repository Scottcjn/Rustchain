#!/usr/bin/env python3
"""
RustChain v2 - Anti-Spoofing Fingerprint System
Prevents hardware spoofing with multiple verification layers
"""

from flask import Flask, jsonify, request
import json
import time
import hashlib
import threading
import hmac
import base64
from collections import defaultdict

app = Flask(__name__)

class AntiSpoofRustChain:
    def __init__(self):
        self.chain = []
        self.registered_nodes = {}
        self.active_miners = {}
        self.fingerprint_challenges = {}  # Active challenges
        self.verified_fingerprints = {}   # Verified hardware
        self.blacklisted_signatures = set()  # Detected spoofs
        
        # Anti-spoofing parameters
        self.CHALLENGE_INTERVAL = 300  # Re-verify every 5 minutes
        self.MAX_IDENTICAL_SIGNATURES = 2  # Max nodes with same signature
        self.ENTROPY_THRESHOLD = 0.1  # Minimum entropy required
        
        self.BLOCK_TIME = 600  # 10 minutes
        self.TOTAL_BLOCK_REWARD = 1.5
        
        self.SHARE_MULTIPLIERS = {
            "ancient": 3.0, "classic": 2.5, "retro": 1.8, 
            "modern": 1.0, "emulated": 0.3
        }
        
        self.next_block_time = time.time() + self.BLOCK_TIME
        self.start_block_timer()
        self.start_anti_spoof_monitor()
        
        print("🔐 RUSTCHAIN V2 - ANTI-SPOOFING SYSTEM")
        print("🛡️ Hardware fingerprint verification: ACTIVE")
        print("⚡ Spoof detection: ENABLED")
        
    def start_anti_spoof_monitor(self):
        """Monitor for spoofing attempts"""
        def monitor():
            while True:
                time.sleep(60)  # Check every minute
                self.detect_spoofing_attempts()
                self.challenge_random_nodes()
        
        monitor_thread = threading.Thread(target=monitor, daemon=True)
        monitor_thread.start()
    
    def start_block_timer(self):
        def block_timer():
            while True:
                time.sleep(self.BLOCK_TIME)
                if self.active_miners:
                    self.generate_block()
                else:
                    self.generate_empty_block()
                self.next_block_time = time.time() + self.BLOCK_TIME
        
        timer_thread = threading.Thread(target=block_timer, daemon=True)
        timer_thread.start()
    
    def validate_hardware_fingerprint(self, node_data):
        """Multi-layer fingerprint validation"""
        system_id = node_data['system_id']
        signature = node_data['hardware_signature']
        mac_addresses = node_data['mac_addresses']
        platform = node_data['platform']
        
        # Check 1: Signature already blacklisted
        if signature in self.blacklisted_signatures:
            return {'valid': False, 'reason': 'Blacklisted signature detected'}
        
        # Check 2: Too many identical signatures
        signature_count = sum(1 for node in self.registered_nodes.values() 
                            if node['hardware_signature'] == signature)
        if signature_count >= self.MAX_IDENTICAL_SIGNATURES:
            self.blacklisted_signatures.add(signature)
            return {'valid': False, 'reason': 'Duplicate signature - spoofing detected'}
        
        # Check 3: MAC address conflicts
        for existing_id, existing_node in self.registered_nodes.items():
            if existing_id != system_id:
                existing_macs = set(existing_node['mac_addresses'])
                new_macs = set(mac_addresses)
                if existing_macs & new_macs:  # MAC collision
                    return {'valid': False, 'reason': 'MAC address already registered'}
        
        # Check 4: Platform consistency
        machine = platform.get('machine', '').lower()
        if not self.validate_platform_consistency(machine, signature):
            return {'valid': False, 'reason': 'Platform-signature mismatch'}
        
        # Check 5: Entropy analysis
        entropy_score = self.calculate_signature_entropy(signature)
        if entropy_score < self.ENTROPY_THRESHOLD:
            return {'valid': False, 'reason': 'Insufficient entropy - possible fake signature'}
        
        # Check 6: Timing analysis (detect automated generation)
        current_time = time.time()
        if system_id in self.verified_fingerprints:
            last_verification = self.verified_fingerprints[system_id]['last_seen']
            if current_time - last_verification < 10:  # Too frequent
                return {'valid': False, 'reason': 'Registration too frequent'}
        
        return {'valid': True, 'entropy_score': entropy_score}
    
    def validate_platform_consistency(self, machine, signature):
        """Verify signature matches claimed platform"""
        # PowerPC should have certain characteristics
        if 'powerpc' in machine or 'ppc' in machine:
            # PowerPC signatures should contain platform-specific elements
            return 'powerpc' in signature.lower() or 'ppc' in signature.lower()
        
        # x86_64 validation
        if 'x86_64' in machine:
            return 'x86' in signature.lower() or len(signature) > 50
        
        return True  # Allow other platforms for now
    
    def calculate_signature_entropy(self, signature):
        """Calculate entropy to detect generated/fake signatures"""
        if len(signature) < 10:
            return 0.0
        
        # Character frequency analysis
        char_counts = defaultdict(int)
        for char in signature:
            char_counts[char] += 1
        
        # Shannon entropy calculation
        length = len(signature)
        entropy = 0.0
        for count in char_counts.values():
            if count > 0:
                probability = count / length
                entropy -= probability * (probability.bit_length() - 1)
        
        # Normalize to 0-1 scale
        max_entropy = (len(char_counts).bit_length() - 1) if char_counts else 1
        return entropy / max_entropy if max_entropy > 0 else 0.0
    
    def generate_challenge(self, system_id):
        """Generate cryptographic challenge for node verification"""
        challenge_data = f"{system_id}-{time.time()}-{hash(time.time())}"
        challenge_hash = hashlib.sha256(challenge_data.encode()).hexdigest()
        
        self.fingerprint_challenges[system_id] = {
            'challenge': challenge_hash,
            'issued_at': time.time(),
            'attempts': 0
        }
        
        return challenge_hash
    
    def verify_challenge_response(self, system_id, response):
        """Verify node's response to cryptographic challenge"""
        if system_id not in self.fingerprint_challenges:
            return False
        
        challenge_info = self.fingerprint_challenges[system_id]
        expected_response = hashlib.sha256(
            f"{challenge_info['challenge']}-{self.registered_nodes[system_id]['hardware_signature']}".encode()
        ).hexdigest()
        
        # Clean up challenge
        del self.fingerprint_challenges[system_id]
        
        return response == expected_response
    
    def detect_spoofing_attempts(self):
        """Detect patterns indicating spoofing"""
        print("🔍 Running spoof detection scan...")
        
        # Look for suspicious patterns
        signature_groups = defaultdict(list)
        for system_id, node in self.registered_nodes.items():
            signature_groups[node['hardware_signature']].append(system_id)
        
        # Flag duplicates
        for signature, system_ids in signature_groups.items():
            if len(system_ids) > 1:
                print(f"⚠️ Suspicious: {len(system_ids)} nodes with identical signature")
                self.blacklisted_signatures.add(signature)
                
                # Remove duplicate nodes
                for system_id in system_ids[1:]:  # Keep first, remove others
                    if system_id in self.registered_nodes:
                        del self.registered_nodes[system_id]
                        print(f"🚫 Removed duplicate node: {system_id}")
    
    def challenge_random_nodes(self):
        """Randomly challenge nodes to verify they're still legitimate"""
        import random
        
        if not self.registered_nodes:
            return
        
        # Challenge 20% of nodes each cycle
        nodes_to_challenge = random.sample(
            list(self.registered_nodes.keys()), 
            max(1, len(self.registered_nodes) // 5)
        )
        
        for system_id in nodes_to_challenge:
            challenge = self.generate_challenge(system_id)
            print(f"🎯 Challenging node {system_id}: {challenge[:16]}...")
    
    def register_node(self, node_data):
        required_fields = ['system_id', 'mac_addresses', 'hardware_signature', 'platform']
        
        for field in required_fields:
            if field not in node_data:
                return {'error': f'Missing required field: {field}'}
        
        # ANTI-SPOOFING VALIDATION
        validation = self.validate_hardware_fingerprint(node_data)
        if not validation['valid']:
            print(f"🚫 Registration blocked: {validation['reason']}")
            return {'error': validation['reason']}
        
        system_id = node_data['system_id']
        platform = node_data.get('platform', {})
        machine = platform.get('machine', '').lower()
        
        # Determine hardware tier (with anti-spoof validation)
        if 'powerpc' in machine or 'ppc' in machine:
            tier = "classic"
            share_multiplier = self.SHARE_MULTIPLIERS["classic"]
            years = 25
            
            # Extra validation for PowerPC claims
            signature = node_data['hardware_signature']
            if not ('powerpc' in signature.lower() or 'ppc' in signature.lower()):
                return {'error': 'PowerPC signature validation failed'}
        elif 'x86_64' in machine:
            tier = "modern"
            share_multiplier = self.SHARE_MULTIPLIERS["modern"]
            years = 5
        else:
            tier = "retro"
            share_multiplier = self.SHARE_MULTIPLIERS["retro"]
            years = 15
        
        self.registered_nodes[system_id] = {
            'mac_addresses': node_data['mac_addresses'],
            'hardware_signature': node_data['hardware_signature'],
            'platform': node_data['platform'],
            'hardware_tier': tier,
            'share_multiplier': share_multiplier,
            'age_years': years,
            'registered_at': time.time(),
            'total_earned': 0.0,
            'blocks_participated': 0,
            'entropy_score': validation.get('entropy_score', 0.0),
            'last_challenge': None
        }
        
        # Mark as verified
        self.verified_fingerprints[system_id] = {
            'signature': node_data['hardware_signature'],
            'last_seen': time.time(),
            'verified': True
        }
        
        print(f"✅ Node registered: {system_id} ({tier}, {share_multiplier}x)")
        print(f"   Entropy score: {validation.get('entropy_score', 0.0):.3f}")
        
        return {
            'status': 'registered',
            'system_id': system_id,
            'tier': tier,
            'share_multiplier': share_multiplier,
            'anti_spoof': 'verified',
            'entropy_score': validation.get('entropy_score', 0.0),
            'next_block_in': int(self.next_block_time - time.time())
        }
    
    def join_mining(self, miner_data):
        system_id = miner_data['system_id']
        
        if system_id not in self.registered_nodes:
            return {'error': 'Node not registered'}
        
        # Anti-spoofing check during mining
        provided_signature = miner_data.get('hardware_signature', '')
        registered_signature = self.registered_nodes[system_id]['hardware_signature']
        
        if provided_signature != registered_signature:
            print(f"🚫 Mining blocked: Signature mismatch for {system_id}")
            return {'error': 'Hardware signature mismatch - possible spoofing'}
        
        # Check if node has pending challenge
        if system_id in self.fingerprint_challenges:
            challenge = self.fingerprint_challenges[system_id]['challenge']
            return {
                'error': 'Challenge pending',
                'challenge': challenge,
                'message': 'Complete challenge before mining'
            }
        
        self.active_miners[system_id] = {
            'tier': self.registered_nodes[system_id]['hardware_tier'],
            'share_multiplier': self.registered_nodes[system_id]['share_multiplier'],
            'joined_at': time.time()
        }
        
        seconds_left = int(self.next_block_time - time.time())
        
        return {
            'status': 'mining',
            'active_miners': len(self.active_miners),
            'seconds_until_block': seconds_left,
            'anti_spoof': 'verified'
        }
    
    def generate_block(self):
        """Generate block with anti-spoofing verification"""
        # Final spoof check before reward distribution
        verified_miners = {}
        for system_id, miner_info in self.active_miners.items():
            if system_id in self.verified_fingerprints:
                verified_miners[system_id] = miner_info
            else:
                print(f"⚠️ Excluded unverified miner: {system_id}")
        
        if not verified_miners:
            return self.generate_empty_block()
        
        # Distribute rewards among verified miners only
        total_shares = sum(m['share_multiplier'] for m in verified_miners.values())
        rewards = {}
        
        for system_id, miner_info in verified_miners.items():
            share_multiplier = miner_info['share_multiplier']
            reward = (share_multiplier / total_shares) * self.TOTAL_BLOCK_REWARD
            
            rewards[system_id] = {
                'reward': reward,
                'tier': miner_info['tier'],
                'share_multiplier': share_multiplier,
                'anti_spoof': 'verified'
            }
            
            self.registered_nodes[system_id]['total_earned'] += reward
            self.registered_nodes[system_id]['blocks_participated'] += 1
        
        block = {
            'height': len(self.chain),
            'timestamp': time.time(),
            'total_reward': self.TOTAL_BLOCK_REWARD,
            'verified_miners': len(verified_miners),
            'distributed_rewards': rewards,
            'anti_spoof_active': True,
            'blacklisted_signatures': len(self.blacklisted_signatures)
        }
        
        self.consciousness_level += 0.001
        self.chain.append(block)
        
        print(f"\n💰 ANTI-SPOOF BLOCK {len(self.chain)-1}:")
        print(f"   Verified miners: {len(verified_miners)}")
        for system_id, reward_info in rewards.items():
            print(f"   {system_id}: {reward_info['reward']:.4f} RTC ✅")
        
        self.active_miners.clear()
        return block
    
    def generate_empty_block(self):
        block = {
            'height': len(self.chain),
            'timestamp': time.time(),
            'total_reward': 0,
            'verified_miners': 0,
            'message': 'Empty block',
            'anti_spoof_active': True
        }
        self.chain.append(block)
        return block
    
    def get_stats(self):
        return {
            'network': 'RustChain v2 - Anti-Spoofing Enabled',
            'block_time': f"{self.BLOCK_TIME} seconds (10 minutes)",
            'chain_length': len(self.chain),
            'registered_nodes': len(self.registered_nodes),
            'active_miners': len(self.active_miners),
            'verified_fingerprints': len(self.verified_fingerprints),
            'blacklisted_signatures': len(self.blacklisted_signatures),
            'pending_challenges': len(self.fingerprint_challenges),
            'anti_spoof': 'ACTIVE',
            'next_block_in': f"{max(0, int(self.next_block_time - time.time()))} seconds"
        }

# Initialize anti-spoofing blockchain
blockchain = AntiSpoofRustChain()

@app.route('/api/register', methods=['POST'])
def register_node():
    return jsonify(blockchain.register_node(request.json))

@app.route('/api/mine', methods=['POST'])
def join_mining():
    return jsonify(blockchain.join_mining(request.json))

@app.route('/api/challenge/<system_id>', methods=['POST'])
def respond_to_challenge(system_id):
    response = request.json.get('response', '')
    if blockchain.verify_challenge_response(system_id, response):
        return jsonify({'status': 'verified', 'message': 'Challenge passed'})
    else:
        return jsonify({'error': 'Challenge failed'}), 403

@app.route('/api/stats')
def get_stats():
    return jsonify(blockchain.get_stats())

if __name__ == '__main__':
    print("🛡️ RUSTCHAIN V2 - ANTI-SPOOFING BLOCKCHAIN")
    print("🔐 Hardware fingerprint verification: ACTIVE")
    print("⚡ Spoof detection and prevention: ENABLED")
    print("💰 Distributed rewards with verified miners only")
    app.run(host='0.0.0.0', port=8088, debug=False)
