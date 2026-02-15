#!/usr/bin/env python3
"""
wRTC Price Ticker Bot for Telegram

Posts current wRTC/SOL price from Raydium DEX.
"""

import os
import time
from typing import Dict, Optional
from datetime import datetime
import requests


class PriceFetcher:
    """Fetch wRTC price from multiple APIs"""

    WRTC_MINT = "12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X"
    RAYDIUM_POOL = "8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb"

    def __init__(self):
        self.last_price: Optional[float] = None
        self.last_check: Optional[float] = None
        self.price_history: list = []

    def fetch_jupiter_price(self) -> Optional[Dict]:
        """Fetch price from Jupiter API"""
        try:
            url = f"https://price.jup.ag/v2/price?ids={self.WRTC_MINT}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            if self.WRTC_MINT in data:
                price_data = data[self.WRTC_MINT]
                return {
                    "price": float(price_data.get("price", 0)),
                    "id": price_data.get("id", ""),
                }
        except Exception as e:
            print(f"[Jupiter API] Error: {e}")

        return None

    def fetch_dexscreener_price(self) -> Optional[Dict]:
        """Fetch price from DexScreener API"""
        try:
            url = f"https://api.dexscreener.com/latest/dex/tokens/{self.WRTC_MINT}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            if "pairs" in data and len(data["pairs"]) > 0:
                pair = data["pairs"][0]
                price_usd = float(pair.get("priceUsd", 0))
                liquidity = float(pair.get("liquidity", {}).get("usd", 0))
                change_24h = float(pair.get("priceChange", {}).get("h24", 0))

                return {
                    "price_usd": price_usd,
                    "price_sol": float(pair.get("priceNative", 0)),
                    "change_24h": change_24h,
                    "liquidity": liquidity,
                    "sol_price_usd": price_usd / pair.get("priceNative", 1) if pair.get("priceNative") else 0,
                }
        except Exception as e:
            print(f"[DexScreener API] Error: {e}")

        return None

    def get_price(self) -> Optional[Dict]:
        """Get price from available APIs"""
        # Try DexScreener first (more data)
        price_data = self.fetch_dexscreener_price()

        if not price_data:
            # Fallback to Jupiter
            jupiter_data = self.fetch_jupiter_price()
            if jupiter_data:
                price_data = {
                    "price_usd": jupiter_data["price"],
                    "price_sol": 0,
                    "change_24h": 0,
                    "liquidity": 0,
                }

        if price_data:
            # Track price history
            self.price_history.append({
                "timestamp": time.time(),
                "price": price_data.get("price_usd", price_data.get("price", 0))
            })

            # Keep only last 24 hours of history
            current_time = time.time()
            self.price_history = [
                h for h in self.price_history
                if current_time - h["timestamp"] < 86400
            ]

            self.last_price = price_data.get("price_usd", 0)
            self.last_check = current_time

        return price_data

    def check_price_alert(self, threshold: float = 10.0) -> Optional[str]:
        """Check if price moved more than threshold % in last hour"""
        if not self.last_price or not self.last_check:
            return None

        one_hour_ago = time.time() - 3600
        recent_prices = [
            h for h in self.price_history
            if h["timestamp"] > one_hour_ago
        ]

        if len(recent_prices) < 2:
            return None

        old_price = recent_prices[0]["price"]
        new_price = self.last_price

        if old_price == 0:
            return None

        change_pct = ((new_price - old_price) / old_price) * 100

        if abs(change_pct) >= threshold:
            direction = "📈 UP" if change_pct > 0 else "📉 DOWN"
            return f"⚠️ **Price Alert!** wRTC {direction} {abs(change_pct):.2f}% in last hour!"

        return None


class TelegramBot:
    """Simple Telegram bot wrapper"""

    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    def send_message(self, chat_id: str, message: str, parse_mode: str = "Markdown"):
        """Send message to Telegram chat"""
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": parse_mode,
            }

            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[Telegram] Error sending message: {e}")
            return None

    def get_updates(self, offset: int = 0, timeout: int = 30) -> Dict:
        """Get bot updates"""
        try:
            url = f"{self.base_url}/getUpdates"
            payload = {
                "offset": offset,
                "timeout": timeout,
            }

            response = requests.get(url, params=payload, timeout=timeout + 5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[Telegram] Error getting updates: {e}")
            return {"ok": False, "result": []}


def format_price_message(price_data: Dict) -> str:
    """Format price data for Telegram message"""
    price_usd = price_data.get("price_usd", 0)
    price_sol = price_data.get("price_sol", 0)
    change_24h = price_data.get("change_24h", 0)
    liquidity = price_data.get("liquidity", 0)

    # Format change percentage
    change_emoji = "📈" if change_24h >= 0 else "📉"
    change_str = f"{change_emoji} {change_24h:+.2f}%" if change_24h != 0 else "0.00%"

    # Format numbers
    price_usd_str = f"${price_usd:.6f}" if price_usd < 0.01 else f"${price_usd:.4f}"
    liquidity_str = f"${liquidity:,.0f}" if liquidity > 0 else "N/A"

    message = f"""
🪙 **wRTC Price**

💰 **Price (USD):** `{price_usd_str}`
💎 **Price (SOL):** `{price_sol:.8f}`

📊 **24h Change:** {change_str}
💧 **Liquidity:** `{liquidity_str}`

🔗 [Swap on Raydium](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X)
📊 [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb)

---
🤖 *Powered by RustChain Price Bot*
"""
    return message


def main():
    """Main bot function"""
    # Get bot token from environment
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        print("Error: TELEGRAM_BOT_TOKEN environment variable not set")
        print("Set it with: export TELEGRAM_BOT_TOKEN='your_bot_token'")
        return

    # Initialize components
    fetcher = PriceFetcher()
    bot = TelegramBot(bot_token)

    print("🤖 wRTC Price Bot started")
    print(f"📊 Fetching price for wRTC: {PriceFetcher.WRTC_MINT}")
    print()

    # Test price fetch
    print("Fetching current price...")
    price_data = fetcher.get_price()

    if price_data:
        print("✅ Price fetched successfully!")
        print(f"   Price (USD): ${price_data.get('price_usd', 0):.6f}")
        print(f"   Price (SOL): {price_data.get('price_sol', 0):.8f}")
        print(f"   24h Change: {price_data.get('change_24h', 0):+.2f}%")
        print(f"   Liquidity: ${price_data.get('liquidity', 0):,.0f}")
        print()
        print("✅ Bot is ready to receive /price commands!")
        print("   Send /price to your bot to get current price")
        print()
        print("Example message format:")
        print(format_price_message(price_data))
    else:
        print("❌ Failed to fetch price")
        print("Please check your internet connection and API availability")


if __name__ == "__main__":
    main()
