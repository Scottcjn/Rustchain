import time
import requests
import argparse
from pypresence import Presence
from datetime import datetime

# Default Client ID for RustChain RPC (Ideally the maintainer creates an official App)
# Users can override this
DEFAULT_CLIENT_ID = '123456789012345678' 

def get_miner_stats(node_url, wallet):
    """Fetch miner stats from the node API"""
    try:
        # Check balance/earnings
        # Note: This is an estimation based on available API endpoints
        resp = requests.get(f"{node_url}/wallet/balance?miner_id={wallet}", verify=False, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return data
    except Exception as e:
        # print(f"API Error: {e}")
        pass
    return None

def main():
    parser = argparse.ArgumentParser(description="RustChain Discord Rich Presence")
    parser.add_argument("--wallet", required=True, help="Your Miner Wallet Name")
    parser.add_argument("--node", default="https://50.28.86.131", help="Node URL")
    parser.add_argument("--client-id", default=DEFAULT_CLIENT_ID, help="Discord App Client ID")
    parser.add_argument("--hardware", default="Vintage CPU", help="Your Hardware Type (e.g. G4, POWER8)")
    
    args = parser.parse_args()

    print(f"🎮 Starting Discord RPC for wallet: {args.wallet}")
    print(f"🔌 Hardware: {args.hardware}")

    try:
        RPC = Presence(args.client_id)
        RPC.connect()
        print("✅ Connected to Discord!")
    except Exception as e:
        print(f"❌ Could not connect to Discord: {e}")
        print("Make sure the Discord Desktop App is running.")
        return

    start_time = int(time.time())

    while True:
        try:
            stats = get_miner_stats(args.node, args.wallet)
            
            # Default values if API fails
            balance = "0.00"
            if stats and 'balance' in stats:
                balance = f"{stats['balance']:.2f}"

            # Update Presence
            RPC.update(
                state=f"💰 Earned: {balance} RTC",
                details=f"🔨 Mining on {args.hardware}",
                start=start_time,
                large_image="rustchain_logo", # Requires asset uploaded to Discord App
                large_text="RustChain: Proof of Antiquity",
                small_image="mining_active",
                small_text="Mining Active",
                buttons=[
                    {"label": "Join RustChain", "url": "https://rustchain.org"},
                    {"label": "View Explorer", "url": "https://rustchain.org/explorer"}
                ]
            )
            
            # Update every 15s (Discord rate limit)
            time.sleep(15)

        except KeyboardInterrupt:
            print("Stopping RPC...")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(15)

if __name__ == "__main__":
    main()
