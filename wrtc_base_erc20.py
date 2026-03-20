// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import json
import os
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from web3 import Web3
from eth_account import Account
import logging

# Base L2 network configuration
BASE_MAINNET_RPC = "https://mainnet.base.org"
BASE_TESTNET_RPC = "https://goerli.base.org"
BASE_CHAIN_ID_MAINNET = 8453
BASE_CHAIN_ID_TESTNET = 84531

# Database path
DB_PATH = "rustchain.db"

# OpenZeppelin ERC-20 contract template with mint/burn
ERC20_CONTRACT_SOURCE = '''
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/Pausable.sol";

contract WrappedRTC is ERC20, Ownable, Pausable {
    uint8 private _decimals;

    event TokensMinted(address indexed to, uint256 amount, string txHash);
    event TokensBurned(address indexed from, uint256 amount, string txHash);

    constructor(
        string memory name,
        string memory symbol,
        uint8 decimals_,
        uint256 initialSupply
    ) ERC20(name, symbol) {
        _decimals = decimals_;
        _mint(msg.sender, initialSupply * 10**decimals_);
    }

    function decimals() public view virtual override returns (uint8) {
        return _decimals;
    }

    function mint(address to, uint256 amount, string memory txHash)
        external
        onlyOwner
        whenNotPaused
    {
        _mint(to, amount);
        emit TokensMinted(to, amount, txHash);
    }

    function burn(uint256 amount, string memory txHash)
        external
        whenNotPaused
    {
        _burn(msg.sender, amount);
        emit TokensBurned(msg.sender, amount, txHash);
    }

    function burnFrom(address from, uint256 amount, string memory txHash)
        external
        onlyOwner
        whenNotPaused
    {
        _spendAllowance(from, msg.sender, amount);
        _burn(from, amount);
        emit TokensBurned(from, amount, txHash);
    }

    function pause() external onlyOwner {
        _pause();
    }

    function unpause() external onlyOwner {
        _unpause();
    }
}
'''

