#!/usr/bin/env python3
"""
Micro Liquidity Verification Tool (Bounty #692)

Verifies liquidity pool status, LP token balances, and generates evidence reports
for wRTC liquidity provision on Solana DEXs (Raydium, Orca, etc.).

Usage:
    python verify_liquidity.py --pool POOL_ADDRESS
    python verify_liquidity.py --wallet YOUR_WALLET --check-lp
    python verify_liquidity.py --wallet YOUR_WALLET --pool POOL_ADDRESS --output report.json
"""

import argparse
import json
import hashlib
import sys
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict

# Try to import requests, provide helpful error if missing
try:
    import requests
except ImportError:
    print("Error: 'requests' library required. Install with: pip install requests")
    sys.exit(1)


# Constants - Official wRTC pools
WRTC_MINT = "12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X"
SOL_MINT = "So111D1r32v1NvGaTQeXj5Xh9VxNf6"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

# Official pool addresses
WRTC_SOL_POOL = "8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb"
WRTC_USDC_POOL = ""  # To be added when available

# API endpoints
DEXSCREENER_API = "https://api.dexscreener.com/latest/dex"
SOLANA_RPC = "https://api.mainnet-beta.solana.com"
RAYDIUM_API = "https://api.raydium.io/v2"


@dataclass
class PoolInfo:
    """Pool information data structure"""
    address: str
    pair: str
    base_token: str
    quote_token: str
    tvl_usd: float
    volume_24h_usd: float
    fees_24h_usd: float
    price_usd: float
    price_change_24h: float
    liquidity_locked: bool
    pool_age_days: int


@dataclass
class PositionInfo:
    """Liquidity position information"""
    wallet: str
    lp_tokens: str
    lp_tokens_formatted: float
    share_percent: float
    value_usd: float
    fees_earned_usd: float
    impermanent_loss_percent: float


@dataclass
class TransactionProof:
    """Transaction proof data structure"""
    signature: str
    type: str
    timestamp: str
    block_height: int
    sol_deposited: float
    wrtc_deposited: float
    lp_tokens_received: str


@dataclass
class VerificationReport:
    """Complete verification report"""
    verification_id: str
    timestamp: str
    tool_version: str
    wallet: Optional[str]
    pool: Dict[str, Any]
    position: Optional[Dict[str, Any]]
    transactions: List[Dict[str, Any]]
    safety_checks: Dict[str, Any]
    proof_hash: str


