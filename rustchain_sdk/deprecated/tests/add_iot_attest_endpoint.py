#!/usr/bin/env python3
"""
Add IoT/MIPS attestation endpoint to RustChain
For low-tier devices like MikroTik routers that cannot do cryptographic signing
"""

import re

ENDPOINT_CODE = """

# ==================== IoT/MIPS Attestation ====================
# Low-tier attestation for embedded devices (MikroTik, OpenWrt, etc.)
# These devices get minimal rewards but prove network participation

IOT_ATTESTATIONS = {}  # miner_id -> last attestation data

@app.route("/api/iot-attest", methods=["POST"])
def iot_attest():
    \"\"\"
    Accept attestation from IoT/embedded devices.
    Required fields: miner_id, cpu, arch, board, serial
    Optional fields: entropy, timestamp, cpu_load, free_mem, tier
    
    IoT tier gets 0.001 RTC per attestation (vs 0.01 for full miners)
    \"\"\"
    try:
        data = request.get_json(force=True)
    except:
        return jsonify({"error": "Invalid JSON"}), 400
    
    required = ["miner_id", "cpu", "arch", "serial"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400
    
    miner_id = data["miner_id"]
    
    # Rate limit: one attestation per minute per device
    import time
    now = time.time()
    if miner_id in IOT_ATTESTATIONS:
        last = IOT_ATTESTATIONS[miner_id].get("timestamp_unix", 0)
        if now - last < 60:
            return jsonify({"error": "Rate limited - wait 1 minute", "wait_seconds": int(60 - (now - last))}), 429
    
    # Store attestation
    IOT_ATTESTATIONS[miner_id] = {
        **data,
        "timestamp_unix": now,
        "tier": data.get("tier", "iot-generic"),
        "reward_rate": 0.001  # Low tier reward
    }
    
    # Log it
    app.logger.info(f"IoT attestation from {miner_id}: {data.get('arch', 'unknown')} / {data.get('cpu', 'unknown')}")
    
    return jsonify({
        "status": "accepted",
        "miner_id": miner_id,
        "tier": IOT_ATTESTATIONS[miner_id]["tier"],
        "reward_rate": 0.001,
        "message": "IoT attestation recorded. Low-tier rewards will be calculated at epoch end."
    })

@app.route("/api/iot-miners", methods=["GET"])
def list_iot_miners():
    \"\"\"List all IoT devices that have attested\"\"\"
    return jsonify({
        "count": len(IOT_ATTESTATIONS),
        "miners": [
            {
                "miner_id": mid,
                "arch": data.get("arch"),
                "cpu": data.get("cpu"),
                "tier": data.get("tier"),
                "last_seen": data.get("timestamp_unix")
            }
            for mid, data in IOT_ATTESTATIONS.items()
        ]
    })

"""

def add_iot_endpoint(filepath):
    with open(filepath, "r") as f:
        content = f.read()
    
    if "/api/iot-attest" in content:
        print("IoT endpoint already exists!")
        return False
    
    # Insert before the if __name__ block
    if "if __name__" in content:
        content = content.replace("if __name__", ENDPOINT_CODE + "\nif __name__")
    else:
        content += ENDPOINT_CODE
    
    with open(filepath, "w") as f:
        f.write(content)
    
    print("IoT endpoint added successfully!")
    return True

if __name__ == "__main__":
    add_iot_endpoint("/root/rustchain/rustchain_v2_integrated_v2.2.1_rip200.py")
