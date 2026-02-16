#!/usr/bin/env python3
"""
Test script for wRTC Price Ticker Bot

This script tests price fetching without requiring a Telegram bot token.
"""

from wrtc_price_bot import PriceFetcher, format_price_message


def test_price_fetch():
    """Test price fetching from APIs"""
    print("=" * 60)
    print("wRTC Price Bot - Price Fetch Test")
    print("=" * 60)
    print()

    # Initialize fetcher
    fetcher = PriceFetcher()

    print("📊 Testing DexScreener API...")
    dexscreener_data = fetcher.fetch_dexscreener_price()

    if dexscreener_data:
        print("✅ DexScreener API working!")
        print(f"   Price (USD): ${dexscreener_data.get('price_usd', 0):.6f}")
        print(f"   Price (SOL): {dexscreener_data.get('price_sol', 0):.8f}")
        print(f"   24h Change: {dexscreener_data.get('change_24h', 0):+.2f}%")
        print(f"   Liquidity: ${dexscreener_data.get('liquidity', 0):,.0f}")
    else:
        print("❌ DexScreener API failed")

    print()
    print("🪙 Testing Jupiter API...")
    jupiter_data = fetcher.fetch_jupiter_price()

    if jupiter_data:
        print("✅ Jupiter API working!")
        print(f"   Price: ${jupiter_data.get('price', 0):.6f}")
        print(f"   ID: {jupiter_data.get('id', '')}")
    else:
        print("❌ Jupiter API failed")

    print()
    print("🎯 Testing integrated price fetch...")

    # Get best available price
    price_data = fetcher.get_price()

    if price_data:
        print("✅ Price fetched successfully!")
        print()
        print("Price Data:")
        print(f"   USD: ${price_data.get('price_usd', 0):.6f}")
        print(f"   SOL: {price_data.get('price_sol', 0):.8f}")
        print(f"   24h Change: {price_data.get('change_24h', 0):+.2f}%")
        print(f"   Liquidity: ${price_data.get('liquidity', 0):,.0f}")
        print()
        print("Formatted Message:")
        print("-" * 60)
        print(format_price_message(price_data))
        print("-" * 60)
    else:
        print("❌ All APIs failed to fetch price")

    print()
    print("=" * 60)
    print("Test completed!")
    print("=" * 60)

    return price_data is not None


if __name__ == "__main__":
    import sys
    success = test_price_fetch()
    sys.exit(0 if success else 1)
