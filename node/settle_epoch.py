#!/usr/bin/env python3
import requests
import time

NODE_URL = "http://localhost:8099"

def trigger_settlement():
    try:
        resp = requests.get(f"{NODE_URL}/epoch", timeout=10)
        epoch_info = resp.json()
        current_epoch = epoch_info.get("epoch", 0)
        prev_epoch = current_epoch - 1
        
        resp = requests.post(f"{NODE_URL}/rewards/settle", 
                           json={"epoch": prev_epoch}, 
                           timeout=60)
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] Settlement for epoch {prev_epoch}: {resp.status_code}")
        if resp.status_code == 200:
            return resp.json()
        return resp.text[:200]
    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    result = trigger_settlement()
    print(result)
