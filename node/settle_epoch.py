#!/usr/bin/env python3
"""RustChain Epoch Settlement Trigger Script"""
from __future__ import annotations

import requests
import time
from typing import Optional, Union, Dict, Any

NODE_URL: str = "http://localhost:8099"


def trigger_settlement() -> Optional[Union[Dict[str, Any], str]]:
    """
    Trigger epoch settlement for the previous epoch.
    
    Returns:
        dict|str|None: Settlement result JSON, response text, or None on error.
    """
    try:
        resp = requests.get(f"{NODE_URL}/epoch", timeout=10)
        epoch_info = resp.json()
        current_epoch: int = epoch_info.get("epoch", 0)
        prev_epoch: int = current_epoch - 1
        
        resp = requests.post(f"{NODE_URL}/rewards/settle", 
                           json={"epoch": prev_epoch}, 
                           timeout=60)
        ts: str = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] Settlement for epoch {prev_epoch}: {resp.status_code}")
        if resp.status_code == 200:
            return resp.json()
        return resp.text[:200]
    except Exception as e:
        print(f"Error: {e}")
        return None


if __name__ == "__main__":
    result: Optional[Union[Dict[str, Any], str]] = trigger_settlement()
    print(result)
