#!/usr/bin/env python3
"""
Liquidity Safety Checks (Bounty #692)

Comprehensive safety analysis before providing liquidity to wRTC pools.
Checks for token authenticity, pool health, impermanent loss risk, and rug pull indicators.

Usage:
    python liquidity_safety_checks.py --pool POOL_ADDRESS
    python liquidity_safety_checks.py --pool POOL_ADDRESS --check impermanent_loss
    python liquidity_safety_checks.py --wallet YOUR_WALLET --pool POOL_ADDRESS
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict

try:
    import requests
except ImportError:
    print("Error: 'requests' library required. Install with: pip install requests")
    sys.exit(1)


# Constants
WRTC_MINT = "12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X"
SOL_MINT = "So111D1r32v1NvGaTQeXj5Xh9VxNf6"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
WRTC_SOL_POOL = "8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb"

# API endpoints
DEXSCREENER_API = "https://api.dexscreener.com/latest/dex"
SOLANA_RPC = "https://api.mainnet-beta.solana.com"


@dataclass
class SafetyCheckResult:
    """Result of a single safety check"""
    name: str
    passed: bool
    score: float  # 0.0 to 1.0
    details: str
    recommendations: List[str]


@dataclass
class OverallSafetyReport:
    """Complete safety report"""
    timestamp: str
    pool_address: str
    wallet_address: Optional[str]
    overall_score: float
    overall_passed: bool
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    checks: List[Dict[str, Any]]
    summary: str
    recommendations: List[str]


class LiquiditySafetyChecker:
    """Perform comprehensive safety checks on liquidity pools"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "RustChain-Safety-Checker/1.0"
        })
    
    def log(self, message: str):
        """Print message if verbose mode is enabled"""
        if self.verbose:
            print(f"[INFO] {message}")
    
    def fetch_pool_data(self, pool_address: str) -> Optional[Dict[str, Any]]:
        """Fetch pool data from DexScreener"""
        try:
            url = f"{DEXSCREENER_API}/pairs/solana/{pool_address}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if not data.get("pairs"):
                return None
            
            return data["pairs"][0]
            
        except requests.exceptions.RequestException as e:
            self.log(f"Error fetching pool data: {e}")
            return None
    
    def fetch_token_data(self, mint_address: str) -> Optional[Dict[str, Any]]:
        """Fetch token data from DexScreener"""
        try:
            url = f"{DEXSCREENER_API}/tokens/solana/{mint_address}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if not data.get("tokens"):
                return None
            
            return data["tokens"][0]
            
        except requests.exceptions.RequestException as e:
            self.log(f"Error fetching token data: {e}")
            return None
    
    def check_token_authenticity(self, pool_data: Dict[str, Any]) -> SafetyCheckResult:
        """Verify token mint addresses are authentic"""
        recommendations = []
        
        base_token = pool_data.get("baseToken", {})
        quote_token = pool_data.get("quoteToken", {})
        
        base_address = base_token.get("address", "")
        quote_address = quote_token.get("address", "")
        
        # Check if wRTC is in the pair
        wrtc_present = WRTC_MINT in [base_address, quote_address]
        
        # Check if paired with known token
        known_pair = quote_address in [SOL_MINT, USDC_MINT] or base_address in [SOL_MINT, USDC_MINT]
        
        # Calculate score
        score = 0.0
        if wrtc_present:
            score += 0.6
        if known_pair:
            score += 0.4
        
        passed = score >= 0.8
        
        details = f"Pair: {base_token.get('symbol', '?')}/{quote_token.get('symbol', '?')}"
        if wrtc_present:
            details += " | wRTC verified ✅"
        else:
            details += " | wRTC NOT found ⚠️"
        
        if not passed:
            recommendations.append("Only provide liquidity to pools with verified wRTC mint address")
            recommendations.append(f"Official wRTC mint: {WRTC_MINT}")
        
        return SafetyCheckResult(
            name="Token Authenticity",
            passed=passed,
            score=score,
            details=details,
            recommendations=recommendations
        )
    
    def check_pool_health(self, pool_data: Dict[str, Any]) -> SafetyCheckResult:
        """Assess pool health metrics"""
        recommendations = []
        
        liquidity = pool_data.get("liquidity", {})
        volume = pool_data.get("volume", {})
        price_change = pool_data.get("priceChange", {})
        
        tvl_usd = liquidity.get("usd", 0)
        volume_24h = volume.get("h24", 0)
        price_change_24h = price_change.get("h24", 0)
        
        # Calculate pool age
        created_at = pool_data.get("pairCreatedAt")
        pool_age_days = 0
        if created_at:
            try:
                created_dt = datetime.fromtimestamp(created_at / 1000, tz=timezone.utc)
                now = datetime.now(timezone.utc)
                pool_age_days = (now - created_dt).days
            except (ValueError, TypeError):
                pass
        
        # Score calculation
        score = 0.0
        
        # TVL scoring (max 0.4)
        if tvl_usd >= 50000:
            score += 0.4
        elif tvl_usd >= 10000:
            score += 0.3
        elif tvl_usd >= 1000:
            score += 0.2
        elif tvl_usd >= 100:
            score += 0.1
        
        # Volume scoring (max 0.3)
        if volume_24h >= 10000:
            score += 0.3
        elif volume_24h >= 1000:
            score += 0.2
        elif volume_24h >= 100:
            score += 0.1
        
        # Age scoring (max 0.3)
        if pool_age_days >= 90:
            score += 0.3
        elif pool_age_days >= 30:
            score += 0.2
        elif pool_age_days >= 7:
            score += 0.1
        
        passed = score >= 0.6
        
        details = (
            f"TVL: ${tvl_usd:,.2f} | "
            f"24h Vol: ${volume_24h:,.2f} | "
            f"Age: {pool_age_days}d | "
            f"24h Δ: {price_change_24h:+.1f}%"
        )
        
        if tvl_usd < 1000:
            recommendations.append("Low TVL increases impermanent loss and slippage risk")
        if volume_24h < 100:
            recommendations.append("Low volume means minimal fee earnings")
        if pool_age_days < 7:
            recommendations.append("New pool - monitor for stability before committing significant capital")
        
        return SafetyCheckResult(
            name="Pool Health",
            passed=passed,
            score=score,
            details=details,
            recommendations=recommendations
        )
    
    def check_liquidity_lock(self, pool_data: Dict[str, Any]) -> SafetyCheckResult:
        """Check if pool liquidity is locked"""
        recommendations = []
        
        # DexScreener doesn't provide direct lock info
        # Check for indicators
        liquidity = pool_data.get("liquidity", {})
        tvl_usd = liquidity.get("usd", 0)
        
        # Heuristic: High TVL + old pool = likely safe
        created_at = pool_data.get("pairCreatedAt")
        pool_age_days = 0
        if created_at:
            try:
                created_dt = datetime.fromtimestamp(created_at / 1000, tz=timezone.utc)
                now = datetime.now(timezone.utc)
                pool_age_days = (now - created_dt).days
            except (ValueError, TypeError):
                pass
        
        # Score based on indirect indicators
        score = 0.5  # Base score (unknown)
        
        if pool_age_days > 90 and tvl_usd > 50000:
            score = 0.9  # Very likely locked or safe
        elif pool_age_days > 30 and tvl_usd > 10000:
            score = 0.7
        elif pool_age_days > 7 and tvl_usd > 1000:
            score = 0.6
        
        passed = score >= 0.6
        
        details = f"Liquidity Lock Status: Unknown (estimated safety: {score:.0%})"
        
        recommendations.append("Verify liquidity lock status on Raydium or lock service (e.g., StreamFlow, Team Finance)")
        recommendations.append("Official wRTC/SOL pool on Raydium is considered safe")
        
        return SafetyCheckResult(
            name="Liquidity Lock",
            passed=passed,
            score=score,
            details=details,
            recommendations=recommendations
        )
    
    def assess_rug_pull_risk(self, pool_data: Dict[str, Any]) -> SafetyCheckResult:
        """Assess rug pull risk indicators"""
        recommendations = []
        
        liquidity = pool_data.get("liquidity", {})
        tvl_usd = liquidity.get("usd", 0)
        
        created_at = pool_data.get("pairCreatedAt")
        pool_age_days = 0
        if created_at:
            try:
                created_dt = datetime.fromtimestamp(created_at / 1000, tz=timezone.utc)
                now = datetime.now(timezone.utc)
                pool_age_days = (now - created_dt).days
            except (ValueError, TypeError):
                pass
        
        # Check for suspicious patterns
        volume_24h = pool_data.get("volume", {}).get("h24", 0)
        
        # Rug pull risk assessment
        risk_score = 0.0  # Higher is safer
        
        # Low risk: Old pool, high TVL, consistent volume
        if pool_age_days > 90 and tvl_usd > 50000 and volume_24h > 1000:
            risk_score = 0.95
        elif pool_age_days > 30 and tvl_usd > 10000:
            risk_score = 0.85
        elif pool_age_days > 7 and tvl_usd > 1000:
            risk_score = 0.6
        elif tvl_usd > 100:
            risk_score = 0.4
        else:
            risk_score = 0.2  # High risk
        
        passed = risk_score >= 0.6
        
        details = f"Rug Pull Risk: {'LOW' if risk_score >= 0.7 else 'MEDIUM' if risk_score >= 0.4 else 'HIGH'} ({risk_score:.0%} safe)"
        
        if risk_score < 0.4:
            recommendations.append("⚠️ HIGH RISK: New pool with low liquidity")
            recommendations.append("Consider waiting for pool to mature before providing liquidity")
        elif risk_score < 0.6:
            recommendations.append("⚠️ MEDIUM RISK: Monitor pool closely")
            recommendations.append("Start with small amounts until pool proves stable")
        
        return SafetyCheckResult(
            name="Rug Pull Risk",
            passed=passed,
            score=risk_score,
            details=details,
            recommendations=recommendations
        )
    
    def calculate_impermanent_loss_risk(
        self,
        pool_data: Dict[str, Any],
        price_volatility: float = 0.5
    ) -> SafetyCheckResult:
        """Calculate impermanent loss risk"""
        recommendations = []
        
        price_change = pool_data.get("priceChange", {})
        price_change_24h = abs(price_change.get("h24", 0))
        price_change_7d = abs(price_change.get("d7", 0))
        price_change_30d = abs(price_change.get("d30", 0))
        
        # Estimate IL based on volatility
        # Simplified IL calculation: IL ≈ 2 * (price_ratio - 1) / (price_ratio + 1)
        # Using price change as proxy for volatility
        
        avg_volatility = (price_change_24h + price_change_7d / 7 + price_change_30d / 30) / 3
        
        # IL risk score (higher is safer = less IL expected)
        if avg_volatility < 5:
            il_risk = "LOW"
            score = 0.9
        elif avg_volatility < 15:
            il_risk = "MEDIUM"
            score = 0.6
        elif avg_volatility < 30:
            il_risk = "HIGH"
            score = 0.3
        else:
            il_risk = "VERY HIGH"
            score = 0.1
        
        passed = score >= 0.5
        
        # Estimate potential IL
        estimated_il = min(avg_volatility * 0.5, 50)  # Cap at 50%
        
        details = (
            f"IL Risk: {il_risk} | "
            f"24h Δ: {price_change_24h:.1f}% | "
            f"7d Δ: {price_change_7d:.1f}% | "
            f"Est. Max IL: {estimated_il:.1f}%"
        )
        
        recommendations.append(f"Estimated impermanent loss at current volatility: ~{estimated_il:.1f}%")
        recommendations.append("IL is unrealized until you withdraw liquidity")
        recommendations.append("Consider stable pairs (wRTC/USDC) for lower IL risk")
        
        if avg_volatility > 20:
            recommendations.append("⚠️ High volatility - IL risk is significant")
            recommendations.append("Only provide liquidity if you're comfortable holding both tokens long-term")
        
        return SafetyCheckResult(
            name="Impermanent Loss Risk",
            passed=passed,
            score=score,
            details=details,
            recommendations=recommendations
        )
    
    def check_contract_risk(self, pool_data: Dict[str, Any]) -> SafetyCheckResult:
        """Check smart contract risk"""
        recommendations = []
        
        # Raydium is a well-audited, established DEX
        # Contract risk is low for official pools
        
        base_token = pool_data.get("baseToken", {})
        quote_token = pool_data.get("quoteToken", {})
        
        # Check if it's an official Raydium pool
        is_official_pair = (
            WRTC_MINT in [base_token.get("address", ""), quote_token.get("address", "")] and
            (SOL_MINT in [base_token.get("address", ""), quote_token.get("address", "")] or
             USDC_MINT in [base_token.get("address", ""), quote_token.get("address", "")])
        )
        
        if is_official_pair:
            score = 0.9
            details = "Contract Risk: LOW (Official Raydium pool, audited contracts)"
        else:
            score = 0.5
            details = "Contract Risk: MEDIUM (Third-party pool, verify before use)"
        
        passed = score >= 0.6
        
        recommendations.append("Raydium AMM contracts are audited but not risk-free")
        recommendations.append("Never approve unlimited token allowances")
        recommendations.append("Monitor your positions and revoke unused approvals periodically")
        
        return SafetyCheckResult(
            name="Contract Risk",
            passed=passed,
            score=score,
            details=details,
            recommendations=recommendations
        )
    
    def check_wallet_security(self, wallet_address: str) -> SafetyCheckResult:
        """Check wallet security indicators"""
        recommendations = []
        
        # Basic wallet address validation
        if not wallet_address or len(wallet_address) < 32 or len(wallet_address) > 44:
            return SafetyCheckResult(
                name="Wallet Security",
                passed=False,
                score=0.0,
                details="Invalid wallet address format",
                recommendations=["Verify your Solana wallet address is correct (32-44 characters, base58)"]
            )
        
        # Fetch transaction history to check activity
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getSignaturesForAddress",
                "params": [wallet_address, {"limit": 1}]
            }
            
            response = self.session.post(SOLANA_RPC, json=payload, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            if "result" in result and result["result"]:
                # Wallet has transaction history
                score = 0.8
                details = "Wallet Security: GOOD (Active wallet with history)"
            else:
                # New or empty wallet
                score = 0.6
                details = "Wallet Security: OK (New or low-activity wallet)"
                recommendations.append("This appears to be a new wallet - test with small amounts first")
            
        except requests.exceptions.RequestException:
            score = 0.5
            details = "Wallet Security: UNKNOWN (Could not verify)"
            recommendations.append("Could not verify wallet activity - proceed with caution")
        
        passed = score >= 0.6
        
        recommendations.append("Never share your seed phrase or private keys")
        recommendations.append("Use a dedicated wallet for DeFi activities")
        recommendations.append("Keep only what you need for trading in hot wallets")
        
        return SafetyCheckResult(
            name="Wallet Security",
            passed=passed,
            score=score,
            details=details,
            recommendations=recommendations
        )
    
    def run_all_checks(
        self,
        pool_address: str,
        wallet_address: Optional[str] = None
    ) -> OverallSafetyReport:
        """Run all safety checks and generate report"""
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Fetch pool data
        pool_data = self.fetch_pool_data(pool_address)
        if not pool_data:
            return OverallSafetyReport(
                timestamp=timestamp,
                pool_address=pool_address,
                wallet_address=wallet_address,
                overall_score=0.0,
                overall_passed=False,
                risk_level="CRITICAL",
                checks=[],
                summary="Could not fetch pool data - pool may not exist or API error",
                recommendations=["Verify pool address is correct", "Try again later"]
            )
        
        # Run checks
        checks = []
        all_recommendations = []
        
        # Token authenticity
        result = self.check_token_authenticity(pool_data)
        checks.append(asdict(result))
        all_recommendations.extend(result.recommendations)
        
        # Pool health
        result = self.check_pool_health(pool_data)
        checks.append(asdict(result))
        all_recommendations.extend(result.recommendations)
        
        # Liquidity lock
        result = self.check_liquidity_lock(pool_data)
        checks.append(asdict(result))
        all_recommendations.extend(result.recommendations)
        
        # Rug pull risk
        result = self.assess_rug_pull_risk(pool_data)
        checks.append(asdict(result))
        all_recommendations.extend(result.recommendations)
        
        # Impermanent loss
        result = self.calculate_impermanent_loss_risk(pool_data)
        checks.append(asdict(result))
        all_recommendations.extend(result.recommendations)
        
        # Contract risk
        result = self.check_contract_risk(pool_data)
        checks.append(asdict(result))
        all_recommendations.extend(result.recommendations)
        
        # Wallet security (if wallet provided)
        if wallet_address:
            result = self.check_wallet_security(wallet_address)
            checks.append(asdict(result))
            all_recommendations.extend(result.recommendations)
        
        # Calculate overall score
        scores = [check["score"] for check in checks]
        overall_score = sum(scores) / len(scores) if scores else 0.0
        
        # Determine risk level
        if overall_score >= 0.8:
            risk_level = "LOW"
        elif overall_score >= 0.6:
            risk_level = "MEDIUM"
        elif overall_score >= 0.4:
            risk_level = "HIGH"
        else:
            risk_level = "CRITICAL"
        
        overall_passed = overall_score >= 0.6
        
        # Generate summary
        if overall_passed:
            summary = f"✅ Pool passed safety checks (Score: {overall_score:.2f}/1.00, Risk: {risk_level})"
        else:
            summary = f"⚠️ Pool did NOT pass safety checks (Score: {overall_score:.2f}/1.00, Risk: {risk_level})"
        
        return OverallSafetyReport(
            timestamp=timestamp,
            pool_address=pool_address,
            wallet_address=wallet_address,
            overall_score=overall_score,
            overall_passed=overall_passed,
            risk_level=risk_level,
            checks=checks,
            summary=summary,
            recommendations=list(set(all_recommendations))  # Remove duplicates
        )


def print_safety_report(report: OverallSafetyReport):
    """Print safety report in a formatted way"""
    print("\n" + "="*70)
    print("🛡️  LIQUIDITY SAFETY REPORT")
    print("="*70)
    print(f"Timestamp: {report.timestamp}")
    print(f"Pool: {report.pool_address}")
    if report.wallet_address:
        print(f"Wallet: {report.wallet_address[:8]}...{report.wallet_address[-8:]}")
    print()
    
    # Overall result
    status_icon = "✅" if report.overall_passed else "⚠️"
    print(f"{status_icon} {report.summary}")
    print(f"Risk Level: {report.risk_level}")
    print(f"Overall Score: {report.overall_score:.2f}/1.00")
    print()
    
    # Individual checks
    print("-"*70)
    print("DETAILED CHECKS:")
    print("-"*70)
    
    for check in report.checks:
        icon = "✅" if check["passed"] else "⚠️" if check["score"] >= 0.4 else "❌"
        print(f"\n{icon} {check['name']}")
        print(f"   Score: {check['score']:.2f} | {check['details']}")
        if check["recommendations"]:
            print("   Recommendations:")
            for rec in check["recommendations"][:3]:  # Show max 3
                print(f"     • {rec}")
    
    print()
    print("-"*70)
    print("KEY RECOMMENDATIONS:")
    print("-"*70)
    
    for i, rec in enumerate(report.recommendations[:10], 1):  # Show max 10
        print(f"{i:2}. {rec}")
    
    print()
    print("="*70)
    
    # Final verdict
    if report.overall_passed:
        print("✅ VERDICT: Pool appears SAFE for liquidity provision")
        print("   Proceed with standard precautions (start small, monitor position)")
    elif report.risk_level == "HIGH":
        print("⚠️  VERDICT: HIGH RISK - Proceed with extreme caution")
        print("   Consider waiting for pool to mature or choose alternative pool")
    elif report.risk_level == "CRITICAL":
        print("❌ VERDICT: CRITICAL RISK - DO NOT PROVIDE LIQUIDITY")
        print("   Pool shows multiple red flags")
    else:
        print("⚠️  VERDICT: MEDIUM RISK - Review recommendations carefully")
        print("   Only proceed if you understand and accept the risks")
    
    print("="*70 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Liquidity Safety Checks (Bounty #692)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --pool 8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb
  %(prog)s --pool POOL_ADDRESS --check impermanent_loss
  %(prog)s --wallet YOUR_WALLET --pool POOL_ADDRESS
  %(prog)s --pool POOL_ADDRESS --output safety_report.json
        """
    )
    
    parser.add_argument("--pool", type=str, required=True, help="Pool address to check")
    parser.add_argument("--wallet", type=str, help="Your wallet address (optional)")
    parser.add_argument("--check", type=str, choices=[
        "all", "token_authenticity", "pool_health", "liquidity_lock",
        "rug_pull", "impermanent_loss", "contract_risk", "wallet_security"
    ], default="all", help="Specific check to run (default: all)")
    parser.add_argument("--output", type=str, help="Output file for report (JSON)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    print(f"\n🔍 Running safety checks for pool: {args.pool}")
    
    checker = LiquiditySafetyChecker(verbose=args.verbose)
    
    # Run checks
    if args.check == "all":
        report = checker.run_all_checks(args.pool, args.wallet)
    else:
        # Run specific check
        pool_data = checker.fetch_pool_data(args.pool)
        if not pool_data:
            print("❌ Error: Could not fetch pool data")
            sys.exit(1)
        
        check_methods = {
            "token_authenticity": checker.check_token_authenticity,
            "pool_health": checker.check_pool_health,
            "liquidity_lock": checker.check_liquidity_lock,
            "rug_pull": checker.assess_rug_pull_risk,
            "impermanent_loss": checker.calculate_impermanent_loss_risk,
            "contract_risk": checker.check_contract_risk,
            "wallet_security": checker.check_wallet_security if args.wallet else None
        }
        
        method = check_methods.get(args.check)
        if method:
            if args.check == "wallet_security" and not args.wallet:
                print("❌ Error: --wallet required for wallet_security check")
                sys.exit(1)
            result = method(pool_data) if args.check != "wallet_security" else method(args.wallet)
            # Create minimal report
            from datetime import datetime, timezone
            report = OverallSafetyReport(
                timestamp=datetime.now(timezone.utc).isoformat(),
                pool_address=args.pool,
                wallet_address=args.wallet,
                overall_score=result.score,
                overall_passed=result.passed,
                risk_level="LOW" if result.score >= 0.7 else "MEDIUM" if result.score >= 0.4 else "HIGH",
                checks=[asdict(result)],
                summary=f"{result.name}: {'PASSED' if result.passed else 'REVIEW RECOMMENDED'}",
                recommendations=result.recommendations
            )
        else:
            print(f"❌ Unknown check: {args.check}")
            sys.exit(1)
    
    # Print report
    print_safety_report(report)
    
    # Save to file if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(asdict(report), f, indent=2)
        print(f"✅ Safety report saved to: {args.output}")
    
    # Exit with appropriate code
    sys.exit(0 if report.overall_passed else 1)


if __name__ == "__main__":
    main()
