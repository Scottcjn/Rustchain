#!/usr/bin/env python3
"""
RustChain Weekly Miner Leaderboard Bot for Discord

Posts weekly/daily mining leaderboards to Discord.
- Top 10 miners by RTC balance
- Top earners this epoch
- Architecture distribution
- Network stats

Requirements:
    pip install requests discord-webhook

Usage:
    python leaderboard_bot.py --webhook WEBHOOK_URL --wallet WALLET_ID
"""

import os
import sys
import argparse
import time
import requests
from datetime import datetime, timedelta
from discord_webhook import DiscordWebhook, DiscordEmbed

# Configuration
NODE_URL = os.environ.get("NODE_URL", "https://50.28.86.131")
UPDATE_INTERVAL = 86400  # 24 hours


def get_miners():
    """Fetch all miners from the network."""
    try:
        resp = requests.get(f"{NODE_URL}/api/miners", timeout=30)
        if resp.status_code == 200:
            return resp.json().get("miners", [])
        return []
    except Exception as e:
        print(f"Error fetching miners: {e}")
        return []


def get_balance(wallet: str) -> dict:
    """Fetch wallet balance."""
    try:
        resp = requests.get(
            f"{NODE_URL}/wallet/balance",
            params={"miner_id": wallet},
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json()
        return {}
    except Exception:
        return {}


def get_epoch():
    """Fetch current epoch info."""
    try:
        resp = requests.get(f"{NODE_URL}/epoch", timeout=10)
        if resp.status_code == 200:
            return resp.json()
        return {}
    except Exception:
        return {}


def format_leaderboard(miners: list) -> str:
    """Format leaderboard as Discord markdown."""
    if not miners:
        return "No miners data available."
    
    # Sort by balance
    sorted_miners = sorted(miners, key=lambda x: x.get("balance", 0), reverse=True)
    
    # Build leaderboard
    lines = ["**🏆 Top Miners by Balance**\n"]
    lines.append("```
Rank | Wallet                    | Balance   | Hardware")
    lines.append("-" * 60)
    
    for i, m in enumerate(sorted_miners[:10], 1):
        wallet = m.get("miner_id", "unknown")[:22]
        balance = m.get("balance", 0)
        hardware = m.get("hardware", "Unknown")[:12]
        lines.append(f"{i:>4} | {wallet:<24} | {balance:>9.2f} | {hardware}")
    
    lines.append("```")
    
    # Architecture breakdown
    arch_counts = {}
    for m in miners:
        hw = m.get("hardware", "Unknown")
        arch = "Unknown"
        if "G4" in hw or "PowerPC" in hw:
            arch = "PowerPC G4"
        elif "G5" in hw:
            arch = "PowerPC G5"
        elif "M1" in hw or "M2" in hw or "M3" in hw or "M4" in hw:
            arch = "Apple Silicon"
        elif "POWER8" in hw:
            arch = "IBM POWER8"
        elif "Intel" in hw or "Core" in hw:
            arch = "Modern x86"
        arch_counts[arch] = arch_counts.get(arch, 0) + 1
    
    lines.append("\n**🖥️ Architecture Distribution**\n")
    lines.append("```")
    for arch, count in sorted(arch_counts.items(), key=lambda x: x[1], reverse=True):
        pct = count / len(miners) * 100
        lines.append(f"{arch}: {count} ({pct:.1f}%)")
    lines.append("```")
    
    # Network stats
    total_balance = sum(m.get("balance", 0) for m in miners)
    lines.append(f"\n**📊 Network Stats**")
    lines.append(f"- Total Miners: {len(miners)}")
    lines.append(f"- Total RTC: {total_balance:.2f}")
    
    epoch = get_epoch()
    if epoch:
        lines.append(f"- Current Epoch: {epoch.get('epoch', 'N/A')}")
    
    return "\n".join(lines)


def post_to_discord(webhook_url: str, message: str):
    """Post leaderboard to Discord webhook."""
    try:
        webhook = DiscordWebhook(url=webhook_url, content=message)
        response = webhook.execute()
        return True
    except Exception as e:
        print(f"Error posting to Discord: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="RustChain Leaderboard Bot")
    parser.add_argument(
        "--webhook",
        type=str,
        required=True,
        help="Discord webhook URL"
    )
    parser.add_argument(
        "--wallet",
        type=str,
        help="Optional: wallet for notifications"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=UPDATE_INTERVAL,
        help="Update interval in seconds"
    )
    args = parser.parse_args()
    
    print("🏆 RustChain Leaderboard Bot starting...")
    
    # Initial post
    print("Fetching miner data...")
    miners = get_miners()
    leaderboard = format_leaderboard(miners)
    
    epoch_info = get_epoch()
    title = f"🏆 RustChain Leaderboard - Epoch {epoch_info.get('epoch', '?')}"
    
    # Post with embed
    webhook = DiscordWebhook(url=args.webhook)
    embed = DiscordEmbed(
        title=title,
        description=leaderboard,
        color="00ff00"
    )
    embed.set_footer(text=f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    webhook.add_embed(embed)
    
    try:
        webhook.execute()
        print("✅ Leaderboard posted!")
    except Exception as e:
        print(f"⚠️  Posting failed: {e}")
    
    print(f"Done! (Run with --help to see options)")


if __name__ == "__main__":
    main()
