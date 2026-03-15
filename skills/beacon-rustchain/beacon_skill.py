"""RustChain Beacon Skill for OpenClaw agents."""
import json, os, urllib.request, time, hashlib

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")

def api(path, data=None):
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(f"{NODE}{path}", body, {"Content-Type": "application/json"})
    if data: req.method = "POST"
    try:
        return json.loads(urllib.request.urlopen(req, timeout=10).read())
    except:
        return {}

def register(agent_id, agent_type="openclaw", capabilities=None):
    envelope = {
        "agent_id": agent_id,
        "agent_type": agent_type,
        "capabilities": capabilities or ["general"],
        "timestamp": int(time.time()),
        "nonce": hashlib.sha256(f"{agent_id}{time.time()}".encode()).hexdigest()[:16]
    }
    return api("/beacon/submit", {"envelope": envelope})

def digest():
    return api("/beacon/digest")

def agents():
    return api("/beacon/envelopes")

def status():
    return api("/health")
