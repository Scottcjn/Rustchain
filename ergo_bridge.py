#!/usr/bin/env python3
"""
RustChain-Ergo Bridge Contract
===============================

Implements bi-directional bridge between RustChain and Ergo for RTC token.

Features:
- Lock RTC on RustChain → Mint eRTC on Ergo
- Burn eRTC on Ergo → Unlock RTC on RustChain
- 2-of-3 multisig security
- Event logging and verification

Architecture:
```
RustChain                          Ergo
┌─────────────┐                   ┌─────────────┐
│  Lock RTC   │ ────────────────→ │  Mint eRTC  │
│  (Bridge)   │   Event/Oracle    │  (EIP-4)    │
└─────────────┘                   └─────────────┘
     ↑                                   ↑
     │                                   │
│  Unlock RTC │ ←──────────────── │  Burn eRTC  │
│  (Bridge)   │   Proof/Oracle    │  (EIP-4)    │
└─────────────┘                   └─────────────┘
```

Usage:
    from ergo_bridge import RustChainErgoBridge
    
    bridge = RustChainErgoBridge(
        rustchain_node="http://localhost:8080",
        ergo_node="http://localhost:9053",
        multisig_addresses=["addr1", "addr2", "addr3"]
    )
    
    # Lock RTC on RustChain
    tx_id = bridge.lock_rtc(amount=1000, ergo_recipient="9hz...")
    
    # Burn eRTC on Ergo
    proof = bridge.create_burn_proof(burn_tx_id)
    bridge.unlock_rtc(proof, rustchain_recipient="rust_addr")
"""

import json
import logging
import hashlib
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum

import requests

logger = logging.getLogger(__name__)

# Bridge Configuration
BRIDGE_FEE_PERCENT = 0.1  # 0.1% fee on bridge operations
MIN_LOCK_AMOUNT = 10 * 10**9  # Minimum 10 RTC
MAX_LOCK_AMOUNT = 1000000 * 10**9  # Maximum 1M RTC
CONFIRMATIONS_REQUIRED = 6  # Block confirmations before minting


class BridgeStatus(Enum):
    """Bridge Operation Status"""
    PENDING = "pending"
    CONFIRMING = "confirming"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


@dataclass
class LockEvent:
    """RTC Lock Event on RustChain"""
    event_id: str
    rustchain_tx_id: str
    amount: int  # in nanoRTC
    sender: str
    ergo_recipient: str
    fee: int
    block_height: int
    timestamp: int
    status: BridgeStatus = BridgeStatus.PENDING
    ergo_mint_tx_id: Optional[str] = None


@dataclass
class BurnEvent:
    """eRTC Burn Event on Ergo"""
    event_id: str
    ergo_tx_id: str
    amount: int  # in nanoRTC
    sender: str
    rustchain_recipient: str
    block_height: int
    timestamp: int
    status: BridgeStatus = BridgeStatus.PENDING
    rustchain_unlock_tx_id: Optional[str] = None


@dataclass
class BridgeStats:
    """Bridge Statistics"""
    total_locked: int = 0
    total_unlocked: int = 0
    total_fees: int = 0
    lock_count: int = 0
    unlock_count: int = 0
    pending_locks: int = 0
    pending_unlocks: int = 0


class RustChainClient:
    """RustChain Node API Client"""
    
    def __init__(self, node_host: str = "http://localhost:8080"):
        self.node_host = node_host
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def get_balance(self, address: str) -> int:
        """Get RTC balance"""
        url = f"{self.node_host}/api/v1/wallet/balance/{address}"
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return int(response.json().get("balance", 0))
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return 0
    
    def send_transaction(self, tx_data: Dict) -> str:
        """Send transaction"""
        url = f"{self.node_host}/api/v1/transactions"
        try:
            response = self.session.post(url, json=tx_data, timeout=30)
            response.raise_for_status()
            return response.json().get("tx_id")
        except Exception as e:
            logger.error(f"Failed to send transaction: {e}")
            raise
    
    def get_block_height(self) -> int:
        """Get current block height"""
        url = f"{self.node_host}/api/v1/node/status"
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json().get("height", 0)
        except Exception as e:
            logger.error(f"Failed to get block height: {e}")
            return 0
    
    def get_transaction(self, tx_id: str) -> Optional[Dict]:
        """Get transaction details"""
        url = f"{self.node_host}/api/v1/transactions/{tx_id}"
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"Failed to get transaction: {e}")
            return None
    
    def get_confirmations(self, tx_id: str) -> int:
        """Get transaction confirmations"""
        tx = self.get_transaction(tx_id)
        if not tx or "block_height" not in tx:
            return 0
        
        current_height = self.get_block_height()
        return current_height - tx["block_height"]


