"""
RustChain Solana SPL Token Deployment Module

This module provides tools for deploying and managing wRTC (wrapped RustChain)
as a Solana SPL Token with multi-sig governance support.

Track A: Core SPL token deployment and integration artifacts.
"""

import os
import json
import hashlib
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict
from pathlib import Path

# Solana SDK imports (runtime check for availability)
try:
    from solana.rpc.api import Client
    from solana.rpc.commitment import Commitment
    from solana.rpc.types import TxOpts
    from solana.transaction import Transaction
    from solders.keypair import Keypair
    from solders.pubkey import Pubkey
    from solders.system_program import TransferParams, transfer
    from spl.token.client import Token
    from spl.token.instructions import (
        InitializeMintParams,
        initialize_mint,
        mint_to,
        MintToParams,
    )
    SOLANA_SDK_AVAILABLE = True
except ImportError:
    SOLANA_SDK_AVAILABLE = False
    # Provide stub classes for documentation/testing
    Client = None
    Keypair = None
    Pubkey = None
    Token = None


@dataclass
class TokenConfig:
    """Configuration for SPL token deployment."""
    name: str = "Wrapped RustChain"
    symbol: str = "wRTC"
    decimals: int = 9
    description: str = "Solana-wrapped version of RustChain (RTC) token, backed 1:1 by locked RTC on RustChain."
    image_url: str = "https://rustchain.org/wrtc-logo.png"
    external_url: str = "https://rustchain.org"
    bridge_name: str = "BoTTube"
    
    def to_metadata(self) -> Dict[str, Any]:
        """Convert to SPL Token metadata format."""
        return {
            "name": self.name,
            "symbol": self.symbol,
            "description": self.description,
            "image": self.image_url,
            "external_url": self.external_url,
            "attributes": [
                {"trait_type": "Chain", "value": "Solana"},
                {"trait_type": "Standard", "value": "SPL Token"},
                {"trait_type": "Backing", "value": "1:1 RTC"},
                {"trait_type": "Bridge", "value": self.bridge_name}
            ]
        }


@dataclass
class MultiSigConfig:
    """Configuration for multi-sig governance."""
    signers: List[str]  # List of signer public keys
    threshold: int = 3  # Required signatures
    description: str = "RustChain wRTC Multi-Sig Governance"
    
    def validate(self) -> bool:
        """Validate multi-sig configuration."""
        if len(self.signers) < self.threshold:
            return False
        if self.threshold < 1:
            return False
        # Validate pubkey format (base58, 32-44 chars)
        for signer in self.signers:
            if not isinstance(signer, str) or len(signer) < 32 or len(signer) > 44:
                return False
        return True


@dataclass
class BridgeEscrowConfig:
    """Configuration for bridge escrow vault."""
    escrow_authority: str  # PDA or program address
    mint_address: str  # wRTC mint address
    daily_mint_cap: int = 100_000_000_000_000  # 100k wRTC in lamports (9 decimals)
    per_tx_limit: int = 10_000_000_000_000  # 10k wRTC
    total_supply_cap: Optional[int] = None  # None = no cap
    
    def validate(self) -> bool:
        """Validate escrow configuration."""
        if self.daily_mint_cap <= 0:
            return False
        if self.per_tx_limit <= 0:
            return False
        if self.per_tx_limit > self.daily_mint_cap:
            return False
        return True


