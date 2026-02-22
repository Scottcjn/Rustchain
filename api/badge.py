import os
import time
from flask import Flask, jsonify, request

app = Flask(__name__)

# Mock node state — in production, this would be imported from node.state or similar
# For RIP-200 nodes, we check the last attestation / epoch participation.
def get_node_mining_status():
    """
    Determines if the node is actively mining based on local state.
    In a real RIP-200 node, we'd check:
    1. Local miner process status
    2. Last successful attestation timestamp
    """
    try:
        # Check if we have a local heartbeat file or DB entry
        # For this implementation, we look for 'last_attestation.timestamp'
        # which is updated by the miner worker.
        ts_file = "last_attestation.timestamp"
        if os.path.exists(ts_file):
            with open(ts_file, "r") as f:
                last_ts = float(f.read().strip())
                # Active if attestation within last 20 minutes
                if (time.time() - last_ts) < 1200:
                    return "Active"
        
        # Fallback: check if miner process is in env (for containerized runs)
        if os.environ.get("MINER_ACTIVE") == "true":
            return "Active"
            
    except Exception:
        pass
        
    return "Inactive"

@app.route("/api/badge")
def mining_badge_json():
    """
    Returns a shields.io-compatible JSON endpoint.
    Usage: https://img.shields.io/endpoint?url=https://your-node.com/api/badge
    """
    status = get_node_mining_status()
    color = "brightgreen" if status == "Active" else "inactive"
    
    return jsonify({
        "schemaVersion": 1,
        "label": "RustChain",
        "message": status,
        "color": color
    })

if __name__ == "__main__":
    # Internal port, mapped to 8082 or similar via proxy
    app.run(port=8082)
