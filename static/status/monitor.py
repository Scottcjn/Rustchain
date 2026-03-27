import requests
import time
import json
import os
from datetime import datetime

# Node configuration
NODES = [
    {"name": "Node 1", "url": "https://50.28.86.131/health", "location": "LiquidWeb US"},
    {"name": "Node 2", "url": "https://50.28.86.153/health", "location": "LiquidWeb US"},
    {"name": "Node 3", "url": "http://76.8.228.245:8099/health", "location": "Ryan's Proxmox"},
    {"name": "Node 4", "url": "http://38.76.217.189:8099/health", "location": "Hong Kong"},
]

DATA_FILE = "node_status.json"

def check_nodes():
    results = []
    for node in NODES:
        start_time = time.time()
        try:
            # Use pinned cert if available, else system CA bundle
            _cert = os.path.expanduser("~/.rustchain/node_cert.pem")
            _verify = _cert if os.path.exists(_cert) else True
            resp = requests.get(node["url"], timeout=10, verify=_verify)
            latency = (time.time() - start_time) * 1000
            
            if resp.status_code == 200:
                data = resp.json()
                results.append({
                    "name": node["name"],
                    "url": node["url"],
                    "location": node["location"],
                    "status": "up",
                    "latency_ms": round(latency, 2),
                    "version": data.get("version", "unknown"),
                    "miners": data.get("active_miners", data.get("miners", 0)),
                    "epoch": data.get("current_epoch", data.get("epoch", 0)),
                    "timestamp": datetime.now().isoformat()
                })
            else:
                results.append({
                    "name": node["name"],
                    "url": node["url"],
                    "location": node["location"],
                    "status": "down",
                    "error": f"HTTP {resp.status_code}",
                    "timestamp": datetime.now().isoformat()
                })
        except Exception as e:
            results.append({
                "name": node["name"],
                "url": node["url"],
                "location": node["location"],
                "status": "down",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
    
    # Save to history file for dashboard to read
    history = []
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                history = json.load(f)
        except: pass
    
    history.append({"time": datetime.now().isoformat(), "nodes": results})
    # Keep last 1440 entries (24 hours at 1/min)
    history = history[-1440:]
    
    with open(DATA_FILE, 'w') as f:
        json.dump(history, f, indent=2)
    
    return results

if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    print(f"Checking {len(NODES)} nodes...")
    res = check_nodes()
    for r in res:
        print(f"[{r['status'].upper()}] {r['name']}: {r.get('latency_ms', 'N/A')}ms")
