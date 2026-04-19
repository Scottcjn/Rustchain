import time
import requests
import os

def get_node_stats():
    # Attempt to query the local Rustchain RPC
    try:
        response = requests.post("http://localhost:3000/rpc", 
                               json={"method": "get_status", "params": []}, 
                               timeout=2)
        return response.json()
    except:
        return None

def print_dashboard():
    os.system('clear')
    print("="*40)
    print("   RUSTCHAIN NODE HEALTH DASHBOARD   ")
    print("="*40)
    stats = get_node_stats()
    
    if stats:
        print(f"Status:    ONLINE")
        print(f"Peers:     {stats.get('peers', '0')}")
        print(f"Block:     {stats.get('height', 'Unknown')}")
        print(f"Hashrate:  {stats.get('hashrate', '0')} H/s")
    else:
        print(f"Status:    OFFLINE (Node not responding on port 3000)")
    
    print("-" * 40)
    print("Press Ctrl+C to exit")

if __name__ == "__main__":
    while True:
        print_dashboard()
        time.sleep(5)
