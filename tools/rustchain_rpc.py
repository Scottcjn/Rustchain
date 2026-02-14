import time
import requests
import argparse
from pypresence import Presence
from datetime import datetime

# RustChain Application ID (Placeholder - Maintainer needs to register this on Discord Dev Portal)
CLIENT_ID = "123456789012345678" 

def get_miner_stats(wallet_address, node_url="https://50.28.86.131"):
    """Fetch miner stats from the node API."""
    try:
        # Get miner info (mocking the endpoint structure based on README)
        response = requests.get(f"{node_url}/api/miners", verify=False)
        if response.status_code == 200:
            miners = response.json()
            # Find our miner
            for m in miners:
                if m.get('wallet') == wallet_address:
                    return m
        return None
    except Exception as e:
        print(f"Error fetching stats: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="RustChain Discord Rich Presence")
    parser.add_argument("--wallet", required=True, help="Your RustChain wallet address")
    parser.add_argument("--node", default="https://50.28.86.131", help="Node URL")
    args = parser.parse_args()

    print(f"Starting Discord RPC for wallet: {args.wallet}")
    
    try:
        RPC = Presence(CLIENT_ID)
        RPC.connect()
        print("Connected to Discord!")
    except Exception as e:
        print(f"Failed to connect to Discord: {e}")
        print("Make sure Discord is running on this machine.")
        return

    start_time = time.time()

    while True:
        stats = get_miner_stats(args.wallet, args.node)
        
        if stats:
            hardware = stats.get('hardware', 'Unknown Hardware')
            epoch_score = stats.get('score', 0)
            
            details = f"Mining on {hardware}"
            state = f"Score: {epoch_score} | Vintage Power ⚡"
            
            RPC.update(
                details=details,
                state=state,
                large_image="rustchain_logo", # Assumes 'rustchain_logo' asset exists in Discord App
                large_text="RustChain Proof-of-Antiquity",
                start=start_time,
                buttons=[{"label": "Start Mining", "url": "https://rustchain.org"}]
            )
            print(f"Updated status: {details} - {state}")
        else:
            RPC.update(
                details="Idle / Connecting...",
                state="Waiting for miner stats...",
                large_image="rustchain_logo",
                start=start_time
            )
            print("Miner not found or API error.")

        time.sleep(15)

if __name__ == "__main__":
    main()
