#!/usr/bin/env python3
"""
Setup script for RustChain Telegram Bot
"""

import os
import sys
import subprocess


def main():
    print("🦀 RustChain Telegram Bot — Setup")
    print("=" * 40)

    # Install deps
    print("\n📦 Installing dependencies...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
        check=True,
    )
    print("✅ Dependencies installed.")

    # Check BOT_TOKEN
    token = os.getenv("BOT_TOKEN")
    if not token:
        print("\n⚠️  BOT_TOKEN not set in environment.")
        print("   Get one from @BotFather on Telegram, then run:")
        print("   export BOT_TOKEN='your_token_here'")
        print("   python3 bot.py")
    else:
        print("\n✅ BOT_TOKEN is set.")

    print("\n🚀 To run the bot:")
    print("   python3 bot.py")

    print("\n📋 Configuration:")
    print(f"   RUSTCHAIN_API: {os.getenv('RUSTCHAIN_API', 'http://50.28.86.131')}")
    print(f"   BOT_TOKEN: {'set ✓' if token else 'not set ✗'}")


if __name__ == "__main__":
    main()
