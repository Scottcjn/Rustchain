// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import os
import json
import sqlite3
import time
from typing import Dict, Any, Optional, List
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solana.rpc.api import Client
from solana.rpc.commitment import Commitment
from solana.transaction import Transaction
from spl.token.instructions import (
    create_mint, mint_to, burn, set_authority, AuthorityType,
    create_associated_token_account, get_associated_token_address
)
from spl.token.client import Token
from metaplex.metadata import create_metadata_account_v3
import requests

DB_PATH = "rustchain.db"

class WRTCSolanaManager:
    """Solana SPL token management for wRTC token operations"""

    def __init__(self, network="devnet"):
        self.network = network
        self.rpc_url = self._get_rpc_url(network)
        self.client = Client(self.rpc_url, commitment=Commitment("confirmed"))
        self.token_program_id = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
        self.metadata_program_id = Pubkey.from_string("metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s")
        self._init_database()

    def _get_rpc_url(self, network):
        """Get RPC URL for network"""
        urls = {
            "devnet": "https://api.devnet.solana.com",
            "mainnet": "https://api.mainnet-beta.solana.com",
            "testnet": "https://api.testnet.solana.com"
        }
        return urls.get(network, urls["devnet"])

    def _init_database(self):
        """Initialize database tables for Solana operations"""
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS solana_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mint_address TEXT UNIQUE NOT NULL,
                    network TEXT NOT NULL,
                    token_name TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    decimals INTEGER DEFAULT 9,
                    total_supply INTEGER DEFAULT 0,
                    authority_pubkey TEXT,
                    metadata_account TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS solana_operations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation_type TEXT NOT NULL,
                    mint_address TEXT NOT NULL,
                    signature TEXT UNIQUE NOT NULL,
                    amount INTEGER,
                    recipient TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    confirmed_at TIMESTAMP
                )
            ''')

    def create_wrtc_token(self, payer_keypair: Keypair, mint_authority: Optional[Keypair] = None):
        """Create wRTC SPL token with metadata"""
        if mint_authority is None:
            mint_authority = payer_keypair

        mint_keypair = Keypair()
        decimals = 9

        # Create mint account
        create_mint_ix = create_mint(
            conn=self.client,
            payer=payer_keypair.pubkey(),
            mint=mint_keypair.pubkey(),
            decimals=decimals,
            mint_authority=mint_authority.pubkey(),
            freeze_authority=None
        )

        # Create metadata
        metadata_data = {
            "name": "Wrapped Rustchain Token",
            "symbol": "wRTC",
            "uri": self._get_token_metadata_uri(),
            "seller_fee_basis_points": 0,
            "creators": None
        }

        metadata_account, _ = self._derive_metadata_account(mint_keypair.pubkey())

        metadata_ix = create_metadata_account_v3(
            metadata=metadata_account,
            mint=mint_keypair.pubkey(),
            mint_authority=mint_authority.pubkey(),
            payer=payer_keypair.pubkey(),
            update_authority=mint_authority.pubkey(),
            data=metadata_data,
            is_mutable=True,
            collection=None,
            uses=None
        )

        # Build and send transaction
        transaction = Transaction()
        transaction.add(create_mint_ix)
        transaction.add(metadata_ix)

        try:
            signature = self.client.send_transaction(
                transaction,
                payer_keypair, mint_keypair, mint_authority,
                opts={"skip_confirmation": False}
            )

            # Store in database
            self._store_token_info(
                mint_keypair.pubkey().to_base58(),
                "wRTC",
                "Wrapped Rustchain Token",
                decimals,
                mint_authority.pubkey().to_base58(),
                metadata_account.to_base58()
            )

            return {
                "mint_address": mint_keypair.pubkey().to_base58(),
                "metadata_account": metadata_account.to_base58(),
                "signature": signature.value,
                "network": self.network
            }

        except Exception as e:
            raise Exception(f"Failed to create wRTC token: {str(e)}")

    def mint_tokens(self, mint_address: str, recipient: str, amount: int, authority_keypair: Keypair):
        """Mint wRTC tokens to recipient"""
        mint_pubkey = Pubkey.from_string(mint_address)
        recipient_pubkey = Pubkey.from_string(recipient)

        # Get or create associated token account
        ata = get_associated_token_address(recipient_pubkey, mint_pubkey)

        try:
            # Check if ATA exists
            account_info = self.client.get_account_info(ata)
            if account_info.value is None:
                # Create ATA
                create_ata_ix = create_associated_token_account(
                    payer=authority_keypair.pubkey(),
                    owner=recipient_pubkey,
                    mint=mint_pubkey
                )
                tx = Transaction().add(create_ata_ix)
                self.client.send_transaction(tx, authority_keypair)
        except Exception:
            pass

        # Mint tokens
        mint_ix = mint_to(
            program_id=self.token_program_id,
            mint=mint_pubkey,
            dest=ata,
            mint_authority=authority_keypair.pubkey(),
            amount=amount
        )

        transaction = Transaction().add(mint_ix)

        try:
            signature = self.client.send_transaction(
                transaction, authority_keypair,
                opts={"skip_confirmation": False}
            )

            # Record operation
            self._record_operation(
                "mint", mint_address, signature.value,
                amount, recipient, "confirmed"
            )

            return signature.value

        except Exception as e:
            raise Exception(f"Failed to mint tokens: {str(e)}")

    def burn_tokens(self, mint_address: str, token_account: str, amount: int, owner_keypair: Keypair):
        """Burn wRTC tokens from account"""
        burn_ix = burn(
            program_id=self.token_program_id,
            account=Pubkey.from_string(token_account),
            mint=Pubkey.from_string(mint_address),
            owner=owner_keypair.pubkey(),
            amount=amount
        )

        transaction = Transaction().add(burn_ix)

        try:
            signature = self.client.send_transaction(
                transaction, owner_keypair,
                opts={"skip_confirmation": False}
            )

            self._record_operation(
                "burn", mint_address, signature.value,
                amount, owner_keypair.pubkey().to_base58(), "confirmed"
            )

            return signature.value

        except Exception as e:
            raise Exception(f"Failed to burn tokens: {str(e)}")

    def set_mint_authority(self, mint_address: str, current_authority: Keypair, new_authority: Optional[str] = None):
        """Set or revoke mint authority"""
        new_auth_pubkey = Pubkey.from_string(new_authority) if new_authority else None

        set_auth_ix = set_authority(
            program_id=self.token_program_id,
            account=Pubkey.from_string(mint_address),
            authority=AuthorityType.MINT_TOKENS,
            current_authority=current_authority.pubkey(),
            new_authority=new_auth_pubkey
        )

        transaction = Transaction().add(set_auth_ix)

        try:
            signature = self.client.send_transaction(
                transaction, current_authority,
                opts={"skip_confirmation": False}
            )
            return signature.value
        except Exception as e:
            raise Exception(f"Failed to set mint authority: {str(e)}")

    def get_token_supply(self, mint_address: str):
        """Get current token supply"""
        try:
            supply_info = self.client.get_token_supply(Pubkey.from_string(mint_address))
            return supply_info.value.ui_amount
        except Exception as e:
            raise Exception(f"Failed to get token supply: {str(e)}")

    def get_token_balance(self, token_account: str):
        """Get token account balance"""
        try:
            balance_info = self.client.get_token_account_balance(Pubkey.from_string(token_account))
            return balance_info.value.ui_amount
        except Exception as e:
            raise Exception(f"Failed to get token balance: {str(e)}")

    def get_associated_token_account(self, owner: str, mint: str):
        """Get associated token account address"""
        return get_associated_token_address(
            Pubkey.from_string(owner),
            Pubkey.from_string(mint)
        ).to_base58()

    def deploy_to_mainnet(self, devnet_config: Dict[str, Any], mainnet_keypair: Keypair):
        """Deploy wRTC token to mainnet with same configuration"""
        mainnet_manager = WRTCSolanaManager("mainnet")

        result = mainnet_manager.create_wrtc_token(
            payer_keypair=mainnet_keypair,
            mint_authority=mainnet_keypair
        )

        return result

    def _derive_metadata_account(self, mint_pubkey: Pubkey):
        """Derive metadata account PDA"""
        seeds = [
            b"metadata",
            bytes(self.metadata_program_id),
            bytes(mint_pubkey)
        ]
        return Pubkey.find_program_address(seeds, self.metadata_program_id)

    def _get_token_metadata_uri(self):
        """Get metadata URI for wRTC token"""
        metadata = {
            "name": "Wrapped Rustchain Token",
            "symbol": "wRTC",
            "description": "Wrapped RTC token for cross-chain operations on Solana",
            "image": "https://raw.githubusercontent.com/Scottcjn/Rustchain/main/assets/wrtc-logo.png",
            "external_url": "https://github.com/Scottcjn/Rustchain",
            "attributes": [
                {"trait_type": "Network", "value": "Cross-Chain"},
                {"trait_type": "Type", "value": "Wrapped Token"},
                {"trait_type": "Chain", "value": "Solana"}
            ]
        }

        # In production, upload to IPFS or Arweave
        return "https://arweave.net/wrtc-metadata.json"

    def _store_token_info(self, mint_address: str, symbol: str, name: str, decimals: int, authority: str, metadata_account: str):
        """Store token information in database"""
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO solana_tokens
                (mint_address, network, token_name, symbol, decimals, authority_pubkey, metadata_account)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (mint_address, self.network, name, symbol, decimals, authority, metadata_account))

    def _record_operation(self, op_type: str, mint_address: str, signature: str, amount: int, recipient: str, status: str):
        """Record token operation in database"""
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                INSERT INTO solana_operations
                (operation_type, mint_address, signature, amount, recipient, status, confirmed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (op_type, mint_address, signature, amount, recipient, status,
                 int(time.time()) if status == "confirmed" else None))

    def get_token_info(self, mint_address: str):
        """Get stored token information"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('''
                SELECT * FROM solana_tokens WHERE mint_address = ?
            ''', (mint_address,))
            row = cursor.fetchone()

            if row:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
            return None

    def get_operations_history(self, mint_address: str, limit: int = 50):
        """Get operations history for token"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('''
                SELECT * FROM solana_operations
                WHERE mint_address = ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (mint_address, limit))

            operations = []
            for row in cursor.fetchall():
                columns = [desc[0] for desc in cursor.description]
                operations.append(dict(zip(columns, row)))

            return operations

def deploy_wrtc_devnet():
    """Deployment script for wRTC on Solana devnet"""
    try:
        # Generate or load keypair
        keypair = Keypair()
        manager = WRTCSolanaManager("devnet")

        print("Creating wRTC token on Solana devnet...")
        result = manager.create_wrtc_token(keypair)

        print(f"✅ wRTC Token Created Successfully!")
        print(f"Mint Address: {result['mint_address']}")
        print(f"Metadata Account: {result['metadata_account']}")
        print(f"Transaction: {result['signature']}")
        print(f"Network: {result['network']}")

        return result

    except Exception as e:
        print(f"❌ Deployment failed: {str(e)}")
        return None

if __name__ == "__main__":
    deploy_wrtc_devnet()
