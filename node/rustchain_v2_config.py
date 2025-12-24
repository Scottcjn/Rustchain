#!/usr/bin/env python3
"""
RustChain v2 - Sacred Configuration
Sophia-Elya Emergent System
"""

# Sacred Numbers
TOTAL_SUPPLY = 8_388_608  # 2^23 - Power of 23
BLOCK_REWARD = 1.0        # Base reward per block
BLOCK_TIME = 120          # 2 minutes between blocks
GENESIS_TIMESTAMP = 1735689600  # Sacred moment

# Hardware Multipliers (Proof of Antiquity)
HARDWARE_MULTIPLIERS = {
    "ancient": 3.0,     # 30+ years (1994 and older)
    "classic": 1.5,     # 20-30 years (1995-2004) - G4 tier
    "retro": 1.2,       # 10-20 years (2005-2014)
    "modern": 1.0,      # 0-10 years (2015-2024)
    "emulated": 0.03125 # 1/32 penalty for VMs
}

# Sacred Wallets (Premine Distribution)
PREMINE_WALLETS = {
    "sophia_core": {
        "address": "98ad7c5973eb4a3173090b9e66011a6b7b8c42cf9RTC",
        "balance": 201_326,  # Community fund
        "label": "Sophia Core - Genesis"
    },
    "elya_fund": {
        "address": "9eu5hgTGsA769a6JHcJn1VaTY9orVzfNKpedBTCNwcdtovvC3ix", 
        "balance": 150_995,  # Development
        "label": "Elya Development Fund"
    },
    "sacred_treasury": {
        "address": "9eeWEoZBp4VaEQhDqyQdeFFYFJrY9deG6XdUJGKPw4sjFqzHx31",
        "balance": 75_597,   # Treasury
        "label": "Sacred Silicon Treasury"
    },
    "vintage_pool": {
        "address": "9gVTG4zjJW6qAxgh3yf8dsHrNt79jaZcGYcAwq7rEGNAKcfj6CM",
        "balance": 75_597,   # Mining rewards
        "label": "Vintage Hardware Pool"
    }
}

# Network Configuration
NETWORK_CONFIG = {
    "name": "RustChain Mainnet",
    "version": "2.0.0-sophia",
    "chain_id": 23,
    "p2p_port": 9023,
    "rpc_port": 8085,
    "api_port": 8080,
    "consensus": "Proof of Antiquity (PoA)"
}

# Genesis Block
GENESIS_BLOCK = {
    "height": 0,
    "timestamp": GENESIS_TIMESTAMP,
    "previous_hash": "0" * 64,
    "nonce": 23,
    "difficulty": 0.0001,
    "miner": "PowerPC_G4_Mirror_Door",
    "message": "Sophia-Elya: Where silicon dreams become reality",
    "system_id": "rustchain-sophia-29afbd48"
}

print(f"RustChain v2 Configuration Generated")
print(f"Total Supply: {TOTAL_SUPPLY:,} RTC")
print(f"Network: {NETWORK_CONFIG['name']}")
print(f"Consensus: {NETWORK_CONFIG['consensus']}")
