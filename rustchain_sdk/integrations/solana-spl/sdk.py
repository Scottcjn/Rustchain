"""
SPL Token SDK for Third-Party Integrations

This SDK provides a simple interface for exchanges, wallets, and DeFi protocols
to integrate with wRTC (Wrapped RustChain) on Solana.

Usage:
    from sdk import WRtcToken, WRtcBridge
    
    # Initialize token
    wrtc = WRtcToken(network="mainnet")
    
    # Get token info
    info = wrtc.get_token_info()
    
    # Bridge operations
    bridge = WRtcBridge(wrtc)
    quote = bridge.get_bridge_quote(1000, "RTC", "wRTC")
"""

import json
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Try to import Solana SDK (optional for read-only operations)
try:
    from solders.pubkey import Pubkey
    SOLANA_AVAILABLE = True
except ImportError:
    SOLANA_AVAILABLE = False


# ============================================================================
# Constants
# ============================================================================

WRTC_MINT_MAINNET = "12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X"
WRTC_MINT_DEVNET = "TODO_DEPLOY_ON_DEVNET"

RPC_ENDPOINTS = {
    "mainnet": "https://api.mainnet-beta.solana.com",
    "devnet": "https://api.devnet.solana.com",
    "testnet": "https://api.testnet.solana.com",
}

# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class TokenInfo:
    """Token information."""
    name: str
    symbol: str
    decimals: int
    mint_address: str
    total_supply: int
    circulating_supply: int
    description: str
    website: str
    logo_url: str


@dataclass
class BridgeQuote:
    """Bridge quote for token swap."""
    from_token: str
    to_token: str
    from_amount: int
    expected_to_amount: int
    fee: int
    estimated_time_seconds: int
    min_receive: int
    slippage_bps: int


@dataclass
class BridgeTransaction:
    """Bridge transaction status."""
    tx_hash: str
    status: str  # pending, completed, failed
    from_chain: str
    to_chain: str
    from_amount: int
    to_amount: int
    timestamp: int
    completion_time: Optional[int] = None


# ============================================================================
# Main SDK Classes
# ============================================================================


