#!/usr/bin/env python3
"""
wRTC SPL Token Deployment Script

This script automates the deployment of wRTC (wrapped RustChain) as a Solana SPL Token.
Supports both testnet (devnet) and mainnet deployments.

Usage:
    # Testnet deployment
    python deploy.py --network devnet --config config/testnet-config.json

    # Mainnet deployment (requires confirmation)
    python deploy.py --network mainnet --config config/mainnet-config.json --confirm

    # Verification only
    python deploy.py --verify --mint-address <MINT_ADDRESS>
"""

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from spl_deployment import (
    SPLTokenDeployment,
    TokenConfig,
    MultiSigConfig,
    BridgeEscrowConfig,
    BridgeIntegration,
    load_config_from_file,
    save_config_to_file,
    hash_config
)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Deploy wRTC SPL Token on Solana",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Deploy to devnet
  python deploy.py --network devnet --config config/testnet-config.json

  # Deploy to mainnet (requires --confirm flag)
  python deploy.py --network mainnet --config config/mainnet-config.json --confirm

  # Verify existing deployment
  python deploy.py --verify --mint-address 12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X

  # Generate deployment report
  python deploy.py --report --config config/mainnet-config.json
        """
    )
    
    parser.add_argument(
        "--network",
        choices=["devnet", "testnet", "mainnet", "localnet"],
        default="devnet",
        help="Solana network to deploy to (default: devnet)"
    )
    
    parser.add_argument(
        "--config",
        type=str,
        default="config/default-config.json",
        help="Path to configuration JSON file"
    )
    
    parser.add_argument(
        "--keypair",
        type=str,
        default=os.environ.get("SOLANA_KEYPAIR", "~/.config/solana/id.json"),
        help="Path to Solana keypair file (default: $SOLANA_KEYPAIR or ~/.config/solana/id.json)"
    )
    
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirm mainnet deployment (required for mainnet)"
    )
    
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify existing deployment instead of deploying"
    )
    
    parser.add_argument(
        "--mint-address",
        type=str,
        help="Mint address to verify (required with --verify)"
    )
    
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate deployment report without deploying"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate deployment without sending transactions"
    )
    
    parser.add_argument(
        "--output",
        type=str,
        default="deployment-output.json",
        help="Output file for deployment artifacts"
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


def load_keypair(keypair_path: str):
    """Load Solana keypair from file."""
    from solders.keypair import Keypair
    
    path = Path(keypair_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Keypair not found: {path}")
    
    with open(path, 'r') as f:
        keypair_data = json.load(f)
    
    return Keypair.from_bytes(keypair_data)


def deploy_testnet(args):
    """Deploy to testnet (devnet)."""
    print("🚀 Deploying wRTC to Solana Devnet...")
    print(f"   Config: {args.config}")
    print(f"   Keypair: {args.keypair}")
    
    # Load configuration
    config_data = load_config_from_file(args.config)
    token_config = TokenConfig(**config_data.get("token", {}))
    
    # Initialize deployment
    rpc_url = get_rpc_url(args.network)
    
    if args.dry_run:
        print("\n📝 DRY RUN MODE - No transactions will be sent")
        print(f"\nToken Configuration:")
        print(f"  Name: {token_config.name}")
        print(f"  Symbol: {token_config.symbol}")
        print(f"  Decimals: {token_config.decimals}")
        print(f"\nNetwork: {args.network} ({rpc_url})")
        return {"status": "dry_run", "config": token_config.to_metadata()}
    
    # Initialize deployment (only when not dry-run)
    deployment = SPLTokenDeployment(rpc_url)
    
    # Load keypair
    try:
        keypair = load_keypair(args.keypair)
        print(f"   Deployer: {keypair.pubkey()}")
    except Exception as e:
        print(f"   ⚠️  Keypair not loaded (simulation mode)")
        # Continue without actual deployment
        return {"status": "simulated", "config": token_config.to_metadata()}
    
    # Deploy token
    try:
        mint_address = deployment.deploy_token(token_config, keypair)
        print(f"\n✅ Token deployed successfully!")
        print(f"   Mint Address: {mint_address}")
        
        # Create escrow account
        escrow_config = BridgeEscrowConfig(**config_data.get("escrow", {}))
        escrow_account = deployment.create_escrow_account(keypair, keypair.pubkey())
        print(f"   Escrow Account: {escrow_account}")
        
        # Verify deployment
        verification = deployment.verify_deployment()
        
        # Save deployment artifacts
        artifacts = {
            "status": "success",
            "network": args.network,
            "rpc_url": rpc_url,
            "mint_address": mint_address,
            "escrow_account": escrow_account,
            "token_config": token_config.to_metadata(),
            "verification": verification,
            "timestamp": datetime.utcnow().isoformat(),
            "config_hash": hash_config(config_data)
        }
        
        save_config_to_file(artifacts, args.output)
        print(f"\n📄 Deployment artifacts saved to: {args.output}")
        
        # Generate report
        report = deployment.generate_deployment_report(token_config)
        report_file = args.output.replace(".json", "-report.md")
        with open(report_file, 'w') as f:
            f.write(report)
        print(f"📊 Deployment report saved to: {report_file}")
        
        return artifacts
        
    except Exception as e:
        print(f"\n❌ Deployment failed: {str(e)}")
        return {"status": "failed", "error": str(e)}


def verify_deployment(args):
    """Verify existing deployment."""
    if not args.mint_address:
        print("❌ Error: --mint-address required for verification")
        return False
    
    print(f"🔍 Verifying wRTC deployment...")
    print(f"   Mint Address: {args.mint_address}")
    print(f"   Network: {args.network}")
    
    rpc_url = get_rpc_url(args.network)
    deployment = SPLTokenDeployment(rpc_url)
    
    # Set mint address for verification
    from solders.pubkey import Pubkey
    deployment.mint_address = Pubkey.from_string(args.mint_address)
    
    verification = deployment.verify_deployment()
    
    print(f"\n📊 Verification Results:")
    for check_name, check_result in verification.get("checks", {}).items():
        status = "✅" if check_result else "❌"
        print(f"   {status} {check_name}: {check_result}")
    
    # Save verification report
    verification["mint_address"] = args.mint_address
    verification["network"] = args.network
    verification["timestamp"] = datetime.utcnow().isoformat()
    
    save_config_to_file(verification, args.output)
    print(f"\n📄 Verification report saved to: {args.output}")
    
    return verification.get("status") == "success"


def generate_report(args):
    """Generate deployment report."""
    print("📊 Generating deployment report...")
    
    config_data = load_config_from_file(args.config)
    token_config = TokenConfig(**config_data.get("token", {}))
    
    rpc_url = get_rpc_url(args.network)
    deployment = SPLTokenDeployment(rpc_url)
    
    report = deployment.generate_deployment_report(token_config)
    
    # Output to stdout or file
    if args.output:
        report_file = args.output.replace(".json", "-report.md")
        with open(report_file, 'w') as f:
            f.write(report)
        print(f"Report saved to: {report_file}")
    else:
        print("\n" + report)
    
    return report


def main():
    """Main entry point."""
    args = parse_args()
    
    print("=" * 60)
    print("RustChain wRTC SPL Token Deployment")
    print("=" * 60)
    print()
    
    # Safety check for mainnet
    if args.network == "mainnet" and not args.confirm and not args.verify and not args.report:
        print("❌ ERROR: Mainnet deployment requires --confirm flag")
        print("   This is a destructive operation. Please confirm you understand the risks.")
        print()
        print("   Add --confirm to proceed, or use --verify to check existing deployment")
        sys.exit(1)
    
    if args.network == "mainnet" and args.confirm:
        print("⚠️  WARNING: You are about to deploy to MAINNET")
        print("   This will incur real SOL fees and create a production token.")
        print()
        response = input("Type 'CONFIRM' to proceed: ")
        if response != "CONFIRM":
            print("Deployment cancelled.")
            sys.exit(0)
    
    # Execute requested operation
    if args.verify:
        success = verify_deployment(args)
        sys.exit(0 if success else 1)
    
    elif args.report:
        generate_report(args)
        sys.exit(0)
    
    else:
        # Deploy
        result = deploy_testnet(args)
        
        if result.get("status") == "success":
            print("\n✅ Deployment completed successfully!")
            sys.exit(0)
        elif result.get("status") == "dry_run":
            print("\n✅ Dry run completed (no transactions sent)")
            sys.exit(0)
        elif result.get("status") == "simulated":
            print("\n✅ Simulation completed (keypair not loaded)")
            sys.exit(0)
        else:
            print("\n❌ Deployment failed")
            sys.exit(1)


if __name__ == "__main__":
    main()