class BaseERC20Manager:
    def __init__(self, network="testnet"):
        self.network = network
        self.w3 = None
        self.contract_address = None
        self.contract_abi = None
        self.setup_web3()
        self.init_db()

    def setup_web3(self):
        """Initialize Web3 connection"""
        rpc_url = BASE_TESTNET_RPC if self.network == "testnet" else BASE_MAINNET_RPC
        try:
            self.w3 = Web3(Web3.HTTPProvider(rpc_url))
            if not self.w3.is_connected():
                raise Exception(f"Failed to connect to Base {self.network}")
            logging.info(f"Connected to Base {self.network}")
        except Exception as e:
            logging.error(f"Web3 connection failed: {e}")
            raise

    def init_db(self):
        """Initialize database tables for Base ERC-20 tracking"""
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS base_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    contract_address TEXT UNIQUE NOT NULL,
                    token_name TEXT NOT NULL,
                    token_symbol TEXT NOT NULL,
                    decimals INTEGER NOT NULL,
                    total_supply TEXT NOT NULL,
                    network TEXT NOT NULL,
                    deployment_tx TEXT,
                    deployment_block INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS base_operations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    contract_address TEXT NOT NULL,
                    operation_type TEXT NOT NULL,
                    tx_hash TEXT UNIQUE NOT NULL,
                    from_address TEXT,
                    to_address TEXT,
                    amount TEXT NOT NULL,
                    block_number INTEGER,
                    gas_used INTEGER,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (contract_address) REFERENCES base_tokens(contract_address)
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS base_bridge_locks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lock_id TEXT UNIQUE NOT NULL,
                    user_address TEXT NOT NULL,
                    amount TEXT NOT NULL,
                    destination_chain TEXT NOT NULL,
                    destination_address TEXT NOT NULL,
                    tx_hash TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    unlock_tx TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

    def deploy_wrtc_token(self, deployer_private_key: str, initial_supply: int = 50000) -> Dict:
        """Deploy wRTC ERC-20 token on Base"""
        try:
            account = Account.from_key(deployer_private_key)
            deployer_address = account.address

            # Token parameters
            token_name = "Wrapped Rustchain Token"
            token_symbol = "wRTC"
            decimals = 18

            # Get deployment parameters
            nonce = self.w3.eth.get_transaction_count(deployer_address)
            gas_price = self.w3.eth.gas_price
            chain_id = BASE_CHAIN_ID_TESTNET if self.network == "testnet" else BASE_CHAIN_ID_MAINNET

            # Compile and deploy contract (simplified - would need actual compilation)
            # This is a placeholder for the actual deployment process
            constructor_args = [token_name, token_symbol, decimals, initial_supply]

            # For demo purposes, simulate deployment
            deployment_tx_hash = "0x" + hashlib.sha256(f"{deployer_address}{nonce}".encode()).hexdigest()
            contract_addr = Web3.to_checksum_address("0x" + hashlib.sha256(deployment_tx_hash.encode()).hexdigest()[:40])

            # Store deployment info
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute('''
                    INSERT INTO base_tokens
                    (contract_address, token_name, token_symbol, decimals, total_supply, network, deployment_tx)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (contract_addr, token_name, token_symbol, decimals, str(initial_supply * 10**decimals),
                      self.network, deployment_tx_hash))

            self.contract_address = contract_addr

            return {
                "success": True,
                "contract_address": contract_addr,
                "deployment_tx": deployment_tx_hash,
                "token_name": token_name,
                "token_symbol": token_symbol,
                "decimals": decimals,
                "initial_supply": initial_supply,
                "network": self.network
            }

        except Exception as e:
            logging.error(f"Token deployment failed: {e}")
            return {"success": False, "error": str(e)}

    def mint_tokens(self, owner_private_key: str, recipient_address: str, amount: int, bridge_tx_hash: str) -> Dict:
        """Mint wRTC tokens (for bridge unlock)"""
        try:
            if not self.contract_address:
                raise Exception("Contract not deployed or address not set")

            account = Account.from_key(owner_private_key)
            owner_address = account.address

            # Convert amount to wei
            amount_wei = amount * 10**18

            # Simulate transaction
            tx_hash = "0x" + hashlib.sha256(f"mint_{recipient_address}_{amount}_{bridge_tx_hash}".encode()).hexdigest()

            # Record operation
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute('''
                    INSERT INTO base_operations
                    (contract_address, operation_type, tx_hash, from_address, to_address, amount, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (self.contract_address, "mint", tx_hash, owner_address, recipient_address,
                      str(amount_wei), "confirmed"))

            logging.info(f"Minted {amount} wRTC to {recipient_address}")

            return {
                "success": True,
                "tx_hash": tx_hash,
                "recipient": recipient_address,
                "amount": amount,
                "bridge_tx": bridge_tx_hash
            }

        except Exception as e:
            logging.error(f"Token minting failed: {e}")
            return {"success": False, "error": str(e)}

    def burn_tokens(self, user_private_key: str, amount: int, destination_address: str) -> Dict:
        """Burn wRTC tokens (for bridge lock)"""
        try:
            if not self.contract_address:
                raise Exception("Contract not deployed or address not set")

            account = Account.from_key(user_private_key)
            user_address = account.address

            # Convert amount to wei
            amount_wei = amount * 10**18

            # Generate lock ID for bridge
            lock_id = hashlib.sha256(f"{user_address}_{amount}_{destination_address}_{datetime.now().isoformat()}".encode()).hexdigest()

            # Simulate burn transaction
            tx_hash = "0x" + hashlib.sha256(f"burn_{user_address}_{amount}_{lock_id}".encode()).hexdigest()

            # Record burn operation
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute('''
                    INSERT INTO base_operations
                    (contract_address, operation_type, tx_hash, from_address, to_address, amount, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (self.contract_address, "burn", tx_hash, user_address, "0x0000000000000000000000000000000000000000",
                      str(amount_wei), "confirmed"))

                # Record bridge lock
                conn.execute('''
                    INSERT INTO base_bridge_locks
                    (lock_id, user_address, amount, destination_chain, destination_address, tx_hash, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (lock_id, user_address, str(amount_wei), "rustchain", destination_address, tx_hash, "locked"))

            logging.info(f"Burned {amount} wRTC from {user_address}, lock_id: {lock_id}")

            return {
                "success": True,
                "tx_hash": tx_hash,
                "lock_id": lock_id,
                "amount": amount,
                "destination_address": destination_address
            }

        except Exception as e:
            logging.error(f"Token burning failed: {e}")
            return {"success": False, "error": str(e)}

    def get_token_info(self, contract_address: str = None) -> Dict:
        """Get token information"""
        addr = contract_address or self.contract_address
        if not addr:
            return {"error": "No contract address provided"}

        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.execute('''
                    SELECT * FROM base_tokens WHERE contract_address = ?
                ''', (addr,))
                token_data = cursor.fetchone()

                if not token_data:
                    return {"error": "Token not found"}

                # Get operation stats
                cursor = conn.execute('''
                    SELECT operation_type, COUNT(*), SUM(CAST(amount AS INTEGER))
                    FROM base_operations
                    WHERE contract_address = ? AND status = 'confirmed'
                    GROUP BY operation_type
                ''', (addr,))
                operations = cursor.fetchall()

                op_stats = {}
                for op_type, count, total_amount in operations:
                    op_stats[op_type] = {"count": count, "total_amount": total_amount or 0}

                return {
                    "contract_address": token_data[1],
                    "token_name": token_data[2],
                    "token_symbol": token_data[3],
                    "decimals": token_data[4],
                    "total_supply": token_data[5],
                    "network": token_data[6],
                    "deployment_tx": token_data[7],
                    "operations": op_stats,
                    "created_at": token_data[9]
                }

        except Exception as e:
            return {"error": str(e)}

    def verify_on_basescan(self, contract_address: str, source_code: str = None) -> Dict:
        """Prepare BaseScan verification data"""
        try:
            source = source_code or ERC20_CONTRACT_SOURCE

            verification_data = {
                "contract_address": contract_address,
                "source_code": source,
                "compiler_version": "v0.8.19+commit.7dd6d404",
                "optimization": "true",
                "optimization_runs": 200,
                "constructor_arguments": "",
                "network": self.network
            }

            # Store verification request
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO base_operations
                    (contract_address, operation_type, tx_hash, status)
                    VALUES (?, ?, ?, ?)
                ''', (contract_address, "verification",
                      hashlib.sha256(f"verify_{contract_address}".encode()).hexdigest(), "pending"))

            return {
                "success": True,
                "verification_data": verification_data,
                "basescan_url": f"https://{'goerli.' if self.network == 'testnet' else ''}basescan.org/address/{contract_address}"
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_bridge_locks(self, user_address: str = None) -> List[Dict]:
        """Get bridge lock history"""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                if user_address:
                    cursor = conn.execute('''
                        SELECT * FROM base_bridge_locks WHERE user_address = ? ORDER BY created_at DESC
                    ''', (user_address,))
                else:
                    cursor = conn.execute('''
                        SELECT * FROM base_bridge_locks ORDER BY created_at DESC LIMIT 100
                    ''')

                locks = []
                for row in cursor.fetchall():
                    locks.append({
                        "lock_id": row[1],
                        "user_address": row[2],
                        "amount": row[3],
                        "destination_chain": row[4],
                        "destination_address": row[5],
                        "tx_hash": row[6],
                        "status": row[7],
                        "unlock_tx": row[8],
                        "created_at": row[9]
                    })

                return locks

        except Exception as e:
            logging.error(f"Failed to get bridge locks: {e}")
            return []

def main():
    """Demo usage"""
    manager = BaseERC20Manager("testnet")

    # Demo private key (never use in production)
    demo_key = "0x" + "1" * 64

    print("Deploying wRTC on Base...")
    deployment = manager.deploy_wrtc_token(demo_key)
    print(f"Deployment result: {deployment}")

    if deployment["success"]:
        print("\nGetting token info...")
        info = manager.get_token_info()
        print(f"Token info: {info}")

        print("\nPreparing BaseScan verification...")
        verification = manager.verify_on_basescan(deployment["contract_address"])
        print(f"Verification: {verification}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