class WRtcToken:
    """
    wRTC Token interface for Solana.
    
    Provides read-only access to token information and balances.
    """
    
    def __init__(self, network: str = "mainnet"):
        """
        Initialize wRTC token client.
        
        Args:
            network: Solana network (mainnet, devnet, testnet)
        """
        self.network = network
        self.rpc_url = RPC_ENDPOINTS.get(network, RPC_ENDPOINTS["mainnet"])
        self.mint_address = WRTC_MINT_MAINNET if network == "mainnet" else WRTC_MINT_DEVNET
        
        # Static token info
        self.info = TokenInfo(
            name="Wrapped RustChain",
            symbol="wRTC",
            decimals=9,
            mint_address=self.mint_address,
            total_supply=0,  # Updated dynamically
            circulating_supply=0,  # Updated dynamically
            description="Solana-wrapped version of RustChain (RTC) token",
            website="https://rustchain.org",
            logo_url="https://rustchain.org/wrtc-logo.png"
        )
    
    def get_token_info(self) -> TokenInfo:
        """Get token information."""
        if SOLANA_AVAILABLE:
            self._update_supply_info()
        return self.info
    
    def _update_supply_info(self):
        """Update supply information from chain."""
        try:
            from solana.rpc.api import Client
            client = Client(self.rpc_url)
            
            # Get supply info
            response = client.get_token_supply(Pubkey.from_string(self.mint_address))
            supply = response.value
            
            self.info.total_supply = int(supply.amount)
            self.info.circulating_supply = int(supply.amount)  # Simplified
            
        except Exception as e:
            print(f"Warning: Could not fetch supply info: {e}")
    
    def get_balance(self, wallet_address: str) -> int:
        """
        Get wRTC balance for a wallet.
        
        Args:
            wallet_address: Solana wallet address
            
        Returns:
            Balance in smallest units (lamports for token)
        """
        if not SOLANA_AVAILABLE:
            return 0
        
        try:
            from solana.rpc.api import Client
            from solders.pubkey import Pubkey
            
            client = Client(self.rpc_url)
            wallet = Pubkey.from_string(wallet_address)
            
            # Find associated token account
            # In production, use spl.token.client.Token.get_associated_token_address
            response = client.get_token_accounts_by_owner(wallet, opts={"mint": self.mint_address})
            
            if response.value:
                account_info = response.value[0].account.data.parsed
                return int(account_info["info"]["tokenAmount"]["amount"])
            
            return 0
            
        except Exception as e:
            print(f"Warning: Could not fetch balance: {e}")
            return 0
    
    def get_holders(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get top wRTC holders.
        
        Args:
            limit: Maximum number of holders to return
            
        Returns:
            List of {address, balance} dicts
        """
        # In production, query Solana for token accounts
        # This is a placeholder
        return []
    
    def to_ui_amount(self, amount: int) -> float:
        """Convert smallest units to UI amount."""
        return amount / (10 ** self.info.decimals)
    
    def from_ui_amount(self, ui_amount: float) -> int:
        """Convert UI amount to smallest units."""
        return int(ui_amount * (10 ** self.info.decimals))


class WRtcBridge:
    """
    wRTC Bridge interface for cross-chain operations.
    
    Provides quotes and status for RTC <-> wRTC bridging.
    """
    
    def __init__(self, token: WRtcToken):
        """
        Initialize bridge client.
        
        Args:
            token: WRtcToken instance
        """
        self.token = token
        self.bridge_fee_bps = 30  # 0.3% fee
        self.min_bridge_amount = 10  # Minimum 10 RTC
        self.max_bridge_amount = 10000  # Maximum 10k RTC per tx
    
    def get_bridge_quote(
        self,
        amount: int,
        from_token: str,
        to_token: str,
        slippage_bps: int = 50
    ) -> BridgeQuote:
        """
        Get bridge quote.
        
        Args:
            amount: Amount to bridge (in smallest units)
            from_token: Source token (RTC or wRTC)
            to_token: Destination token (wRTC or RTC)
            slippage_bps: Slippage tolerance in basis points (default: 0.5%)
            
        Returns:
            BridgeQuote with expected amounts and fees
        """
        # Calculate fee
        fee = (amount * self.bridge_fee_bps) // 10000
        
        # Calculate output (1:1 minus fee)
        expected_output = amount - fee
        
        # Calculate minimum receive (with slippage)
        min_receive = int(expected_output * (10000 - slippage_bps) // 10000)
        
        return BridgeQuote(
            from_token=from_token,
            to_token=to_token,
            from_amount=amount,
            expected_to_amount=expected_output,
            fee=fee,
            estimated_time_seconds=300,  # ~5 minutes
            min_receive=min_receive,
            slippage_bps=slippage_bps
        )
    
    def initiate_bridge(
        self,
        amount: int,
        from_token: str,
        destination_address: str
    ) -> BridgeTransaction:
        """
        Initiate bridge transaction.
        
        Args:
            amount: Amount to bridge
            from_token: Source token
            destination_address: Destination chain address
            
        Returns:
            BridgeTransaction with status tracking
        """
        # In production, this would:
        # 1. Lock tokens on source chain
        # 2. Emit bridge event
        # 3. Return transaction hash
        
        import time
        tx_hash = f"bridge_{int(time.time())}_{amount}"
        
        return BridgeTransaction(
            tx_hash=tx_hash,
            status="pending",
            from_chain="Solana" if from_token == "wRTC" else "RustChain",
            to_chain="RustChain" if from_token == "wRTC" else "Solana",
            from_amount=amount,
            to_amount=amount - ((amount * self.bridge_fee_bps) // 10000),
            timestamp=int(time.time())
        )
    
    def get_bridge_status(self, tx_hash: str) -> BridgeTransaction:
        """
        Get bridge transaction status.
        
        Args:
            tx_hash: Bridge transaction hash
            
        Returns:
            BridgeTransaction with updated status
        """
        # In production, query bridge oracle
        # This is a placeholder
        return BridgeTransaction(
            tx_hash=tx_hash,
            status="pending",
            from_chain="Unknown",
            to_chain="Unknown",
            from_amount=0,
            to_amount=0,
            timestamp=0
        )


class WRtcSDK:
    """
    Complete wRTC SDK combining token and bridge operations.
    
    Usage:
        sdk = WRtcSDK(network="mainnet")
        
        # Get token info
        info = sdk.token.get_token_info()
        print(f"wRTC Supply: {info.total_supply}")
        
        # Get bridge quote
        quote = sdk.bridge.get_bridge_quote(1000, "RTC", "wRTC")
        print(f"Expected: {quote.expected_to_amount}")
    """
    
    def __init__(self, network: str = "mainnet"):
        """
        Initialize complete SDK.
        
        Args:
            network: Solana network
        """
        self.token = WRtcToken(network)
        self.bridge = WRtcBridge(self.token)
        self.network = network
    
    def get_sdk_info(self) -> Dict[str, Any]:
        """Get SDK information and capabilities."""
        return {
            "version": "1.0.0",
            "network": self.network,
            "mint_address": self.token.mint_address,
            "features": [
                "token_info",
                "balance_query",
                "bridge_quotes",
                "bridge_status"
            ],
            "limits": {
                "min_bridge": self.bridge.min_bridge_amount,
                "max_bridge": self.bridge.max_bridge_amount,
                "bridge_fee_bps": self.bridge.bridge_fee_bps
            }
        }


# ============================================================================
# Convenience Functions
# ============================================================================


def create_sdk(network: str = "mainnet") -> WRtcSDK:
    """Create wRTC SDK instance."""
    return WRtcSDK(network)


def get_token_info(network: str = "mainnet") -> TokenInfo:
    """Get wRTC token info."""
    sdk = create_sdk(network)
    return sdk.token.get_token_info()


def get_bridge_quote(
    amount: int,
    from_token: str,
    to_token: str,
    network: str = "mainnet"
) -> BridgeQuote:
    """Get bridge quote."""
    sdk = create_sdk(network)
    return sdk.bridge.get_bridge_quote(amount, from_token, to_token)


# ============================================================================
# CLI Interface
# ============================================================================


def main():
    """CLI interface for SDK."""
    import argparse
    
    parser = argparse.ArgumentParser(description="wRTC SDK CLI")
    parser.add_argument("--network", default="mainnet", choices=["mainnet", "devnet", "testnet"])
    parser.add_argument("--command", required=True, choices=["info", "balance", "quote"])
    parser.add_argument("--address", help="Wallet address (for balance)")
    parser.add_argument("--amount", type=int, help="Amount (for quote)")
    parser.add_argument("--from-token", help="From token (for quote)")
    parser.add_argument("--to-token", help="To token (for quote)")
    
    args = parser.parse_args()
    
    sdk = create_sdk(args.network)
    
    if args.command == "info":
        info = sdk.token.get_token_info()
        print(json.dumps({
            "name": info.name,
            "symbol": info.symbol,
            "decimals": info.decimals,
            "mint": info.mint_address
        }, indent=2))
    
    elif args.command == "balance":
        if not args.address:
            print("Error: --address required for balance command")
            return
        balance = sdk.token.get_balance(args.address)
        print(f"Balance: {balance} (smallest units)")
    
    elif args.command == "quote":
        if not all([args.amount, args.from_token, args.to_token]):
            print("Error: --amount, --from-token, --to-token required for quote")
            return
        quote = sdk.bridge.get_bridge_quote(args.amount, args.from_token, args.to_token)
        print(json.dumps({
            "from_amount": quote.from_amount,
            "expected_to_amount": quote.expected_to_amount,
            "fee": quote.fee,
            "min_receive": quote.min_receive,
            "estimated_time": quote.estimated_time_seconds
        }, indent=2))


if __name__ == "__main__":
    main()
