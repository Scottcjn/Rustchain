#!/usr/bin/env python3
"""
RTC Wallet Distribution Tracker - Test Script
"""

import requests
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

MINERS_API_URL = "https://50.28.86.131/api/miners"
BALANCE_API_URL = "https://50.28.86.131/wallet/balance"
TOTAL_SUPPLY = 8300000

FOUNDER_WALLETS = {
    'founder_community': 'Community Fund',
    'founder_dev_fund': 'Development Fund',
    'founder_team_bounty': 'Team & Bounties',
    'founder_founders': 'Founders Pool'
}

def get_balance(miner_id):
    """Get balance for a specific miner"""
    try:
        response = requests.get(BALANCE_API_URL, params={'miner_id': miner_id}, verify=False, timeout=10)
        response.raise_for_status()
        data = response.json()
        return {
            'miner_id': miner_id,
            'balance_rtc': data.get('amount_rtc', 0),
            'balance_i64': data.get('amount_i64', 0)
        }
    except Exception as e:
        print(f"⚠️  Error fetching balance for {miner_id}: {e}")
        return {
            'miner_id': miner_id,
            'balance_rtc': 0,
            'balance_i64': 0
        }

def format_number(num):
    """Format large numbers with K/M suffixes"""
    if num >= 1000000:
        return f"{num / 1000000:.2f}M"
    elif num >= 1000:
        return f"{num:,}"
    return str(num)

def calculate_gini(balances):
    """Calculate Gini coefficient for income distribution"""
    if not balances:
        return 0

    balances = sorted(balances)
    n = len(balances)
    sum_balances = sum(balances)

    if sum_balances == 0:
        return 0

    numerator = sum((i + 1) * bal for i, bal in enumerate(balances))
    gini = (2 * numerator) / (n * sum_balances) - (n + 1) / n
    return max(0, gini)

def main():
    print("🪙 RTC Wallet Distribution Tracker - Test\n")
    print("=" * 80)

    # Fetch miners from API
    print("\n⏳ Fetching miner list from API...")
    try:
        response = requests.get(MINERS_API_URL, verify=False, timeout=30)
        response.raise_for_status()
        miners = response.json()
        print(f"✅ Found {len(miners)} miners!")
    except Exception as e:
        print(f"❌ Failed to fetch miners: {e}")
        return

    # Fetch balances for all miners (parallel requests)
    print("\n⏳ Fetching wallet balances (this may take a moment)...")
    wallets = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(get_balance, miner['miner']): miner['miner']
            for miner in miners
        }

        for future in as_completed(futures):
            result = future.result()
            if result['balance_rtc'] > 0:
                wallets.append(result)

    print(f"✅ Found {len(wallets)} wallets with non-zero balance!")

    if not wallets:
        print("\n❌ No wallets with balance found!")
        return

    # Sort by balance (descending)
    wallets.sort(key=lambda x: x['balance_rtc'], reverse=True)

    # Calculate statistics
    total_wallets = len(wallets)
    in_circulation = sum(w['balance_rtc'] for w in wallets)
    percent_minted = (in_circulation / TOTAL_SUPPLY) * 100

    print(f"\n📊 Statistics:")
    print(f"   Total wallets: {total_wallets}")
    print(f"   Total supply: {format_number(TOTAL_SUPPLY)} RTC")
    print(f"   In circulation: {format_number(in_circulation)} RTC")
    print(f"   % minted: {percent_minted:.2f}%")

    # Calculate Gini coefficient
    balances = [w['balance_rtc'] for w in wallets]
    gini = calculate_gini(balances)
    print(f"   Gini coefficient: {gini:.4f}")

    # Identify whales and founders
    whale_threshold = TOTAL_SUPPLY * 0.01  # 1% of supply
    whales = []
    founder_balance = 0
    founder_count = 0

    print(f"\n🐋 Whale Wallets (>1% supply = {format_number(whale_threshold)} RTC):")
    for w in wallets:
        if w['balance_rtc'] >= whale_threshold:
            whales.append(w)
            percent = (w['balance_rtc'] / TOTAL_SUPPLY) * 100
            label = FOUNDER_WALLETS.get(w['miner_id'], '')
            print(f"   - {w['miner_id']}: {format_number(w['balance_rtc'])} ({percent:.2f}%){' [' + label + ']' if label else ''}")

        if w['miner_id'] in FOUNDER_WALLETS:
            founder_balance += w['balance_rtc']
            founder_count += 1

    if not whales:
        print("   No whale wallets found!")

    print(f"\n💎 Founder Wallets:")
    print(f"   Count: {founder_count}")
    print(f"   Total balance: {format_number(founder_balance)} RTC ({(founder_balance / TOTAL_SUPPLY * 100):.2f}%)")

    # Top 20 holders
    print(f"\n🏆 Top 20 Holders:")
    print("-" * 80)
    print(f"{'Rank':<6} {'Wallet ID':<32} {'Balance':<16} {'% Supply':<12} {'Type'}")
    print("-" * 80)

    for i, w in enumerate(wallets[:20], 1):
        percent = (w['balance_rtc'] / TOTAL_SUPPLY) * 100
        is_whale = w['balance_rtc'] >= whale_threshold
        founder_label = FOUNDER_WALLETS.get(w['miner_id'], '')

        type_str = ''
        if founder_label:
            type_str = f'[Founder: {founder_label}]'
        elif is_whale:
            type_str = '[WHALE]'

        print(f"{i:<6} {w['miner_id'][:32]:<32} {format_number(w['balance_rtc']):<16} {percent:<12.4f} {type_str}")

    print("\n" + "=" * 80)
    print("✅ Test completed successfully!")
    print(f"📁 HTML file: /home/zhanglinqian/.openclaw/workspace/public_html/rtc-wallet-tracker.html")

if __name__ == "__main__":
    main()