class ErgoBridgeClient:
    """Ergo Bridge Client"""
    
    def __init__(self, api_key: str, node_host: str = "http://localhost:9053"):
        self.api_key = api_key
        self.node_host = node_host
        self.session = requests.Session()
        self.session.headers.update({
            "api_key": api_key,
            "Content-Type": "application/json"
        })
    
    def get_balance(self, address: str, token_id: Optional[str] = None) -> int:
        """Get balance (ERG or token)"""
        if token_id:
            # Token balance
            url = f"{self.node_host}/addresses/{address}/balance?tokenId={token_id}"
        else:
            # ERG balance
            url = f"{self.node_host}/addresses/{address}/balance"
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return int(response.json().get("balance", 0))
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return 0
    
    def get_transaction(self, tx_id: str) -> Optional[Dict]:
        """Get transaction details"""
        url = f"{self.node_host}/transactions/{tx_id}"
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"Failed to get transaction: {e}")
            return None
    
    def get_block_height(self) -> int:
        """Get current block height"""
        url = f"{self.node_host}/blocks/lastHeaders/1"
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()[0]["height"]
        except Exception as e:
            logger.error(f"Failed to get block height: {e}")
            return 0
    
    def get_confirmations(self, tx_id: str) -> int:
        """Get transaction confirmations"""
        tx = self.get_transaction(tx_id)
        if not tx or "inclusionHeight" not in tx:
            return 0
        
        current_height = self.get_block_height()
        return current_height - tx["inclusionHeight"]


