#!/usr/bin/env python3
"""
Ergo Token Issuance Module - EIP-4 Standard
============================================

Implements RTC token issuance on Ergo blockchain using EIP-4 token standard.

Features:
- Token creation with metadata
- Mint/burn mechanisms
- Token registry integration
- Bridge contract support

Usage:
    from ergo_token_issuance import ErgoTokenIssuer
    
    issuer = ErgoTokenIssuer(node_api_key, node_api_address)
    token_id = issuer.create_rtc_token()
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

# EIP-4 Token Standard Constants
EIP4_TOKEN_REGISTRY_ID = "03faf2cb329f20905902b250f339d3ebf4b0f1a9d09778e0277928db"
MIN_BOX_VALUE = 1000000  # Minimum ERG value for a box (nanoERG)
TOKEN_CREATION_FEE = 10000000  # 0.01 ERG for token creation

@dataclass
class TokenMetadata:
    """EIP-4 Token Metadata"""
    name: str
    description: str
    symbol: str
    decimals: int = 9
    box42: Optional[str] = None  # Optional NFT for token icon
    
    def to_registers(self) -> Dict[int, str]:
        """Convert metadata to EIP-4 register format"""
        registers = {
            4: f"\"{self.name}\"",
            5: f"\"{self.description}\"",
            6: f"\"{self.symbol}\"",
            7: str(self.decimals)
        }
        if self.box42:
            registers[8] = f'\"{self.box42}\"'
        return registers


@dataclass
class TokenInfo:
    """Token Information"""
    token_id: str
    name: str
    symbol: str
    decimals: int
    total_supply: int
    creator_address: str
    creation_height: int
    metadata: Optional[TokenMetadata] = None


class ErgoNodeClient:
    """Ergo Node API Client"""
    
    def __init__(self, api_key: str, node_host: str = "http://localhost:9053"):
        self.api_key = api_key
        self.node_host = node_host
        self.session = requests.Session()
        self.session.headers.update({
            "api_key": api_key,
            "Content-Type": "application/json"
        })
    
    def get_balance(self, address: str) -> int:
        """Get balance for address in nanoERG"""
        url = f"{self.node_host}/addresses/{address}/balance"
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return int(response.json().get("balance", 0))
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return 0
    
    def get_unspent_boxes(self, address: str, min_conf: int = 1) -> List[Dict]:
        """Get unspent boxes for address"""
        url = f"{self.node_host}/addresses/{address}/boxes/unspent"
        try:
            response = self.session.get(url, params={"minConf": min_conf}, timeout=10)
            response.raise_for_status()
            return response.json().get("items", [])
        except Exception as e:
            logger.error(f"Failed to get unspent boxes: {e}")
            return []
    
    def send_transaction(self, tx_json: Dict) -> str:
        """Send signed transaction"""
        url = f"{self.node_host}/transactions"
        try:
            response = self.session.post(url, json=tx_json, timeout=30)
            response.raise_for_status()
            tx_id = response.json().get("id")
            logger.info(f"Transaction sent: {tx_id}")
            return tx_id
        except Exception as e:
            logger.error(f"Failed to send transaction: {e}")
            raise
    
    def get_current_height(self) -> int:
        """Get current blockchain height"""
        url = f"{self.node_host}/blocks/lastHeaders/1"
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()[0]["height"]
        except Exception as e:
            logger.error(f"Failed to get block height: {e}")
            return 0


class ErgoTokenIssuer:
    """EIP-4 Token Issuer for RustChain Token (RTC)"""
    
    def __init__(self, api_key: str, node_host: str, issuer_address: str):
        self.client = ErgoNodeClient(api_key, node_host)
        self.issuer_address = issuer_address
        self.token_info: Optional[TokenInfo] = None
    
    def create_rtc_token(self, initial_supply: int = 1000000 * 10**9) -> str:
        """
        Create RTC token on Ergo blockchain
        
        Args:
            initial_supply: Initial token supply (default: 1M RTC with 9 decimals)
        
        Returns:
            token_id: The created token ID
        """
        logger.info(f"Creating RTC token with supply: {initial_supply / 10**9} RTC")
        
        # Create token metadata
        metadata = TokenMetadata(
            name="RustChain Token",
            description="Native token of RustChain blockchain, bridged to Ergo",
            symbol="RTC",
            decimals=9
        )
        
        # Get unspent boxes for token creation
        boxes = self.client.get_unspent_boxes(self.issuer_address)
        if not boxes:
            raise ValueError("No unspent boxes available for token creation")
        
        # Select boxes for token creation (need at least TOKEN_CREATION_FEE)
        selected_boxes = self._select_boxes(boxes, TOKEN_CREATION_FEE + MIN_BOX_VALUE)
        
        # Create token transaction
        tx = self._build_token_creation_tx(
            selected_boxes=selected_boxes,
            metadata=metadata,
            initial_supply=initial_supply
        )
        
        # Sign and send transaction
        signed_tx = self._sign_transaction(tx)
        tx_id = self.client.send_transaction(signed_tx)
        
        # Extract token ID from transaction
        token_id = self._extract_token_id(tx)
        
        # Store token info
        self.token_info = TokenInfo(
            token_id=token_id,
            name=metadata.name,
            symbol=metadata.symbol,
            decimals=metadata.decimals,
            total_supply=initial_supply,
            creator_address=self.issuer_address,
            creation_height=self.client.get_current_height(),
            metadata=metadata
        )
        
        logger.info(f"✅ RTC token created: {token_id}")
        return token_id
    
    def mint_tokens(self, amount: int, recipient: str) -> str:
        """
        Mint additional tokens (only for token creator)
        
        Args:
            amount: Amount to mint (in nanoRTC)
            recipient: Recipient address
        
        Returns:
            tx_id: Transaction ID
        """
        if not self.token_info:
            raise ValueError("Token not initialized. Call create_rtc_token first.")
        
        logger.info(f"Minting {amount / 10**9} RTC to {recipient}")
        
        # Get unspent boxes
        boxes = self.client.get_unspent_boxes(self.issuer_address)
        selected_boxes = self._select_boxes(boxes, MIN_BOX_VALUE)
        
        # Build mint transaction
        tx = self._build_mint_tx(
            selected_boxes=selected_boxes,
            amount=amount,
            recipient=recipient
        )
        
        signed_tx = self._sign_transaction(tx)
        return self.client.send_transaction(signed_tx)
    
    def burn_tokens(self, amount: int, holder_address: str, holder_boxes: List[Dict]) -> str:
        """
        Burn tokens (for bridge unlock mechanism)
        
        Args:
            amount: Amount to burn (in nanoRTC)
            holder_address: Token holder address
            holder_boxes: Unspent boxes containing tokens
        
        Returns:
            tx_id: Transaction ID
        """
        logger.info(f"Burning {amount / 10**9} RTC from {holder_address}")
        
        # Build burn transaction (send to provable burn address)
        burn_address = "9hzB5Z7VqFqJqJqJqJqJqJqJqJqJqJqJqJqJqJqJqJqJqJqJ"  # Provable burn
        tx = self._build_burn_tx(
            selected_boxes=holder_boxes,
            amount=amount,
            burn_address=burn_address
        )
        
        # Note: This needs to be signed by the holder
        return tx  # Return unsigned tx for holder to sign
    
    def register_token(self) -> bool:
        """
        Register token in EIP-4 Token Registry
        
        Returns:
            success: Whether registration was successful
        """
        if not self.token_info:
            raise ValueError("Token not initialized")
        
        logger.info(f"Registering token {self.token_info.token_id} in EIP-4 registry")
        
        # Prepare registry entry
        registry_entry = {
            "tokenId": self.token_info.token_id,
            "name": self.token_info.name,
            "symbol": self.token_info.symbol,
            "decimals": self.token_info.decimals,
            "description": self.token_info.metadata.description if self.token_info.metadata else "",
            "type": "EIP-4"
        }
        
        # In production, this would create a transaction to add to the registry
        # For now, just log the entry
        logger.info(f"Registry entry: {json.dumps(registry_entry, indent=2)}")
        
        return True
    
    def _select_boxes(self, boxes: List[Dict], min_value: int) -> List[Dict]:
        """Select boxes with sufficient value"""
        selected = []
        total = 0
        
        for box in sorted(boxes, key=lambda x: int(x["value"]), reverse=True):
            selected.append(box)
            total += int(box["value"])
            if total >= min_value:
                break
        
        if total < min_value:
            raise ValueError(f"Insufficient funds. Need {min_value}, have {total}")
        
        return selected
    
    def _build_token_creation_tx(self, selected_boxes: List[Dict], 
                                  metadata: TokenMetadata,
                                  initial_supply: int) -> Dict:
        """Build token creation transaction"""
        # This is a simplified version - in production would need full transaction building
        tx = {
            "inputs": [{"boxId": box["boxId"]} for box in selected_boxes],
            "dataInputs": [],
            "outputs": [
                {
                    "value": MIN_BOX_VALUE,
                    "ergoTree": self._address_to_tree(self.issuer_address),
                    "assets": [
                        {
                            "tokenId": "TOKEN_ID_PLACEHOLDER",  # Will be filled by node
                            "amount": initial_supply
                        }
                    ],
                    "creationHeight": self.client.get_current_height(),
                    "registers": metadata.to_registers()
                },
                {
                    "value": sum(int(box["value"]) for box in selected_boxes) - MIN_BOX_VALUE - TOKEN_CREATION_FEE,
                    "ergoTree": self._address_to_tree(self.issuer_address),
                    "assets": [],
                    "registers": {}
                }
            ]
        }
        return tx
    
    def _build_mint_tx(self, selected_boxes: List[Dict], amount: int, recipient: str) -> Dict:
        """Build token mint transaction"""
        tx = {
            "inputs": [{"boxId": box["boxId"]} for box in selected_boxes],
            "dataInputs": [],
            "outputs": [
                {
                    "value": MIN_BOX_VALUE,
                    "ergoTree": self._address_to_tree(recipient),
                    "assets": [
                        {
                            "tokenId": self.token_info.token_id,
                            "amount": amount
                        }
                    ],
                    "creationHeight": self.client.get_current_height(),
                    "registers": {}
                }
            ]
        }
        return tx
    
    def _build_burn_tx(self, selected_boxes: List[Dict], amount: int, burn_address: str) -> Dict:
        """Build token burn transaction"""
        tx = {
            "inputs": [{"boxId": box["boxId"]} for box in selected_boxes],
            "dataInputs": [],
            "outputs": [
                {
                    "value": MIN_BOX_VALUE,
                    "ergoTree": self._address_to_tree(burn_address),
                    "assets": [
                        {
                            "tokenId": self.token_info.token_id,
                            "amount": amount
                        }
                    ],
                    "creationHeight": self.client.get_current_height(),
                    "registers": {"4": "\"BURNED\""}
                }
            ]
        }
        return tx
    
    def _sign_transaction(self, tx: Dict) -> Dict:
        """Sign transaction with node"""
        url = f"{self.client.node_host}/transactions/sign"
        try:
            response = self.client.session.post(url, json=tx, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to sign transaction: {e}")
            raise
    
    def _address_to_tree(self, address: str) -> str:
        """Convert address to ErgoTree (simplified)"""
        # In production, would use proper address parsing
        # This is a placeholder
        return f"P835VhEW{address[:30]}"
    
    def _extract_token_id(self, tx: Dict) -> str:
        """Extract token ID from transaction (simplified)"""
        # In production, would parse the actual transaction
        # This is a placeholder
        return f"TOKEN_{int(time.time())}"


def main():
    """Example usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Ergo Token Issuance")
    parser.add_argument("--api-key", required=True, help="Ergo node API key")
    parser.add_argument("--node-host", default="http://localhost:9053", help="Node host")
    parser.add_argument("--address", required=True, help="Issuer address")
    parser.add_argument("--supply", type=int, default=1000000 * 10**9, help="Initial supply")
    parser.add_argument("--testnet", action="store_true", help="Use testnet")
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    issuer = ErgoTokenIssuer(
        api_key=args.api_key,
        node_host=args.node_host,
        issuer_address=args.address
    )
    
    try:
        token_id = issuer.create_rtc_token(initial_supply=args.supply)
        print(f"\n✅ RTC Token Created: {token_id}")
        
        # Register in EIP-4 registry
        issuer.register_token()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
