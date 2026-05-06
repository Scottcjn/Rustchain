from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from trust_sync import TrustSyncEngine
from migration_handler import MigrationHandler

app = FastAPI(title="AgentFolio ↔ Beacon Integration API")
engine = TrustSyncEngine()
migrator = MigrationHandler()

class ClaimRequest(BaseModel):
    agent_id: str
    beacon_wallet: str
    signature: str

class TrustResponse(BaseModel):
    agent_id: str
    dual_layer_score: float
    trust_hash: str

@app.post("/api/v1/integration/claim")
def claim_identity(req: ClaimRequest):
    # In prod: verify Ed25519 signature
    rec = engine.sync_agent(req.agent_id, req.beacon_wallet, 0.8, 0.9)
    return {"status": "claimed", "dual_layer_score": rec.dual_layer_score}

@app.get("/api/v1/integration/trust/{agent_id}", response_model=TrustResponse)
def get_trust(agent_id: str):
    rec = engine.get_trust(agent_id)
    if not rec:
        raise HTTPException(404, "Agent not found")
    return TrustResponse(agent_id=rec.agent_id, dual_layer_score=rec.dual_layer_score, trust_hash=rec.trust_hash)

@app.post("/api/v1/integration/migrate")
def migrate_agent(moltbook_key: str, agent_id: str, beacon_wallet: str):
    result = migrator.execute_migration(moltbook_key, agent_id, beacon_wallet)
    if result["status"] == "failed":
        raise HTTPException(400, result["reason"])
    return result

# Run with: uvicorn api_server:app --reload
