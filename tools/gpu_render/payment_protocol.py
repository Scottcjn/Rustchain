"""
GPU Render Payment Protocol

RPC endpoints for decentralized GPU rendering with RTC payments.
"""

from flask import Flask, request, jsonify
import sqlite3
import time
import os

app = Flask(__name__)

DB_PATH = os.getenv("RUSTCHAIN_DB", "rustchain.db")


def get_db():
    """Get database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================
# GPU Node Attestation
# ============================================================

@app.route("/api/gpu/attest", methods=["POST"])
def gpu_attest():
    """Register a GPU node for rendering."""
    data = request.json
    
    miner_pubkey = data.get("miner_pubkey")
    gpu_model = data.get("gpu_model")
    vram_gb = data.get("vram_gb")
    cuda_version = data.get("cuda_version")
    rocm_version = data.get("rocm_version")
    benchmark_score = data.get("benchmark_score")
    job_types = data.get("job_types", ["render"])  # render, tts, stt, llm
    
    if not miner_pubkey or not gpu_model:
        return jsonify({"error": "miner_pubkey and gpu_model required"}), 400
    
    db = get_db()
    try:
        db.execute("""
            INSERT OR REPLACE INTO gpu_nodes 
            (miner_pubkey, gpu_model, vram_gb, cuda_version, rocm_version, 
             benchmark_score, job_types, last_attest)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (miner_pubkey, gpu_model, vram_gb, cuda_version, rocm_version,
              benchmark_score, ",".join(job_types), int(time.time())))
        db.commit()
        
        return jsonify({
            "ok": True,
            "miner_pubkey": miner_pubkey,
            "job_types": job_types
        })
    finally:
        db.close()


@app.route("/api/gpu/nodes")
def list_gpu_nodes():
    """List available GPU nodes."""
    job_type = request.args.get("job_type")
    
    db = get_db()
    try:
        if job_type:
            nodes = db.execute("""
                SELECT * FROM gpu_nodes 
                WHERE job_types LIKE ?
            """, (f"%{job_type}%",)).fetchall()
        else:
            nodes = db.execute("SELECT * FROM gpu_nodes").fetchall()
        
        return jsonify({
            "nodes": [dict(n) for n in nodes]
        })
    finally:
        db.close()


# ============================================================
# Render Escrow
# ============================================================

@app.route("/render/escrow", methods=["POST"])
def render_escrow():
    """Lock RTC for a render job."""
    data = request.json
    
    job_id = data.get("job_id")
    from_wallet = data.get("from_wallet")
    to_wallet = data.get("to_wallet")
    amount = data.get("amount")
    job_type = data.get("job_type", "render")
    
    if not all([job_id, from_wallet, to_wallet, amount]):
        return jsonify({"error": "Missing required fields"}), 400
    
    db = get_db()
    try:
        # Check balance
        balance = db.execute(
            "SELECT balance FROM wallets WHERE wallet = ?", (from_wallet,)
        ).fetchone()
        
        if not balance or balance[0] < amount:
            return jsonify({"error": "Insufficient balance"}), 400
        
        # Lock funds
        db.execute("""
            INSERT INTO escrow (job_id, from_wallet, to_wallet, amount, job_type, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'locked', ?)
        """, (job_id, from_wallet, to_wallet, amount, job_type, int(time.time())))
        
        # Deduct from balance
        db.execute(
            "UPDATE wallets SET balance = balance - ? WHERE wallet = ?",
            (amount, from_wallet)
        )
        db.commit()
        
        return jsonify({
            "ok": True,
            "job_id": job_id,
            "amount": amount,
            "status": "locked"
        })
    finally:
        db.close()


@app.route("/render/release", methods=["POST"])
def render_release():
    """Release escrow to GPU node on job completion."""
    data = request.json
    
    job_id = data.get("job_id")
    
    if not job_id:
        return jsonify({"error": "job_id required"}), 400
    
    db = get_db()
    try:
        escrow = db.execute(
            "SELECT * FROM escrow WHERE job_id = ?", (job_id,)
        ).fetchone()
        
        if not escrow:
            return jsonify({"error": "Escrow not found"}), 404
        
        if escrow["status"] != "locked":
            return jsonify({"error": "Escrow not locked"}), 400
        
        # Transfer to GPU node
        db.execute(
            "UPDATE wallets SET balance = balance + ? WHERE wallet = ?",
            (escrow["amount"], escrow["to_wallet"])
        )
        
        # Update status
        db.execute(
            "UPDATE escrow SET status = 'released', released_at = ? WHERE job_id = ?",
            (int(time.time()), job_id)
        )
        db.commit()
        
        return jsonify({
            "ok": True,
            "job_id": job_id,
            "released_to": escrow["to_wallet"],
            "amount": escrow["amount"]
        })
    finally:
        db.close()


