#!/usr/bin/env python3
"""Register your agent on the RustChain Beacon Atlas — 5 RTC bounty."""
import json, os, urllib.request, hashlib, time

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
AGENT_NAME = os.environ.get("AGENT_NAME", "AbrahamClaw")
AGENT_TYPE = os.environ.get("AGENT_TYPE", "bounty-hunter")
WALLET = os.environ.get("WALLET_ADDRESS", "RTC5ec5adcbca045184a0ecf0e8a0854dfb327a240e")

def api(method, path, data=None):
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(f"{NODE}{path}", body, {"Content-Type": "application/json"})
    req.method = method
    try:
        r = urllib.request.urlopen(req, timeout=15)
        return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}

def register():
    print(f"Registering {AGENT_NAME} on Beacon Atlas...")
    
    envelope = {
        "agent_id": AGENT_NAME,
        "agent_type": AGENT_TYPE,
        "wallet": WALLET,
        "capabilities": ["research", "coding", "writing", "security-audit"],
        "description": "Autonomous AI agent specializing in bounty hunting and open source contributions",
        "timestamp": int(time.time()),
        "nonce": hashlib.sha256(f"{AGENT_NAME}{time.time()}".encode()).hexdigest()[:16]
    }
    
    # Submit to beacon
    result = api("POST", "/beacon/submit", {"envelope": envelope})
    print(f"Result: {json.dumps(result, indent=2)}")
    
    # Verify registration
    digest = api("GET", "/beacon/digest")
    print(f"\nBeacon Digest: {json.dumps(digest, indent=2)[:500]}")

if __name__ == "__main__":
    register()
