#!/usr/bin/env python3
"""
Spectrum Finance Pool Manager
==============================

Creates and manages RTC/ERG liquidity pool on Spectrum Finance.

Features:
- Pool creation with custom tokens
- Liquidity addition/removal
- Price initialization
- Pool monitoring
- Fee collection

Usage:
    from spectrum_pool_manager import SpectrumPoolManager
    
    manager = SpectrumPoolManager(
        api_key="your_api_key",
        node_host="http://localhost:9053",
        wallet_address="your_address"
    )
    
    # Create pool
    pool_id = manager.create_rtc_erg_pool(
        rtc_token_id="token_id",
        initial_rtc=1000 * 10**9,
        initial_erg=67 * 10**9
    )
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

# Spectrum Finance API Constants
SPECTRUM_API_BASE = "https://api.spectrum.fi"
SPECTRUM_TESTNET_API = "https://api-testnet.spectrum.fi"
DEFAULT_SLIPPAGE = 0.01  # 1% slippage tolerance
MIN_LIQUIDITY = 1000  # Minimum liquidity to prevent dust attacks


@dataclass
class PoolInfo:
    """Liquidity Pool Information"""
    pool_id: str
    base_token_id: str
    quote_token_id: str
    base_token_name: str
    quote_token_name: str
    base_reserve: int
    quote_reserve: int
    lp_token_id: str
    lp_token_supply: int
    fee: float
    price: float  # quote/base
    created_at: Optional[int] = None


@dataclass
class LiquidityPosition:
    """User's Liquidity Position"""
    pool_id: str
    lp_tokens: int
    base_share: float
    quote_share: float
    base_amount: int
    quote_amount: int
    fees_earned: int = 0


@dataclass
class PoolCreationConfig:
    """Pool Creation Configuration"""
    base_token_id: str
    quote_token_id: str
    base_amount: int
    quote_amount: int
    fee_tier: float = 0.003  # 0.3% default fee
    start_price: Optional[float] = None