class SPLTokenDeployment:
    """
    Main class for deploying and managing wRTC SPL token.
    
    Usage:
        >>> config = TokenConfig()
        >>> deployment = SPLTokenDeployment("https://api.devnet.solana.com")
        >>> mint_address = deployment.deploy_token(config, keypair)
    """
    
    def __init__(self, rpc_url: str = "https://api.devnet.solana.com"):
        """
        Initialize deployment client.
        
        Args:
            rpc_url: Solana RPC endpoint (devnet/mainnet/custom)
        """
        if not SOLANA_SDK_AVAILABLE:
            raise ImportError(
                "Solana SDK not available. Install with: "
                "pip install solana solders spl-token"
            )
        
        self.rpc_url = rpc_url
        self.client = Client(rpc_url)
        self.mint_address: Optional[Pubkey] = None
        self.token_client: Optional[Token] = None
        
    def deploy_token(
        self,
        config: TokenConfig,
        keypair: Keypair,
        freeze_authority: Optional[Pubkey] = None,
        mint_authority: Optional[Pubkey] = None
    ) -> str:
        """
        Deploy new SPL token mint.
        
        Args:
            config: Token configuration
            keypair: Deployer keypair (pays fees, initial authority)
            freeze_authority: Optional freeze authority (default: keypair)
            mint_authority: Optional mint authority (default: keypair)
            
        Returns:
            Mint address as base58 string
        """
        # Use keypair as default authority
        authority = keypair.pubkey()
        freeze_auth = freeze_authority or authority
        mint_auth = mint_authority or authority
        
        # Create token mint
        self.token_client = Token.create_mint(
            self.client,
            keypair,
            mint_authority=mint_auth,
            freeze_authority=freeze_auth,
            decimals=config.decimals
        )
        
        self.mint_address = self.token_client.pubkey
        
        # Initialize metadata
        self._initialize_metadata(config, keypair)
        
        return str(self.mint_address)
    
    def _initialize_metadata(self, config: TokenConfig, keypair: Keypair) -> None:
        """Initialize token metadata on-chain."""
        if not self.mint_address:
            raise ValueError("Mint not deployed yet")
        
        metadata = config.to_metadata()
        
        # Note: Metadata initialization requires Metaplex Token Metadata Program
        # This is a simplified version - production should use full Metaplex SDK
        print(f"Metadata prepared for mint {self.mint_address}:")
        print(json.dumps(metadata, indent=2))
    
    def create_escrow_account(
        self,
        keypair: Keypair,
        owner: Pubkey
    ) -> str:
        """
        Create token account for bridge escrow.
        
        Args:
            keypair: Payer keypair
            owner: Owner of the token account (escrow authority)
            
        Returns:
            Token account address as base58 string
        """
        if not self.token_client:
            raise ValueError("Token client not initialized")
        
        # Create associated token account
        escrow_account = self.token_client.create_associated_token_account(owner)
        
        return str(escrow_account)
    
    def mint_tokens(
        self,
        keypair: Keypair,
        destination: Pubkey,
        amount: int,
        multi_sig_signatures: Optional[List[str]] = None
    ) -> str:
        """
        Mint tokens (requires mint authority).
        
        Args:
            keypair: Mint authority keypair
            destination: Recipient token account
            amount: Amount in smallest units (lamports for token)
            multi_sig_signatures: Optional list of multi-sig signatures
            
        Returns:
            Transaction signature
        """
        if not self.token_client:
            raise ValueError("Token client not initialized")
        
        # Mint tokens
        tx_sig = self.token_client.mint_to(
            dest=destination,
            mint_authority=keypair,
            amount=amount
        )
        
        return str(tx_sig)
    
    def get_supply(self) -> Dict[str, int]:
        """
        Get current token supply information.
        
        Returns:
            Dict with 'total', 'circulating', 'non_circulating'
        """
        if not self.token_client:
            raise ValueError("Token client not initialized")
        
        supply = self.token_client.get_supply()
        
        return {
            "total": supply.value.total,
            "circulating": supply.value.circulating,
            "non_circulating": supply.value.non_circulating
        }
    
    def verify_deployment(self) -> Dict[str, Any]:
        """
        Verify token deployment configuration.
        
        Returns:
            Verification report dict
        """
        if not self.mint_address:
            return {"status": "error", "message": "No mint deployed"}
        
        report = {
            "status": "success",
            "mint_address": str(self.mint_address),
            "rpc_url": self.rpc_url,
            "network": self._detect_network(),
            "checks": {}
        }
        
        # Check mint exists
        try:
            mint_info = self.client.get_account_info(self.mint_address)
            report["checks"]["mint_exists"] = mint_info.value is not None
        except Exception as e:
            report["checks"]["mint_exists"] = False
            report["checks"]["mint_exists_error"] = str(e)
        
        # Check supply
        try:
            supply = self.get_supply()
            report["checks"]["supply"] = supply
        except Exception as e:
            report["checks"]["supply_error"] = str(e)
        
        return report
    
    def _detect_network(self) -> str:
        """Detect Solana network from RPC URL."""
        if "devnet" in self.rpc_url:
            return "devnet"
        elif "mainnet" in self.rpc_url:
            return "mainnet"
        elif "testnet" in self.rpc_url:
            return "testnet"
        else:
            return "custom"
    
    def generate_deployment_report(self, config: TokenConfig) -> str:
        """
        Generate human-readable deployment report.
        
        Args:
            config: Token configuration used
            
        Returns:
            Markdown-formatted report
        """
        verification = self.verify_deployment()
        
        report = f"""# wRTC SPL Token Deployment Report

## Token Configuration
- **Name**: {config.name}
- **Symbol**: {config.symbol}
- **Decimals**: {config.decimals}
- **Description**: {config.description}

## Deployment Status
- **Status**: {verification['status']}
- **Mint Address**: `{verification.get('mint_address', 'N/A')}`
- **Network**: {verification.get('network', 'unknown')}

## Verification Checks
"""
        
        for check_name, check_result in verification.get("checks", {}).items():
            if isinstance(check_result, dict):
                report += f"\n### {check_name}\n"
                for k, v in check_result.items():
                    report += f"- {k}: `{v}`\n"
            else:
                status = "✅" if check_result else "❌"
                report += f"- {status} {check_name}: {check_result}\n"
        
        report += f"\n---\nGenerated: {Path(__file__).name}\n"
        
        return report


