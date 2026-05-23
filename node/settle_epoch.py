#!/usr/bin/env python3
import requests
import time

NODE_URL = "http://localhost:8099"

def _previous_settleable_epoch(epoch_info):
    if not isinstance(epoch_info, dict):
        raise ValueError("/epoch response must be a JSON object")

    current_epoch = epoch_info.get("epoch")
    if not isinstance(current_epoch, int) or isinstance(current_epoch, bool):
        raise ValueError("/epoch response field 'epoch' must be an integer")
    if current_epoch <= 0:
        raise ValueError("/epoch response field 'epoch' must be greater than zero")

    return current_epoch - 1

def trigger_settlement():
    try:
        resp = requests.get(f"{NODE_URL}/epoch", timeout=10)
        epoch_info = resp.json()
        prev_epoch = _previous_settleable_epoch(epoch_info)
        
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
