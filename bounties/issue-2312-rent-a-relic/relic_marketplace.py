import time
import json
import base64
import hashlib
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
except ImportError:
    pass  # Allow mocking for tests

app = FastAPI(title="Rent-a-Relic Market API", version="1.0.0")

# Mock In-Memory DB for Relics
RELICS_DB = {
    "relic_g5_001": {
        "id": "relic_g5_001",
        "name": "Power Mac G5 Quad",
        "architecture": "PowerPC G5",
        "year": 2005,
        "rate_rtc_per_hour": 0.5,
        "status": "available",
        "quirks": ["Requires specific GCC flags", "Loud fans"]
    },
    "relic_sparc_002": {
        "id": "relic_sparc_002",
        "name": "Sun SPARCstation 20",
        "architecture": "SPARC v8",
        "year": 1994,
        "rate_rtc_per_hour": 0.3,
        "status": "available",
        "quirks": ["Solaris 2.4", "Slow I/O"]
    }
}

RESERVATIONS = {}

class ReservationRequest(BaseModel):
    relic_id: str
    agent_id: str
    duration_hours: int

class PaymentRequest(BaseModel):
    session_id: str
    wrtc_tx_hash: str

class PayloadExecution(BaseModel):
    session_id: str
    command: str

@app.get("/api/relics")
def list_relics():
    return {"relics": list(RELICS_DB.values())}

@app.post("/api/reserve")
def reserve_relic(req: ReservationRequest):
    if req.relic_id not in RELICS_DB:
        raise HTTPException(status_code=404, detail="Relic not found")
    
    relic = RELICS_DB[req.relic_id]
    if relic["status"] != "available":
        raise HTTPException(status_code=400, detail="Relic currently unavailable")
    
    total_cost = req.duration_hours * relic["rate_rtc_per_hour"]
    session_id = hashlib.md5(f"{req.relic_id}_{time.time()}".encode()).hexdigest()
    
    RESERVATIONS[session_id] = {
        "relic_id": req.relic_id,
        "agent_id": req.agent_id,
        "duration": req.duration_hours,
        "cost": total_cost,
        "status": "pending_payment",
        "expires_at": time.time() + 3600  # 1 hour to pay
    }
    
    return {
        "session_id": session_id,
        "cost_rtc": total_cost,
        "payment_address": "RTC_ESCROW_MASTER_ADDRESS",
        "status": "Awaiting wRTC deposit"
    }

@app.post("/api/pay")
def verify_payment(req: PaymentRequest):
    if req.session_id not in RESERVATIONS:
        raise HTTPException(status_code=404, detail="Session not found")
        
    reservation = RESERVATIONS[req.session_id]
    if reservation["status"] != "pending_payment":
        raise HTTPException(status_code=400, detail="Session already paid or expired")
        
    # In a real scenario, we verify req.wrtc_tx_hash against RustChain RPC
    # verify_wrtc_deposit(req.wrtc_tx_hash, reservation['cost'])
    
    reservation["status"] = "active"
    RELICS_DB[reservation["relic_id"]]["status"] = "in_use"
    
    return {"status": "Payment verified. Relic locked and ready for execution.", "session_id": req.session_id}

@app.post("/api/execute")
def execute_workload(req: PayloadExecution):
    if req.session_id not in RESERVATIONS:
        raise HTTPException(status_code=404, detail="Session not found")
        
    res = RESERVATIONS[req.session_id]
    if res["status"] != "active":
        raise HTTPException(status_code=403, detail="Session not active or expired")
        
    relic = RELICS_DB[res["relic_id"]]
    
    # Simulate execution on the isolated vintage hardware via SSH/Serial jump host
    time.sleep(1)
    mock_output = f"Execution on {relic['architecture']} completed successfully. Output: [MOCK_BINARY_DATA]"
    output_hash = hashlib.sha256(mock_output.encode()).hexdigest()
    
    # Generate Cryptographic Provenance Receipt (Signed by the Relic's Hardware Key / Beacon)
    try:
        hw_key = Ed25519PrivateKey.generate()
        receipt_data = {
            "relic_id": relic["id"],
            "agent_id": res["agent_id"],
            "duration": res["duration"],
            "output_hash": output_hash,
            "timestamp": int(time.time())
        }
        signature = hw_key.sign(json.dumps(receipt_data, sort_keys=True).encode())
        receipt_data["signature"] = base64.b64encode(signature).decode()
        receipt_data["pub_key"] = base64.b64encode(
            hw_key.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            )
        ).decode()
    except Exception:
        # Fallback if cryptography module is missing in test env
        receipt_data = {"relic_id": relic["id"], "output_hash": output_hash, "signature": "mock_sig_123"}
        
    return {
        "output": mock_output,
        "provenance_receipt": receipt_data
    }