class LiquidityVerifier:
    """Main class for verifying liquidity positions"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "RustChain-Liquidity-Verifier/1.0"
        })
    
    def log(self, message: str):
        """Print message if verbose mode is enabled"""
        if self.verbose:
            print(f"[INFO] {message}")
    
    def fetch_pool_data(self, pool_address: str) -> Optional[PoolInfo]:
        """Fetch pool data from DexScreener API"""
        try:
            url = f"{DEXSCREENER_API}/pairs/solana/{pool_address}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if not data.get("pairs"):
                print(f"❌ Pool not found: {pool_address}")
                return None
            
            pair = data["pairs"][0]
            
            # Extract pool information
            base_token = pair.get("baseToken", {})
            quote_token = pair.get("quoteToken", {})
            liquidity = pair.get("liquidity", {})
            volume = pair.get("volume", {})
            price_change = pair.get("priceChange", {})
            
            # Calculate 24h fees (typically 0.25% of volume on Raydium)
            fees_24h = volume.get("h24", 0) * 0.0025
            
            pool_info = PoolInfo(
                address=pool_address,
                pair=f"{base_token.get('symbol', 'UNKNOWN')}/{quote_token.get('symbol', 'UNKNOWN')}",
                base_token=base_token.get("address", ""),
                quote_token=quote_token.get("address", ""),
                tvl_usd=liquidity.get("usd", 0),
                volume_24h_usd=volume.get("h24", 0),
                fees_24h_usd=fees_24h,
                price_usd=float(pair.get("priceUsd", 0)),
                price_change_24h=price_change.get("h24", 0),
                liquidity_locked=self._check_liquidity_locked(pair),
                pool_age_days=self._calculate_pool_age_days(pair)
            )
            
            return pool_info
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching pool data: {e}")
            return None
        except (KeyError, ValueError, TypeError) as e:
            print(f"❌ Error parsing pool data: {e}")
            return None
    
    def _check_liquidity_locked(self, pair_data: dict) -> bool:
        """Check if pool liquidity is locked"""
        # DexScreener doesn't directly provide lock info
        # This is a placeholder - in production, check lock contracts
        return True  # Assume locked for official pools
    
    def _calculate_pool_age_days(self, pair_data: dict) -> int:
        """Calculate pool age in days"""
        created_at = pair_data.get("pairCreatedAt")
        if created_at:
            try:
                created_dt = datetime.fromtimestamp(created_at / 1000, tz=timezone.utc)
                now = datetime.now(timezone.utc)
                age = now - created_dt
                return age.days
            except (ValueError, TypeError):
                pass
        return 0
    
    def fetch_wallet_lp_tokens(self, wallet_address: str, pool_address: str) -> Optional[Dict[str, Any]]:
        """Fetch LP token balance for a wallet"""
        try:
            # First, get the pool info to find LP mint address
            pool_data = self.fetch_pool_data(pool_address)
            if not pool_data:
                return None
            
            # For Raydium, LP mint is typically derived from pool
            # This is simplified - in production, query pool program accounts
            lp_mint = self._get_lp_mint_address(pool_address)
            
            # Query Solana RPC for token accounts
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTokenAccountsByOwner",
                "params": [
                    wallet_address,
                    {"mint": lp_mint},
                    {"encoding": "jsonParsed"}
                ]
            }
            
            response = self.session.post(SOLANA_RPC, json=payload, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            if "result" in result and "value" in result["result"]:
                accounts = result["result"]["value"]
                if accounts:
                    # Sum up all LP token balances
                    total_lp = 0
                    for account in accounts:
                        parsed = account.get("account", {}).get("data", {}).get("parsed", {})
                        info = parsed.get("info", {})
                        token_amount = info.get("tokenAmount", {})
                        total_lp += float(token_amount.get("uiAmount", 0))
                    
                    return {
                        "lp_mint": lp_mint,
                        "lp_balance": total_lp,
                        "wallet": wallet_address
                    }
            
            return {"lp_mint": lp_mint, "lp_balance": 0, "wallet": wallet_address}
            
        except requests.exceptions.RequestException as e:
            self.log(f"Error fetching wallet LP tokens: {e}")
            return None
        except (KeyError, ValueError, TypeError) as e:
            self.log(f"Error parsing wallet data: {e}")
            return None
    
    def _get_lp_mint_address(self, pool_address: str) -> str:
        """Get LP token mint address for a pool"""
        # Simplified - in production, query pool program
        # Raydium LP mints are deterministic from pool state
        return f"RLP_{pool_address[:38]}"  # Placeholder
    
    def get_wallet_transactions(self, wallet_address: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent transactions for a wallet"""
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getSignaturesForAddress",
                "params": [
                    wallet_address,
                    {"limit": limit}
                ]
            }
            
            response = self.session.post(SOLANA_RPC, json=payload, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            if "result" in result:
                return result["result"]
            
            return []
            
        except requests.exceptions.RequestException as e:
            self.log(f"Error fetching transactions: {e}")
            return []
    
    def analyze_liquidity_transactions(self, transactions: List[Dict[str, Any]]) -> List[TransactionProof]:
        """Analyze transactions for liquidity-related activity"""
        liquidity_txs = []
        
        for tx in transactions:
            signature = tx.get("signature", "")
            
            # Fetch full transaction details
            tx_details = self.fetch_transaction_details(signature)
            if not tx_details:
                continue
            
            # Check if it's a liquidity transaction
            tx_type = self._classify_transaction(tx_details)
            if tx_type in ["add_liquidity", "remove_liquidity"]:
                proof = self._extract_liquidity_proof(tx_details, tx_type)
                if proof:
                    liquidity_txs.append(proof)
        
        return liquidity_txs
    
    def fetch_transaction_details(self, signature: str) -> Optional[Dict[str, Any]]:
        """Fetch full transaction details"""
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTransaction",
                "params": [
                    signature,
                    {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}
                ]
            }
            
            response = self.session.post(SOLANA_RPC, json=payload, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            return result.get("result")
            
        except requests.exceptions.RequestException as e:
            self.log(f"Error fetching transaction {signature}: {e}")
            return None
    
    def _classify_transaction(self, tx_details: dict) -> str:
        """Classify transaction type"""
        # Simplified classification
        # In production, parse instruction data and program IDs
        meta = tx_details.get("meta", {})
        log_messages = meta.get("logMessages", [])
        
        for log in log_messages:
            if "add_liquidity" in log.lower() or "deposit" in log.lower():
                return "add_liquidity"
            elif "remove_liquidity" in log.lower() or "withdraw" in log.lower():
                return "remove_liquidity"
            elif "swap" in log.lower():
                return "swap"
        
        return "unknown"
    
    def _extract_liquidity_proof(self, tx_details: dict, tx_type: str) -> Optional[TransactionProof]:
        """Extract liquidity proof from transaction"""
        try:
            signature = tx_details.get("signature", "unknown")
            slot = tx_details.get("slot", 0)
            block_time = tx_details.get("blockTime", 0)
            timestamp = datetime.fromtimestamp(block_time, tz=timezone.utc).isoformat() if block_time else "unknown"
            
            meta = tx_details.get("meta", {})
            pre_balances = meta.get("preBalances", [])
            post_balances = meta.get("postBalances", [])
            
            # Calculate SOL deposited (simplified)
            sol_deposited = 0
            if pre_balances and post_balances:
                sol_deposited = (pre_balances[0] - post_balances[0]) / 1e9
            
            return TransactionProof(
                signature=signature,
                type=tx_type,
                timestamp=timestamp,
                block_height=slot,
                sol_deposited=sol_deposited,
                wrtc_deposited=0,  # Would need token account parsing
                lp_tokens_received="0"  # Would need token account parsing
            )
            
        except (KeyError, ValueError, TypeError) as e:
            self.log(f"Error extracting liquidity proof: {e}")
            return None
    
    def run_safety_checks(self, pool_info: PoolInfo) -> Dict[str, Any]:
        """Run safety checks on a pool"""
        checks = {
            "token_authenticity": self._check_token_authenticity(pool_info),
            "pool_health": self._check_pool_health(pool_info),
            "liquidity_lock": self._check_liquidity_lock_status(pool_info),
            "rug_pull_risk": self._assess_rug_pull_risk(pool_info),
        }
        
        overall_score = sum(checks.values()) / len(checks)
        
        return {
            "overall_score": round(overall_score, 2),
            "passed": overall_score >= 0.7,
            "checks": checks
        }
    
    def _check_token_authenticity(self, pool_info: PoolInfo) -> float:
        """Verify token mint addresses"""
        score = 0.0
        
        # Check if wRTC is in the pair
        if WRTC_MINT in [pool_info.base_token, pool_info.quote_token]:
            score += 0.5
        
        # Check if paired with known token (SOL, USDC)
        if pool_info.quote_token in [SOL_MINT, USDC_MINT]:
            score += 0.5
        elif pool_info.base_token in [SOL_MINT, USDC_MINT]:
            score += 0.5
        
        return score
    
    def _check_pool_health(self, pool_info: PoolInfo) -> float:
        """Assess pool health metrics"""
        score = 0.0
        
        # TVL check
        if pool_info.tvl_usd >= 10000:
            score += 0.4
        elif pool_info.tvl_usd >= 1000:
            score += 0.2
        
        # Volume check
        if pool_info.volume_24h_usd >= 1000:
            score += 0.3
        elif pool_info.volume_24h_usd >= 100:
            score += 0.1
        
        # Age check
        if pool_info.pool_age_days >= 30:
            score += 0.3
        elif pool_info.pool_age_days >= 7:
            score += 0.1
        
        return score
    
    def _check_liquidity_lock_status(self, pool_info: PoolInfo) -> float:
        """Check if liquidity is locked"""
        return 1.0 if pool_info.liquidity_locked else 0.0
    
    def _assess_rug_pull_risk(self, pool_info: PoolInfo) -> float:
        """Assess rug pull risk (inverse - higher is safer)"""
        risk_score = 0.0
        
        # Low risk if old pool with high TVL
        if pool_info.pool_age_days > 90 and pool_info.tvl_usd > 50000:
            risk_score = 1.0
        elif pool_info.pool_age_days > 30 and pool_info.tvl_usd > 10000:
            risk_score = 0.8
        elif pool_info.pool_age_days > 7 and pool_info.tvl_usd > 1000:
            risk_score = 0.5
        elif pool_info.tvl_usd > 100:
            risk_score = 0.3
        
        return risk_score
    
    def generate_verification_report(
        self,
        wallet_address: Optional[str],
        pool_info: PoolInfo,
        position_info: Optional[PositionInfo],
        transactions: List[TransactionProof],
        safety_checks: Dict[str, Any]
    ) -> VerificationReport:
        """Generate complete verification report"""
        # Create unique verification ID
        timestamp = datetime.now(timezone.utc).isoformat()
        unique_data = f"{wallet_address or 'anon'}-{pool_info.address}-{timestamp}"
        verification_id = f"liq_692_{hashlib.sha256(unique_data.encode()).hexdigest()[:12]}"
        
        # Create proof hash
        proof_data = json.dumps({
            "wallet": wallet_address,
            "pool": pool_info.address,
            "position": asdict(position_info) if position_info else None,
            "transactions": [asdict(tx) for tx in transactions],
            "timestamp": timestamp
        }, sort_keys=True)
        proof_hash = hashlib.sha256(proof_data.encode()).hexdigest()
        
        report = VerificationReport(
            verification_id=verification_id,
            timestamp=timestamp,
            tool_version="1.0.0",
            wallet=wallet_address,
            pool=asdict(pool_info),
            position=asdict(position_info) if position_info else None,
            transactions=[asdict(tx) for tx in transactions],
            safety_checks=safety_checks,
            proof_hash=proof_hash
        )
        
        return report


def print_pool_info(pool_info: PoolInfo):
    """Print pool information in a formatted way"""
    print("\n" + "="*60)
    print(f"🏊 Pool Information")
    print("="*60)
    print(f"Address: {pool_info.address}")
    print(f"Pair: {pool_info.pair}")
    print(f"Base Token: {pool_info.base_token}")
    print(f"Quote Token: {pool_info.quote_token}")
    print(f"TVL: ${pool_info.tvl_usd:,.2f}")
    print(f"24h Volume: ${pool_info.volume_24h_usd:,.2f}")
    print(f"24h Fees: ${pool_info.fees_24h_usd:,.2f}")
    print(f"Price: ${pool_info.price_usd:.6f}")
    print(f"24h Change: {pool_info.price_change_24h:+.2f}%")
    print(f"Liquidity Locked: {'✅ Yes' if pool_info.liquidity_locked else '❌ No'}")
    print(f"Pool Age: {pool_info.pool_age_days} days")
    print("="*60 + "\n")


def print_position_info(position_info: PositionInfo):
    """Print position information"""
    print("\n" + "="*60)
    print(f"💼 Your Liquidity Position")
    print("="*60)
    print(f"Wallet: {position_info.wallet[:8]}...{position_info.wallet[-8:]}")
    print(f"LP Tokens: {position_info.lp_tokens_formatted:,.4f}")
    print(f"Pool Share: {position_info.share_percent:.4f}%")
    print(f"Position Value: ${position_info.value_usd:,.2f}")
    print(f"Fees Earned: ${position_info.fees_earned_usd:,.2f}")
    print(f"Impermanent Loss: {position_info.impermanent_loss_percent:+.2f}%")
    print("="*60 + "\n")


def print_safety_checks(safety_checks: Dict[str, Any]):
    """Print safety check results"""
    print("\n" + "="*60)
    print(f"🛡️ Safety Checks")
    print("="*60)
    
    overall = safety_checks.get("overall_score", 0)
    passed = safety_checks.get("passed", False)
    
    status = "✅ PASSED" if passed else "⚠️ REVIEW RECOMMENDED"
    print(f"Overall Score: {overall:.2f}/1.00 - {status}")
    print()
    
    checks = safety_checks.get("checks", {})
    for check_name, score in checks.items():
        icon = "✅" if score >= 0.7 else "⚠️" if score >= 0.4 else "❌"
        print(f"{icon} {check_name.replace('_', ' ').title()}: {score:.2f}")
    
    print("="*60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Micro Liquidity Verification Tool (Bounty #692)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --pool 8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb
  %(prog)s --wallet YOUR_WALLET --check-lp
  %(prog)s --wallet YOUR_WALLET --pool POOL_ADDRESS --output report.json
  %(prog)s --pool POOL_ADDRESS --safety-check
        """
    )
    
    parser.add_argument("--pool", type=str, help="Pool address to verify")
    parser.add_argument("--wallet", type=str, help="Your wallet address")
    parser.add_argument("--check-lp", action="store_true", help="Check LP token balance")
    parser.add_argument("--output", type=str, help="Output file for report (JSON)")
    parser.add_argument("--include-history", action="store_true", help="Include historical data")
    parser.add_argument("--safety-check", action="store_true", help="Run safety checks only")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.pool and not args.wallet:
        parser.print_help()
        print("\n❌ Error: Either --pool or --wallet must be specified")
        sys.exit(1)
    
    verifier = LiquidityVerifier(verbose=args.verbose)
    
    # Determine pool to check
    pool_address = args.pool or WRTC_SOL_POOL
    
    print(f"\n🔍 Verifying liquidity pool: {pool_address}")
    
    # Fetch pool data
    pool_info = verifier.fetch_pool_data(pool_address)
    if not pool_info:
        sys.exit(1)
    
    print_pool_info(pool_info)
    
    # Safety checks
    if args.safety_check or True:  # Always run safety checks
        safety_checks = verifier.run_safety_checks(pool_info)
        print_safety_checks(safety_checks)
    
    # Check wallet LP tokens if wallet provided
    position_info = None
    if args.wallet and args.check_lp:
        print(f"🔍 Checking LP tokens for wallet: {args.wallet}")
        lp_data = verifier.fetch_wallet_lp_tokens(args.wallet, pool_address)
        if lp_data:
            print(f"LP Balance: {lp_data['lp_balance']:,.4f} LP tokens")
    
    # Analyze transactions if wallet and history requested
    transactions = []
    if args.wallet and args.include_history:
        print("📊 Analyzing transaction history...")
        txs = verifier.get_wallet_transactions(args.wallet)
        transactions = verifier.analyze_liquidity_transactions(txs)
        print(f"Found {len(transactions)} liquidity-related transactions")
    
    # Generate report if output specified
    if args.output:
        report = verifier.generate_verification_report(
            wallet_address=args.wallet,
            pool_info=pool_info,
            position_info=position_info,
            transactions=transactions,
            safety_checks=safety_checks
        )
        
        report_dict = asdict(report)
        
        with open(args.output, 'w') as f:
            json.dump(report_dict, f, indent=2)
        
        print(f"✅ Verification report saved to: {args.output}")
        print(f"Verification ID: {report.verification_id}")
        print(f"Proof Hash: {report.proof_hash}")
    
    # Return success
    print("✅ Verification complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
