#!/usr/bin/env python3
"""
SPL Token Verification Script

Verify wRTC token deployment configuration and security settings.

Usage:
    python verify.py --mint-address <MINT_ADDRESS> --network devnet
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from spl_deployment import (
    SPLTokenDeployment,
    load_config_from_file,
    hash_config
)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Verify wRTC SPL Token deployment"
    )
    
    parser.add_argument(
        "--mint-address",
        type=str,
        required=True,
        help="Token mint address to verify"
    )
    
    parser.add_argument(
        "--network",
        choices=["devnet", "testnet", "mainnet", "localnet"],
        default="devnet",
        help="Solana network (default: devnet)"
    )
    
    parser.add_argument(
        "--config",
        type=str,
        help="Expected configuration file for comparison"
    )
    
    parser.add_argument(
        "--output",
        type=str,
        default="verification-report.json",
        help="Output file for verification report"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    return parser.parse_args()


def get_rpc_url(network: str) -> str:
    """Get RPC URL for specified network."""
    urls = {
        "devnet": "https://api.devnet.solana.com",
        "testnet": "https://api.testnet.solana.com",
        "mainnet": "https://api.mainnet-beta.solana.com",
        "localnet": "http://localhost:8899"
    }
    return urls.get(network, urls["devnet"])


def verify_deployment(mint_address: str, rpc_url: str, config_path: str = None):
    """Verify token deployment."""
    from solders.pubkey import Pubkey
    
    print(f"🔍 Verifying wRTC deployment...")
    print(f"   Mint: {mint_address}")
    print(f"   Network: {rpc_url}")
    print()
    
    # Initialize deployment client
    deployment = SPLTokenDeployment(rpc_url)
    deployment.mint_address = Pubkey.from_string(mint_address)
    
    # Run verification
    verification = deployment.verify_deployment()
    
    # Add config comparison if provided
    if config_path:
        print("📋 Comparing with expected configuration...")
        expected_config = load_config_from_file(config_path)
        verification["expected_config_hash"] = hash_config(expected_config)
    
    # Add timestamp
    verification["verification_timestamp"] = datetime.utcnow().isoformat()
    
    return verification


def print_report(verification: dict, verbose: bool = False):
    """Print verification report."""
    print("=" * 60)
    print("VERIFICATION REPORT")
    print("=" * 60)
    print()
    
    status = verification.get("status", "unknown")
    status_icon = "✅" if status == "success" else "❌"
    print(f"{status_icon} Status: {status}")
    print()
    
    if "mint_address" in verification:
        print(f"🪙 Mint Address: {verification['mint_address']}")
    
    if "network" in verification:
        print(f"🌐 Network: {verification['network']}")
    
    print()
    print("📊 Verification Checks:")
    print("-" * 40)
    
    checks = verification.get("checks", {})
    for check_name, check_result in checks.items():
        if isinstance(check_result, dict):
            print(f"\n  {check_name}:")
            for key, value in check_result.items():
                icon = "✅" if value else "❌" if isinstance(value, bool) else "ℹ️"
                print(f"    {icon} {key}: {value}")
        else:
            icon = "✅" if check_result else "❌" if isinstance(check_result, bool) else "ℹ️"
            print(f"  {icon} {check_name}: {check_result}")
    
    if verbose and "expected_config_hash" in verification:
        print()
        print("📋 Configuration Comparison:")
        print(f"   Expected config hash: {verification['expected_config_hash']}")
    
    print()
    print("=" * 60)


def main():
    """Main entry point."""
    args = parse_args()
    rpc_url = get_rpc_url(args.network)
    
    try:
        verification = verify_deployment(args.mint_address, rpc_url, args.config)
        print_report(verification, args.verbose)
        
        # Save report
        with open(args.output, 'w') as f:
            json.dump(verification, f, indent=2)
        
        print(f"📄 Report saved to: {args.output}")
        
        # Exit with appropriate code
        sys.exit(0 if verification.get("status") == "success" else 1)
        
    except Exception as e:
        print(f"❌ Verification failed: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
