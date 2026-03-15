#!/usr/bin/env python3
"""
Spectrum DEX Integration - Dry Run Pair Check
==============================================

Script to verify Spectrum DEX integration and check RTC/ERG pair status.

Usage:
    python scripts/spectrum_pair_check.py [--testnet]

Requirements:
    - requests library
    - Spectrum API access
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from integrations.spectrum.client import SpectrumClient, erg_to_nanoerg, nanoerg_to_erg

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [SPECTRUM] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


def check_api_health(client: SpectrumClient) -> bool:
    """Check Spectrum API health"""
    logger.info("Checking Spectrum API health...")
    healthy = client.health_check()
    logger.info(f"API Health: {'✅ OK' if healthy else '❌ FAILED'}")
    return healthy


def check_pool_exists(client: SpectrumClient) -> bool:
    """Check if RTC/ERG pool exists"""
    logger.info("Checking for RTC/ERG pool...")
    pool = client.get_rtc_erg_pool()
    
    if pool:
        logger.info(f"✅ Pool found: {pool.id}")
        logger.info(f"   Price: {pool.price} ERG/RTC")
        logger.info(f"   Reserves: {pool.base_reserve} RTC / {pool.quote_reserve} ERG")
        logger.info(f"   LP Supply: {pool.lp_token_supply}")
        logger.info(f"   Fee: {pool.fee}%")
        return True
    else:
        logger.warning("❌ RTC/ERG pool not found")
        logger.info("   Pool needs to be created on Spectrum Finance")
        return False


def list_top_pools(client: SpectrumClient, limit: int = 10):
    """List top pools by TVL"""
    logger.info(f"Top {limit} pools by TVL:")
    pools = client.get_pools(limit=limit)
    
    for i, pool in enumerate(pools, 1):
        print(f"  {i}. {pool.base_token_name}/{pool.quote_token_name}")
        print(f"     Price: {pool.price}")
        print(f"     Fee: {pool.fee}%")


def check_token_info(client: SpectrumClient, token_id: str):
    """Check token information"""
    logger.info(f"Checking token: {token_id}")
    info = client.get_token_info(token_id)
    
    if info:
        logger.info(f"✅ Token found:")
        logger.info(f"   Name: {info.get('name', 'Unknown')}")
        logger.info(f"   Symbol: {info.get('symbol', 'Unknown')}")
        logger.info(f"   Decimals: {info.get('decimals', 0)}")
        return info
    else:
        logger.warning(f"❌ Token not found: {token_id}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Spectrum DEX Pair Check")
    parser.add_argument("--testnet", action="store_true", help="Use testnet")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()
    
    # Configuration
    rtc_token_id = os.environ.get("RTC_TOKEN_ID", "")
    
    logger.info("=" * 60)
    logger.info("Spectrum DEX Integration Check")
    logger.info("=" * 60)
    logger.info(f"API URL: {os.environ.get('SPECTRUM_API_URL', 'https://api.spectrum.fi/v1')}")
    logger.info(f"RTC Token ID: {rtc_token_id or 'NOT SET'}")
    logger.info(f"Testnet: {args.testnet}")
    logger.info("")
    
    # Initialize client
    client = SpectrumClient()
    
    # Run checks
    results = {
        "timestamp": datetime.now().isoformat(),
        "api_health": False,
        "pool_exists": False,
        "token_info": None
    }
    
    # 1. API Health
    results["api_health"] = check_api_health(client)
    print()
    
    # 2. Pool Check
    results["pool_exists"] = check_pool_exists(client)
    print()
    
    # 3. Token Info (if configured)
    if rtc_token_id:
        token_info = check_token_info(client, rtc_token_id)
        results["token_info"] = token_info
        print()
    
    # 4. Top Pools
    list_top_pools(client)
    print()
    
    # Summary
    logger.info("=" * 60)
    logger.info("Summary")
    logger.info("=" * 60)
    
    if results["api_health"]:
        logger.info("✅ Spectrum API is accessible")
    else:
        logger.error("❌ Spectrum API is not accessible")
    
    if results["pool_exists"]:
        logger.info("✅ RTC/ERG pool exists and is tradable")
    else:
        logger.warning("⚠️  RTC/ERG pool does not exist yet")
        logger.info("   Next steps:")
        logger.info("   1. Issue RTC token on Ergo")
        logger.info("   2. Create liquidity pool on Spectrum Finance")
        logger.info("   3. Add initial liquidity")
    
    # JSON output
    if args.json:
        print("\n" + json.dumps(results, indent=2, default=str))
    
    # Return status code
    if results["api_health"]:
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