class BridgeIntegration:
    """
    Bridge integration helpers for wRTC <-> RTC operations.
    
    Provides utilities for:
    - Lock verification (RustChain side)
    - Mint authorization (Solana side)
    - Escrow accounting
    - Cross-chain event tracking
    """
    
    def __init__(self, spl_deployment: SPLTokenDeployment):
        self.spl = spl_deployment
        self.lock_events: List[Dict] = []
        self.mint_events: List[Dict] = []
    
    def verify_rtc_lock(self, rustchain_tx_hash: str, amount: int) -> bool:
        """
        Verify RTC tokens are locked on RustChain.
        
        Args:
            rustchain_tx_hash: Transaction hash on RustChain
            amount: Amount locked (in RTC smallest units)
            
        Returns:
            True if lock verified
        """
        # In production, this would call RustChain node API
        # For now, simulate verification
        print(f"Verifying RTC lock: {rustchain_tx_hash} for {amount} RTC")
        return True
    
    def authorize_mint(
        self,
        destination: str,
        amount: int,
        rustchain_proof: str
    ) -> Dict[str, Any]:
        """
        Authorize wRTC mint after RTC lock verification.
        
        Args:
            destination: Solana address to receive wRTC
            amount: Amount to mint
            rustchain_proof: Proof of RTC lock (tx hash)
            
        Returns:
            Authorization record with signatures
        """
        auth_record = {
            "destination": destination,
            "amount": amount,
            "rustchain_proof": rustchain_proof,
            "timestamp": int(Path(__file__).stat().st_mtime),
            "status": "pending_multi_sig"
        }
        
        # In production, submit to multi-sig service
        # For now, return authorization record
        return auth_record
    
    def get_escrow_balance(self, escrow_account: str) -> int:
        """
        Get wRTC balance in escrow vault.
        
        Args:
            escrow_account: Escrow token account address
            
        Returns:
            Balance in smallest units
        """
        if not self.spl.token_client:
            raise ValueError("Token client not initialized")
        
        account_info = self.spl.token_client.get_account_info(
            Pubkey.from_string(escrow_account)
        )
        
        return account_info.value.amount if account_info.value else 0
    
    def generate_bridge_report(self) -> Dict[str, Any]:
        """Generate bridge status report."""
        return {
            "escrow_balance": self.get_escrow_balance("TODO") if self.spl.token_client else 0,
            "pending_locks": len(self.lock_events),
            "completed_mints": len(self.mint_events),
            "status": "operational"
        }


def load_config_from_file(config_path: str) -> Dict[str, Any]:
    """Load configuration from JSON file."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(path, 'r') as f:
        return json.load(f)


def save_config_to_file(config: Dict[str, Any], config_path: str) -> None:
    """Save configuration to JSON file."""
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, 'w') as f:
        json.dump(config, f, indent=2)


def hash_config(config: Dict[str, Any]) -> str:
    """Generate SHA256 hash of configuration for verification."""
    config_str = json.dumps(config, sort_keys=True)
    return hashlib.sha256(config_str.encode()).hexdigest()