class SpectrumAPI:
    """Spectrum Finance API Client"""
    
    def __init__(self, api_key: str, testnet: bool = False):
        self.api_key = api_key
        self.base_url = SPECTRUM_TESTNET_API if testnet else SPECTRUM_API_BASE
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        })
        self.testnet = testnet
    
    def health_check(self) -> bool:
        """Check API health"""
        try:
            response = self.session.get(f"{self.base_url}/v1/health", timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def get_pools(self, limit: int = 100) -> List[PoolInfo]:
        """Get all pools"""
        try:
            response = self.session.get(
                f"{self.base_url}/v1/pools",
                params={"limit": limit},
                timeout=10
            )
            response.raise_for_status()
            pools_data = response.json()
            
            pools = []
            for p in pools_data.get("items", []):
                pools.append(PoolInfo(
                    pool_id=p["id"],
                    base_token_id=p["baseToken"]["id"],
                    quote_token_id=p["quoteToken"]["id"],
                    base_token_name=p["baseToken"]["name"],
                    quote_token_name=p["quoteToken"]["name"],
                    base_reserve=int(p["baseReserve"]),
                    quote_reserve=int(p["quoteReserve"]),
                    lp_token_id=p["lpToken"]["id"],
                    lp_token_supply=int(p["lpTokenSupply"]),
                    fee=float(p["fee"]),
                    price=float(p["price"]),
                    created_at=p.get("createdAt")
                ))
            return pools
        except Exception as e:
            logger.error(f"Failed to get pools: {e}")
            return []
    
    def get_pool_by_id(self, pool_id: str) -> Optional[PoolInfo]:
        """Get pool by ID"""
        try:
            response = self.session.get(
                f"{self.base_url}/v1/pools/{pool_id}",
                timeout=10
            )
            if response.status_code == 200:
                p = response.json()
                return PoolInfo(
                    pool_id=p["id"],
                    base_token_id=p["baseToken"]["id"],
                    quote_token_id=p["quoteToken"]["id"],
                    base_token_name=p["baseToken"]["name"],
                    quote_token_name=p["quoteToken"]["name"],
                    base_reserve=int(p["baseReserve"]),
                    quote_reserve=int(p["quoteReserve"]),
                    lp_token_id=p["lpToken"]["id"],
                    lp_token_supply=int(p["lpTokenSupply"]),
                    fee=float(p["fee"]),
                    price=float(p["price"])
                )
            return None
        except Exception as e:
            logger.error(f"Failed to get pool: {e}")
            return None
    
    def get_pool_by_tokens(self, base_token_id: str, quote_token_id: str) -> Optional[PoolInfo]:
        """Find pool by token pair"""
        pools = self.get_pools(limit=500)
        for pool in pools:
            if (pool.base_token_id == base_token_id and 
                pool.quote_token_id == quote_token_id):
                return pool
            # Check reverse pair
            if (pool.base_token_id == quote_token_id and 
                pool.quote_token_id == base_token_id):
                # Return with swapped reserves
                return PoolInfo(
                    pool_id=pool.pool_id,
                    base_token_id=base_token_id,
                    quote_token_id=quote_token_id,
                    base_token_name="RTC",
                    quote_token_name="ERG",
                    base_reserve=pool.quote_reserve,
                    quote_reserve=pool.base_reserve,
                    lp_token_id=pool.lp_token_id,
                    lp_token_supply=pool.lp_token_supply,
                    fee=pool.fee,
                    price=1.0 / pool.price if pool.price > 0 else 0
                )
        return None
    
    def create_pool(self, config: PoolCreationConfig) -> str:
        """Create new liquidity pool"""
        try:
            pool_data = {
                "baseTokenId": config.base_token_id,
                "quoteTokenId": config.quote_token_id,
                "baseAmount": str(config.base_amount),
                "quoteAmount": str(config.quote_amount),
                "fee": config.fee_tier
            }
            
            if config.start_price:
                pool_data["startPrice"] = config.start_price
            
            response = self.session.post(
                f"{self.base_url}/v1/pools",
                json=pool_data,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            pool_id = result.get("poolId") or result.get("id")
            logger.info(f"Pool created: {pool_id}")
            return pool_id
        except Exception as e:
            logger.error(f"Failed to create pool: {e}")
            raise
    
    def add_liquidity(self, pool_id: str, base_amount: int, quote_amount: int, 
                      min_lp_tokens: int = 0) -> int:
        """Add liquidity to existing pool"""
        try:
            liquidity_data = {
                "poolId": pool_id,
                "baseAmount": str(base_amount),
                "quoteAmount": str(quote_amount),
                "minLpTokens": str(min_lp_tokens)
            }
            
            response = self.session.post(
                f"{self.base_url}/v1/pools/{pool_id}/liquidity",
                json=liquidity_data,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            lp_tokens = int(result.get("lpTokens", 0))
            logger.info(f"Added liquidity, received {lp_tokens} LP tokens")
            return lp_tokens
        except Exception as e:
            logger.error(f"Failed to add liquidity: {e}")
            raise
    
    def remove_liquidity(self, pool_id: str, lp_tokens: int, 
                         min_base: int = 0, min_quote: int = 0) -> Tuple[int, int]:
        """Remove liquidity from pool"""
        try:
            removal_data = {
                "poolId": pool_id,
                "lpTokens": str(lp_tokens),
                "minBaseAmount": str(min_base),
                "minQuoteAmount": str(min_quote)
            }
            
            response = self.session.post(
                f"{self.base_url}/v1/pools/{pool_id}/liquidity/remove",
                json=removal_data,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            base_amount = int(result.get("baseAmount", 0))
            quote_amount = int(result.get("quoteAmount", 0))
            logger.info(f"Removed liquidity: {base_amount} base, {quote_amount} quote")
            return base_amount, quote_amount
        except Exception as e:
            logger.error(f"Failed to remove liquidity: {e}")
            raise
    
    def get_price(self, base_token_id: str, quote_token_id: str) -> Optional[float]:
        """Get current price for token pair"""
        pool = self.get_pool_by_tokens(base_token_id, quote_token_id)
        if pool:
            return pool.price
        return None
    
    def calculate_optimal_deposit(self, pool_id: str, base_desired: int, 
                                   quote_desired: int) -> Tuple[int, int]:
        """Calculate optimal deposit amounts"""
        try:
            pool = self.get_pool_by_id(pool_id)
            if not pool:
                raise ValueError(f"Pool not found: {pool_id}")
            
            # Calculate optimal amounts based on current reserves
            quote_optimal = (base_desired * pool.quote_reserve) // pool.base_reserve
            
            if quote_optimal <= quote_desired:
                return base_desired, quote_optimal
            else:
                base_optimal = (quote_desired * pool.base_reserve) // pool.quote_reserve
                return base_optimal, quote_desired
        except Exception as e:
            logger.error(f"Failed to calculate optimal deposit: {e}")
            raise


class SpectrumPoolManager:
    """Main Pool Manager for RTC/ERG"""
    
    def __init__(self, api_key: str, node_host: str, wallet_address: str, 
                 testnet: bool = False):
        """
        Initialize pool manager
        
        Args:
            api_key: Spectrum API key
            node_host: Ergo node URL
            wallet_address: Wallet address for operations
            testnet: Use testnet
        """
        self.api = SpectrumAPI(api_key, testnet)
        self.node_host = node_host
        self.wallet_address = wallet_address
        self.testnet = testnet
        
        # Pool cache
        self.rtc_erg_pool: Optional[PoolInfo] = None
        self.positions: Dict[str, LiquidityPosition] = {}
    
    def check_api_health(self) -> bool:
        """Check Spectrum API health"""
        healthy = self.api.health_check()
        logger.info(f"Spectrum API Health: {'✅ OK' if healthy else '❌ FAILED'}")
        return healthy
    
    def rtc_erg_pool_exists(self, rtc_token_id: str) -> bool:
        """Check if RTC/ERG pool exists"""
        # ERG token ID on Ergo (native token)
        erg_token_id = "0000000000000000000000000000000000000000000000000000000000000000"
        
        pool = self.api.get_pool_by_tokens(rtc_token_id, erg_token_id)
        self.rtc_erg_pool = pool
        
        if pool:
            logger.info(f"✅ RTC/ERG pool found: {pool.pool_id}")
            logger.info(f"   Price: {pool.price} ERG/RTC")
            logger.info(f"   Reserves: {pool.base_reserve / 10**9} RTC / {pool.quote_reserve / 10**9} ERG")
            logger.info(f"   LP Supply: {pool.lp_token_supply}")
            logger.info(f"   Fee: {pool.fee * 100}%")
            return True
        else:
            logger.info("❌ RTC/ERG pool not found - needs creation")
            return False
    
    def create_rtc_erg_pool(self, rtc_token_id: str, initial_rtc: int, 
                            initial_erg: int, fee_tier: float = 0.003) -> str:
        """
        Create RTC/ERG liquidity pool
        
        Args:
            rtc_token_id: RTC token ID on Ergo
            initial_rtc: Initial RTC liquidity (in nanoRTC)
            initial_erg: Initial ERG liquidity (in nanoERG)
            fee_tier: Pool fee tier (default 0.3%)
        
        Returns:
            pool_id: Created pool ID
        """
        logger.info(f"Creating RTC/ERG pool...")
        logger.info(f"   Initial RTC: {initial_rtc / 10**9}")
        logger.info(f"   Initial ERG: {initial_erg / 10**9}")
        logger.info(f"   Initial Price: {initial_erg / initial_rtc:.6f} ERG/RTC")
        
        # ERG token ID (native)
        erg_token_id = "0000000000000000000000000000000000000000000000000000000000000000"
        
        # Calculate start price
        start_price = initial_erg / initial_rtc
        
        # Create pool configuration
        config = PoolCreationConfig(
            base_token_id=rtc_token_id,
            quote_token_id=erg_token_id,
            base_amount=initial_rtc,
            quote_amount=initial_erg,
            fee_tier=fee_tier,
            start_price=start_price
        )
        
        # Create pool
        pool_id = self.api.create_pool(config)
        
        # Cache pool info
        self.rtc_erg_pool = PoolInfo(
            pool_id=pool_id,
            base_token_id=rtc_token_id,
            quote_token_id=erg_token_id,
            base_token_name="RTC",
            quote_token_name="ERG",
            base_reserve=initial_rtc,
            quote_reserve=initial_erg,
            lp_token_id=f"LP_{pool_id}",
            lp_token_supply=MIN_LIQUIDITY,
            fee=fee_tier,
            price=start_price,
            created_at=int(time.time())
        )
        
        logger.info(f"✅ Pool created: {pool_id}")
        return pool_id
    
    def add_liquidity_to_pool(self, pool_id: str, rtc_amount: int, 
                               erg_amount: int) -> int:
        """
        Add liquidity to existing pool
        
        Args:
            pool_id: Pool ID
            rtc_amount: RTC amount (nanoRTC)
            erg_amount: ERG amount (nanoERG)
        
        Returns:
            lp_tokens: LP tokens received
        """
        logger.info(f"Adding liquidity to pool {pool_id}")
        logger.info(f"   RTC: {rtc_amount / 10**9}")
        logger.info(f"   ERG: {erg_amount / 10**9}")
        
        # Calculate optimal deposit
        base_optimal, quote_optimal = self.api.calculate_optimal_deposit(
            pool_id, rtc_amount, erg_amount
        )
        
        # Add liquidity
        lp_tokens = self.api.add_liquidity(
            pool_id=pool_id,
            base_amount=base_optimal,
            quote_amount=quote_optimal
        )
        
        # Store position
        pool = self.api.get_pool_by_id(pool_id)
        if pool:
            position = LiquidityPosition(
                pool_id=pool_id,
                lp_tokens=lp_tokens,
                base_share=lp_tokens / pool.lp_token_supply if pool.lp_token_supply > 0 else 0,
                quote_share=lp_tokens / pool.lp_token_supply if pool.lp_token_supply > 0 else 0,
                base_amount=base_optimal,
                quote_amount=quote_optimal
            )
            self.positions[pool_id] = position
        
        return lp_tokens
    
    def remove_liquidity_from_pool(self, pool_id: str, lp_tokens: int) -> Tuple[int, int]:
        """
        Remove liquidity from pool
        
        Args:
            pool_id: Pool ID
            lp_tokens: LP tokens to burn
        
        Returns:
            (rtc_amount, erg_amount): Amounts received
        """
        logger.info(f"Removing liquidity from pool {pool_id}")
        logger.info(f"   LP Tokens: {lp_tokens}")
        
        base_amount, quote_amount = self.api.remove_liquidity(
            pool_id=pool_id,
            lp_tokens=lp_tokens
        )
        
        # Update position
        if pool_id in self.positions:
            position = self.positions[pool_id]
            position.lp_tokens -= lp_tokens
            if position.lp_tokens <= 0:
                del self.positions[pool_id]
        
        return base_amount, quote_amount
    
    def get_pool_stats(self, pool_id: str) -> Dict:
        """Get pool statistics"""
        pool = self.api.get_pool_by_id(pool_id)
        if not pool:
            return {}
        
        # Calculate 24h volume (placeholder - would need historical data)
        volume_24h = 0
        fees_24h = volume_24h * pool.fee
        
        # Calculate APY (placeholder)
        tvl_usd = (pool.base_reserve + pool.quote_reserve) / 10**9 * 1.5  # Simplified
        apy = (fees_24h * 365 / tvl_usd * 100) if tvl_usd > 0 else 0
        
        return {
            "pool_id": pool_id,
            "price": pool.price,
            "base_reserve": pool.base_reserve / 10**9,
            "quote_reserve": pool.quote_reserve / 10**9,
            "tvl_usd": tvl_usd,
            "volume_24h": volume_24h,
            "fees_24h": fees_24h,
            "apy_percent": apy,
            "fee_tier": pool.fee * 100,
            "lp_token_supply": pool.lp_token_supply
        }
    
    def get_user_positions(self) -> List[LiquidityPosition]:
        """Get user's liquidity positions"""
        return list(self.positions.values())
    
    def get_total_value_locked(self) -> Dict[str, float]:
        """Calculate total value locked across all positions"""
        total_rtc = 0
        total_erg = 0
        
        for position in self.positions.values():
            total_rtc += position.base_amount
            total_erg += position.quote_amount
        
        return {
            "rtc": total_rtc / 10**9,
            "erg": total_erg / 10**9
        }


def main():
    """Example usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Spectrum Pool Manager")
    parser.add_argument("--api-key", required=True, help="Spectrum API key")
    parser.add_argument("--node-host", default="http://localhost:9053", help="Ergo node")
    parser.add_argument("--address", required=True, help="Wallet address")
    parser.add_argument("--token-id", required=True, help="RTC token ID")
    parser.add_argument("--testnet", action="store_true", help="Use testnet")
    parser.add_argument("--create-pool", action="store_true", help="Create pool")
    parser.add_argument("--initial-rtc", type=int, default=1000 * 10**9, help="Initial RTC")
    parser.add_argument("--initial-erg", type=int, default=67 * 10**9, help="Initial ERG")
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    manager = SpectrumPoolManager(
        api_key=args.api_key,
        node_host=args.node_host,
        wallet_address=args.address,
        testnet=args.testnet
    )
    
    # Check API health
    if not manager.check_api_health():
        print("❌ Spectrum API not available")
        return 1
    
    # Check if pool exists
    if manager.rtc_erg_pool_exists(args.token_id):
        print(f"\n✅ Pool exists: {manager.rtc_erg_pool.pool_id}")
        
        # Show stats
        stats = manager.get_pool_stats(manager.rtc_erg_pool.pool_id)
        print(f"   Price: {stats['price']} ERG/RTC")
        print(f"   TVL: ${stats['tvl_usd']:.2f}")
    elif args.create_pool:
        print(f"\n🏗️ Creating new pool...")
        pool_id = manager.create_rtc_erg_pool(
            rtc_token_id=args.token_id,
            initial_rtc=args.initial_rtc,
            initial_erg=args.initial_erg
        )
        print(f"\n✅ Pool created: {pool_id}")
    else:
        print(f"\n⚠️ Pool does not exist. Use --create-pool to create.")
    
    return 0


if __name__ == "__main__":
    exit(main())