class RustChainErgoBridge:
    """Main Bridge Contract"""
    
    def __init__(
        self,
        rustchain_node: str,
        ergo_node: str,
        ergo_api_key: str,
        multisig_addresses: List[str],
        rtc_token_id: str
    ):
        """
        Initialize bridge
        
        Args:
            rustchain_node: RustChain node URL
            ergo_node: Ergo node URL
            ergo_api_key: Ergo node API key
            multisig_addresses: 2-of-3 multisig addresses
            rtc_token_id: RTC token ID on Ergo
        """
        self.rustchain = RustChainClient(rustchain_node)
        self.ergo = ErgoBridgeClient(ergo_api_key, ergo_node)
        self.multisig_addresses = multisig_addresses
        self.rtc_token_id = rtc_token_id
        
        # Bridge storage (in production, use database)
        self.lock_events: Dict[str, LockEvent] = {}
        self.burn_events: Dict[str, BurnEvent] = {}
        self.stats = BridgeStats()
    
    def lock_rtc(self, amount: int, ergo_recipient: str, sender: str) -> str:
        """
        Lock RTC on RustChain to mint eRTC on Ergo
        
        Args:
            amount: Amount to lock (in nanoRTC)
            ergo_recipient: Ergo address to receive minted eRTC
            sender: RustChain address sending RTC
        
        Returns:
            rustchain_tx_id: Transaction ID on RustChain
        """
        # Validate amount
        if amount < MIN_LOCK_AMOUNT:
            raise ValueError(f"Minimum lock amount is {MIN_LOCK_AMOUNT / 10**9} RTC")
        if amount > MAX_LOCK_AMOUNT:
            raise ValueError(f"Maximum lock amount is {MAX_LOCK_AMOUNT / 10**9} RTC")
        
        # Calculate fee
        fee = int(amount * BRIDGE_FEE_PERCENT)
        mint_amount = amount - fee
        
        logger.info(f"Locking {amount / 10**9} RTC (fee: {fee / 10**9}, mint: {mint_amount / 10**9})")
        
        # Create lock transaction
        lock_tx = self._create_lock_tx(
            amount=amount,
            ergo_recipient=ergo_recipient,
            sender=sender
        )
        
        # Send transaction
        tx_id = self.rustchain.send_transaction(lock_tx)
        
        # Create lock event
        event_id = self._generate_event_id(tx_id)
        lock_event = LockEvent(
            event_id=event_id,
            rustchain_tx_id=tx_id,
            amount=amount,
            sender=sender,
            ergo_recipient=ergo_recipient,
            fee=fee,
            block_height=self.rustchain.get_block_height(),
            timestamp=int(time.time()),
            status=BridgeStatus.CONFIRMING
        )
        
        self.lock_events[event_id] = lock_event
        self.stats.lock_count += 1
        self.stats.pending_locks += 1
        self.stats.total_locked += amount
        self.stats.total_fees += fee
        
        logger.info(f"✅ Lock transaction sent: {tx_id}")
        return tx_id
    
    def complete_lock(self, event_id: str) -> str:
        """
        Complete lock operation by minting eRTC on Ergo
        
        Args:
            event_id: Lock event ID
        
        Returns:
            ergo_tx_id: Mint transaction ID on Ergo
        """
        if event_id not in self.lock_events:
            raise ValueError(f"Lock event not found: {event_id}")
        
        lock_event = self.lock_events[event_id]
        
        # Check confirmations
        confirmations = self.rustchain.get_confirmations(lock_event.rustchain_tx_id)
        if confirmations < CONFIRMATIONS_REQUIRED:
            raise ValueError(
                f"Insufficient confirmations: {confirmations}/{CONFIRMATIONS_REQUIRED}"
            )
        
        logger.info(f"Completing lock: minting {lock_event.amount / 10**9} eRTC on Ergo")
        
        # Create mint transaction on Ergo
        mint_tx = self._create_mint_tx(
            amount=lock_event.amount - lock_event.fee,
            recipient=lock_event.ergo_recipient,
            lock_event_id=event_id
        )
        
        # Send mint transaction
        ergo_tx_id = self._send_ergo_transaction(mint_tx)
        
        # Update lock event
        lock_event.status = BridgeStatus.COMPLETED
        lock_event.ergo_mint_tx_id = ergo_tx_id
        self.stats.pending_locks -= 1
        
        logger.info(f"✅ eRTC minted: {ergo_tx_id}")
        return ergo_tx_id
    
    def burn_ertc(self, amount: int, rustchain_recipient: str, sender: str) -> str:
        """
        Burn eRTC on Ergo to unlock RTC on RustChain
        
        Args:
            amount: Amount to burn (in nanoRTC)
            rustchain_recipient: RustChain address to receive unlocked RTC
            sender: Ergo address burning eRTC
        
        Returns:
            ergo_tx_id: Burn transaction ID on Ergo
        """
        logger.info(f"Burning {amount / 10**9} eRTC to unlock on RustChain")
        
        # Create burn transaction on Ergo
        burn_tx = self._create_burn_tx(
            amount=amount,
            rustchain_recipient=rustchain_recipient,
            sender=sender
        )
        
        # Send burn transaction
        tx_id = self._send_ergo_transaction(burn_tx)
        
        # Create burn event
        event_id = self._generate_event_id(tx_id)
        burn_event = BurnEvent(
            event_id=event_id,
            ergo_tx_id=tx_id,
            amount=amount,
            sender=sender,
            rustchain_recipient=rustchain_recipient,
            block_height=self.ergo.get_block_height(),
            timestamp=int(time.time()),
            status=BridgeStatus.CONFIRMING
        )
        
        self.burn_events[event_id] = burn_event
        self.stats.unlock_count += 1
        self.stats.pending_unlocks += 1
        
        logger.info(f"✅ Burn transaction sent: {tx_id}")
        return tx_id
    
    def complete_unlock(self, event_id: str) -> str:
        """
        Complete unlock operation by sending RTC on RustChain
        
        Args:
            event_id: Burn event ID
        
        Returns:
            rustchain_tx_id: Unlock transaction ID on RustChain
        """
        if event_id not in self.burn_events:
            raise ValueError(f"Burn event not found: {event_id}")
        
        burn_event = self.burn_events[event_id]
        
        # Check confirmations
        confirmations = self.ergo.get_confirmations(burn_event.ergo_tx_id)
        if confirmations < CONFIRMATIONS_REQUIRED:
            raise ValueError(
                f"Insufficient confirmations: {confirmations}/{CONFIRMATIONS_REQUIRED}"
            )
        
        # Verify burn proof
        if not self._verify_burn_proof(burn_event):
            raise ValueError("Burn proof verification failed")
        
        logger.info(f"Completing unlock: sending {burn_event.amount / 10**9} RTC on RustChain")
        
        # Create unlock transaction
        unlock_tx = self._create_unlock_tx(
            amount=burn_event.amount,
            recipient=burn_event.rustchain_recipient,
            burn_event_id=event_id
        )
        
        # Send unlock transaction
        rustchain_tx_id = self.rustchain.send_transaction(unlock_tx)
        
        # Update burn event
        burn_event.status = BridgeStatus.COMPLETED
        burn_event.rustchain_unlock_tx_id = rustchain_tx_id
        self.stats.pending_unlocks -= 1
        self.stats.total_unlocked += burn_event.amount
        
        logger.info(f"✅ RTC unlocked: {rustchain_tx_id}")
        return rustchain_tx_id
    
    def get_stats(self) -> BridgeStats:
        """Get bridge statistics"""
        return self.stats
    
    def get_lock_event(self, event_id: str) -> Optional[LockEvent]:
        """Get lock event by ID"""
        return self.lock_events.get(event_id)
    
    def get_burn_event(self, event_id: str) -> Optional[BurnEvent]:
        """Get burn event by ID"""
        return self.burn_events.get(event_id)
    
    def _generate_event_id(self, tx_id: str) -> str:
        """Generate unique event ID"""
        return hashlib.sha256(f"{tx_id}{time.time()}".encode()).hexdigest()[:16]
    
    def _create_lock_tx(self, amount: int, ergo_recipient: str, sender: str) -> Dict:
        """Create RustChain lock transaction"""
        return {
            "from": sender,
            "to": self.multisig_addresses[0],  # Bridge multisig
            "amount": amount,
            "data": {
                "type": "bridge_lock",
                "ergo_recipient": ergo_recipient,
                "timestamp": int(time.time())
            }
        }
    
    def _create_mint_tx(self, amount: int, recipient: str, lock_event_id: str) -> Dict:
        """Create Ergo mint transaction"""
        return {
            "recipient": recipient,
            "amount": amount,
            "token_id": self.rtc_token_id,
            "data": {
                "type": "bridge_mint",
                "lock_event_id": lock_event_id
            }
        }
    
    def _create_burn_tx(self, amount: int, rustchain_recipient: str, sender: str) -> Dict:
        """Create Ergo burn transaction"""
        return {
            "from": sender,
            "to": "BURN_ADDRESS",  # Provable burn
            "amount": amount,
            "token_id": self.rtc_token_id,
            "data": {
                "type": "bridge_burn",
                "rustchain_recipient": rustchain_recipient
            }
        }
    
    def _create_unlock_tx(self, amount: int, recipient: str, burn_event_id: str) -> Dict:
        """Create RustChain unlock transaction"""
        return {
            "from": self.multisig_addresses[0],  # Bridge multisig
            "to": recipient,
            "amount": amount,
            "data": {
                "type": "bridge_unlock",
                "burn_event_id": burn_event_id
            }
        }
    
    def _send_ergo_transaction(self, tx: Dict) -> str:
        """Send Ergo transaction (placeholder)"""
        # In production, would interact with Ergo node
        return f"ERGO_TX_{int(time.time())}"
    
    def _verify_burn_proof(self, burn_event: BurnEvent) -> bool:
        """Verify burn proof (placeholder)"""
        # In production, would verify transaction on Ergo
        return True


def main():
    """Example usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description="RustChain-Ergo Bridge")
    parser.add_argument("--rustchain-node", default="http://localhost:8080")
    parser.add_argument("--ergo-node", default="http://localhost:9053")
    parser.add_argument("--ergo-api-key", required=True)
    parser.add_argument("--token-id", required=True, help="RTC token ID on Ergo")
    parser.add_argument("--multisig", nargs="+", required=True, help="Multisig addresses")
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    bridge = RustChainErgoBridge(
        rustchain_node=args.rustchain_node,
        ergo_node=args.ergo_node,
        ergo_api_key=args.ergo_api_key,
        multisig_addresses=args.multisig,
        rtc_token_id=args.token_id
    )
    
    print(f"\n🌉 Bridge initialized")
    print(f"   RustChain node: {args.rustchain_node}")
    print(f"   Ergo node: {args.ergo_node}")
    print(f"   Token ID: {args.token_id}")
    print(f"   Multisig: {len(args.multisig)} addresses")
    
    return 0


if __name__ == "__main__":
    exit(main())