@app.route("/render/refund", methods=["POST"])
def render_refund():
    """Refund escrow if job fails."""
    data = request.json
    
    job_id = data.get("job_id")
    
    if not job_id:
        return jsonify({"error": "job_id required"}), 400
    
    db = get_db()
    try:
        escrow = db.execute(
            "SELECT * FROM escrow WHERE job_id = ?", (job_id,)
        ).fetchone()
        
        if not escrow:
            return jsonify({"error": "Escrow not found"}), 404
        
        # Refund to sender
        db.execute(
            "UPDATE wallets SET balance = balance + ? WHERE wallet = ?",
            (escrow["amount"], escrow["from_wallet"])
        )
        
        # Update status
        db.execute(
            "UPDATE escrow SET status = 'refunded', refunded_at = ? WHERE job_id = ?",
            (int(time.time()), job_id)
        )
        db.commit()
        
        return jsonify({
            "ok": True,
            "job_id": job_id,
            "refunded_to": escrow["from_wallet"],
            "amount": escrow["amount"]
        })
    finally:
        db.close()


# ============================================================
# Voice/Audio (TTS/STT)
# ============================================================

@app.route("/voice/escrow", methods=["POST"])
def voice_escrow():
    """Lock RTC for TTS/STT job."""
    return render_escrow()  # Same logic, different job_type


@app.route("/voice/release", methods=["POST"])
def voice_release():
    """Release on audio delivery."""
    return render_release()


# ============================================================
# LLM Inference
# ============================================================

@app.route("/llm/escrow", methods=["POST"])
def llm_escrow():
    """Lock RTC for inference job."""
    return render_escrow()


@app.route("/llm/release", methods=["POST"])
def llm_release():
    """Release on completion."""
    return render_release()


# ============================================================
# Pricing Oracle
# ============================================================

@app.route("/api/pricing/history")
def pricing_history():
    """Get pricing history for job types."""
    job_type = request.args.get("job_type", "render")
    
    db = get_db()
    try:
        history = db.execute("""
            SELECT * FROM pricing_history 
            WHERE job_type = ?
            ORDER BY timestamp DESC
            LIMIT 100
        """, (job_type,)).fetchall()
        
        return jsonify({
            "job_type": job_type,
            "history": [dict(h) for h in history]
        })
    finally:
        db.close()


@app.route("/api/pricing/current")
def current_pricing():
    """Get current fair market rates."""
    db = get_db()
    try:
        rates = db.execute("""
            SELECT job_type, AVG(price_per_unit) as avg_price, COUNT(*) as samples
            FROM pricing_history
            WHERE timestamp > ?
            GROUP BY job_type
        """, (int(time.time()) - 7*24*3600,)).fetchall()  # Last 7 days
        
        return jsonify({
            "rates": [
                {
                    "job_type": r["job_type"],
                    "price_per_unit": r["avg_price"],
                    "samples": r["samples"]
                }
                for r in rates
            ]
        })
    finally:
        db.close()


# ============================================================
# Database Setup
# ============================================================

def init_db():
    """Initialize database tables."""
    db = get_db()
    try:
        # GPU Nodes table
        db.execute("""
            CREATE TABLE IF NOT EXISTS gpu_nodes (
                id INTEGER PRIMARY KEY,
                miner_pubkey TEXT UNIQUE,
                gpu_model TEXT,
                vram_gb INTEGER,
                cuda_version TEXT,
                rocm_version TEXT,
                benchmark_score REAL,
                job_types TEXT,
                last_attest INTEGER
            )
        """)
        
        # Escrow table
        db.execute("""
            CREATE TABLE IF NOT EXISTS escrow (
                id INTEGER PRIMARY KEY,
                job_id TEXT UNIQUE,
                from_wallet TEXT,
                to_wallet TEXT,
                amount REAL,
                job_type TEXT,
                status TEXT,
                created_at INTEGER,
                released_at INTEGER,
                refunded_at INTEGER
            )
        """)
        
        # Pricing history
        db.execute("""
            CREATE TABLE IF NOT EXISTS pricing_history (
                id INTEGER PRIMARY KEY,
                job_type TEXT,
                price_per_unit REAL,
                node_wallet TEXT,
                timestamp INTEGER
            )
        """)
        
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8099)
