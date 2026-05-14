"""
GPU Render Protocol — Decentralized compute payment layer for RustChain.

Implements Bounty #30:
- GPU Node Attestation (nvidia_gpu, amd_gpu, apple_gpu)
- Render/Voice/LLM escrow payment endpoints
- Pricing oracle with fair market rate tracking
- SQLite-backed escrow and attestation storage

Endpoints:
  POST /gpu/attest          — Register/update GPU attestation
  GET  /gpu/nodes           — List attested GPU nodes
  POST /render/escrow       — Lock RTC for a render job
  POST /render/release      — Release escrow on job completion
  POST /render/refund       — Refund escrow on job failure
  POST /voice/escrow        — Lock RTC for TTS/STT job
  POST /voice/release       — Release on audio delivery
  POST /llm/escrow          — Lock RTC for inference job
  POST /llm/release         — Release on completion
  GET  /render/pricing      — Get current fair market rates
  GET  /render/escrow/<id>  — Get escrow status
"""

import sqlite3
import time
import uuid
import json
import os
import logging
import hashlib
import hmac
import secrets
from functools import wraps

logger = logging.getLogger("gpu_render_protocol")

# ---------------------------------------------------------------------------
# Database schema
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS render_escrow (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT UNIQUE NOT NULL,
    job_type TEXT NOT NULL CHECK(job_type IN ('render', 'tts', 'stt', 'llm')),
    from_wallet TEXT NOT NULL,
    to_wallet TEXT NOT NULL,
    amount_rtc REAL NOT NULL CHECK(amount_rtc > 0),
    status TEXT DEFAULT 'locked' CHECK(status IN ('locked', 'released', 'refunded')),
    created_at INTEGER NOT NULL,
    released_at INTEGER,
    escrow_secret_hash TEXT,
    metadata TEXT  -- JSON blob for job-specific params
);

CREATE TABLE IF NOT EXISTS gpu_attestations (
    miner_id TEXT PRIMARY KEY,
    gpu_model TEXT NOT NULL,
    vram_gb REAL NOT NULL,
    cuda_version TEXT,
    rocm_version TEXT,
    benchmark_score REAL,
    device_arch TEXT NOT NULL CHECK(device_arch IN ('nvidia_gpu', 'amd_gpu', 'apple_gpu')),
    -- Pricing by job type (RTC per unit)
    price_render_minute REAL DEFAULT 0.0,
    price_tts_1k_chars REAL DEFAULT 0.0,
    price_stt_minute REAL DEFAULT 0.0,
    price_llm_1k_tokens REAL DEFAULT 0.0,
    -- Capabilities
    supports_render INTEGER DEFAULT 1,
    supports_tts INTEGER DEFAULT 0,
    supports_stt INTEGER DEFAULT 0,
    supports_llm INTEGER DEFAULT 0,
    tts_models TEXT DEFAULT '[]',   -- JSON array
    llm_models TEXT DEFAULT '[]',   -- JSON array
    last_attestation INTEGER NOT NULL,
    hardware_fingerprint TEXT,
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'suspended', 'offline'))
);

CREATE TABLE IF NOT EXISTS pricing_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_type TEXT NOT NULL,
    device_arch TEXT NOT NULL,
    avg_price REAL NOT NULL,
    min_price REAL NOT NULL,
    max_price REAL NOT NULL,
    sample_count INTEGER NOT NULL,
    recorded_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_escrow_status ON render_escrow(status);
CREATE INDEX IF NOT EXISTS idx_escrow_from ON render_escrow(from_wallet);
CREATE INDEX IF NOT EXISTS idx_escrow_to ON render_escrow(to_wallet);
CREATE INDEX IF NOT EXISTS idx_gpu_arch ON gpu_attestations(device_arch);
"""


class GPURenderProtocol:
    """Core protocol handler for GPU render payments."""

    def __init__(self, db_path=None):
        if db_path is None:
            db_path = os.path.join(
                os.path.dirname(__file__), "..", "data", "gpu_render.db"
            )
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript(SCHEMA_SQL)
        self._ensure_escrow_secret_column(conn)
        conn.commit()
        conn.close()
        logger.info("GPU Render Protocol DB initialized at %s", self.db_path)

    def _ensure_escrow_secret_column(self, conn):
        """Add escrow secret storage for databases created before this guard."""
        cols = {row[1] for row in conn.execute("PRAGMA table_info(render_escrow)").fetchall()}
        if "escrow_secret_hash" not in cols:
            conn.execute("ALTER TABLE render_escrow ADD COLUMN escrow_secret_hash TEXT")

    @staticmethod
    def _hash_escrow_secret(secret: str) -> str:
        return hashlib.sha256((secret or "").encode("utf-8")).hexdigest()

    def _authorize_escrow_action(self, row, actor_wallet: str, escrow_secret: str, required_wallet: str):
        if not actor_wallet or not escrow_secret:
            return {"error": "actor_wallet and escrow_secret are required"}
        if actor_wallet not in {row["from_wallet"], row["to_wallet"]}:
            return {"error": "actor_wallet must be escrow participant"}
        if actor_wallet != required_wallet:
            return {"error": "actor_wallet is not allowed for this escrow action"}
        expected_hash = row["escrow_secret_hash"]
        if not expected_hash:
            return {"error": "escrow_secret missing for existing escrow"}
        if not hmac.compare_digest(self._hash_escrow_secret(escrow_secret), expected_hash):
            return {"error": "invalid escrow_secret"}
        return None

    # -------------------------------------------------------------------
    # GPU Attestation
    # -------------------------------------------------------------------

    def attest_gpu(self, miner_id: str, gpu_info: dict) -> dict:
        """Register or update a GPU node attestation."""
        required = ["gpu_model", "vram_gb", "device_arch"]
        for field in required:
            if field not in gpu_info:
                return {"error": f"Missing required field: {field}"}

        if gpu_info["device_arch"] not in ("nvidia_gpu", "amd_gpu", "apple_gpu"):
            return {"error": "device_arch must be nvidia_gpu, amd_gpu, or apple_gpu"}

        # Generate hardware fingerprint from GPU specs
        fp_data = f"{miner_id}:{gpu_info['gpu_model']}:{gpu_info['vram_gb']}"
        import hashlib
        fingerprint = hashlib.sha256(fp_data.encode()).hexdigest()[:16]

        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO gpu_attestations
                   (miner_id, gpu_model, vram_gb, cuda_version, rocm_version,
                    benchmark_score, device_arch, price_render_minute,
                    price_tts_1k_chars, price_stt_minute, price_llm_1k_tokens,
                    supports_render, supports_tts, supports_stt, supports_llm,
                    tts_models, llm_models, last_attestation, hardware_fingerprint)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(miner_id) DO UPDATE SET
                     gpu_model=excluded.gpu_model,
                     vram_gb=excluded.vram_gb,
                     cuda_version=excluded.cuda_version,
                     rocm_version=excluded.rocm_version,
                     benchmark_score=excluded.benchmark_score,
                     device_arch=excluded.device_arch,
                     price_render_minute=excluded.price_render_minute,
                     price_tts_1k_chars=excluded.price_tts_1k_chars,
                     price_stt_minute=excluded.price_stt_minute,
                     price_llm_1k_tokens=excluded.price_llm_1k_tokens,
                     supports_render=excluded.supports_render,
                     supports_tts=excluded.supports_tts,
                     supports_stt=excluded.supports_stt,
                     supports_llm=excluded.supports_llm,
                     tts_models=excluded.tts_models,
                     llm_models=excluded.llm_models,
                     last_attestation=excluded.last_attestation,
                     hardware_fingerprint=excluded.hardware_fingerprint,
                     status='active'
                """,
                (
                    miner_id,
                    gpu_info["gpu_model"],
                    gpu_info["vram_gb"],
                    gpu_info.get("cuda_version"),
                    gpu_info.get("rocm_version"),
                    gpu_info.get("benchmark_score"),
                    gpu_info["device_arch"],
                    gpu_info.get("price_render_minute", 0.0),
                    gpu_info.get("price_tts_1k_chars", 0.0),
                    gpu_info.get("price_stt_minute", 0.0),
                    gpu_info.get("price_llm_1k_tokens", 0.0),
                    gpu_info.get("supports_render", 1),
                    gpu_info.get("supports_tts", 0),
                    gpu_info.get("supports_stt", 0),
                    gpu_info.get("supports_llm", 0),
                    json.dumps(gpu_info.get("tts_models", [])),
                    json.dumps(gpu_info.get("llm_models", [])),
                    int(time.time()),
                    fingerprint,
                ),
            )
            conn.commit()
            return {
                "status": "attested",
                "miner_id": miner_id,
                "fingerprint": fingerprint,
                "device_arch": gpu_info["device_arch"],
            }
        finally:
            conn.close()

    def list_gpu_nodes(self, job_type=None, device_arch=None) -> list:
        """List active GPU nodes, optionally filtered by capability or arch."""
        conn = self._get_conn()
        try:
            query = "SELECT * FROM gpu_attestations WHERE status='active'"
            params = []
            if job_type:
                col = f"supports_{job_type}"
                query += f" AND {col}=1"
            if device_arch:
                query += " AND device_arch=?"
                params.append(device_arch)
            query += " ORDER BY benchmark_score DESC"
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # -------------------------------------------------------------------
    # Escrow operations
    # -------------------------------------------------------------------

    def create_escrow(self, job_type: str, from_wallet: str, to_wallet: str,
                      amount_rtc: float, metadata: dict = None) -> dict:
        """Lock RTC in escrow for a compute job."""
        valid_types = ("render", "tts", "stt", "llm")
        if job_type not in valid_types:
            return {"error": f"job_type must be one of {valid_types}"}
        if amount_rtc <= 0:
            return {"error": "amount_rtc must be positive"}
        if from_wallet == to_wallet:
            return {"error": "from_wallet and to_wallet must differ"}

        job_id = f"{job_type}-{uuid.uuid4().hex[:12]}"
        escrow_secret = secrets.token_hex(16)
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO render_escrow
                   (job_id, job_type, from_wallet, to_wallet, amount_rtc,
                    status, created_at, escrow_secret_hash, metadata)
                   VALUES (?,?,?,?,?,'locked',?,?,?)""",
                (job_id, job_type, from_wallet, to_wallet, amount_rtc,
                 int(time.time()), self._hash_escrow_secret(escrow_secret),
                 json.dumps(metadata or {})),
            )
            conn.commit()
            return {
                "status": "locked",
                "job_id": job_id,
                "job_type": job_type,
                "amount_rtc": amount_rtc,
                "from_wallet": from_wallet,
                "to_wallet": to_wallet,
                "escrow_secret": escrow_secret,
            }
        finally:
            conn.close()

    def release_escrow(self, job_id: str, actor_wallet: str = "", escrow_secret: str = "") -> dict:
        """Release escrowed RTC to the GPU provider on job completion."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM render_escrow WHERE job_id=?", (job_id,)
            ).fetchone()
            if not row:
                return {"error": "Job not found"}
            if row["status"] != "locked":
                return {"error": f"Job already {row['status']}"}
            auth_error = self._authorize_escrow_action(
                row,
                actor_wallet=actor_wallet,
                escrow_secret=escrow_secret,
                required_wallet=row["from_wallet"],
            )
            if auth_error:
                return auth_error

            now = int(time.time())
            conn.execute(
                "UPDATE render_escrow SET status='released', released_at=? WHERE job_id=?",
                (now, job_id),
            )
            conn.commit()
            return {
                "status": "released",
                "job_id": job_id,
                "amount_rtc": row["amount_rtc"],
                "to_wallet": row["to_wallet"],
                "released_at": now,
            }
        finally:
            conn.close()

    def refund_escrow(self, job_id: str, actor_wallet: str = "", escrow_secret: str = "") -> dict:
        """Refund escrowed RTC to the requester on job failure."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM render_escrow WHERE job_id=?", (job_id,)
            ).fetchone()
            if not row:
                return {"error": "Job not found"}
            if row["status"] != "locked":
                return {"error": f"Job already {row['status']}"}
            auth_error = self._authorize_escrow_action(
                row,
                actor_wallet=actor_wallet,
                escrow_secret=escrow_secret,
                required_wallet=row["to_wallet"],
            )
            if auth_error:
                return auth_error

            now = int(time.time())
            conn.execute(
                "UPDATE render_escrow SET status='refunded', released_at=? WHERE job_id=?",
                (now, job_id),
            )
            conn.commit()
            return {
                "status": "refunded",
                "job_id": job_id,
                "amount_rtc": row["amount_rtc"],
                "from_wallet": row["from_wallet"],
                "refunded_at": now,
            }
        finally:
            conn.close()

    def get_escrow(self, job_id: str) -> dict:
        """Get escrow status for a job."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM render_escrow WHERE job_id=?", (job_id,)
            ).fetchone()
            if not row:
                return {"error": "Job not found"}
            result = dict(row)
            result["metadata"] = json.loads(result.get("metadata") or "{}")
            return result
        finally:
            conn.close()

    # -------------------------------------------------------------------
    # Pricing Oracle
    # -------------------------------------------------------------------

    def get_fair_market_rates(self, job_type=None) -> dict:
        """Calculate fair market rates from active GPU node pricing."""
        conn = self._get_conn()
        try:
            nodes = conn.execute(
                "SELECT * FROM gpu_attestations WHERE status='active'"
            ).fetchall()

            if not nodes:
                return {"error": "No active GPU nodes", "rates": {}}

            price_fields = {
                "render": "price_render_minute",
                "tts": "price_tts_1k_chars",
                "stt": "price_stt_minute",
                "llm": "price_llm_1k_tokens",
            }

            types_to_check = [job_type] if job_type else list(price_fields.keys())
            rates = {}

            for jt in types_to_check:
                field = price_fields[jt]
                prices = [dict(n)[field] for n in nodes if dict(n)[field] > 0]
                if prices:
                    rates[jt] = {
                        "avg": round(sum(prices) / len(prices), 6),
                        "min": round(min(prices), 6),
                        "max": round(max(prices), 6),
                        "providers": len(prices),
                        "unit": "RTC/minute" if jt in ("render", "stt") else
                                "RTC/1k_chars" if jt == "tts" else "RTC/1k_tokens",
                    }

                    # Record to pricing history
                    conn.execute(
                        """INSERT INTO pricing_history
                           (job_type, device_arch, avg_price, min_price,
                            max_price, sample_count, recorded_at)
                           VALUES (?,?,?,?,?,?,?)""",
                        (jt, "all", rates[jt]["avg"], rates[jt]["min"],
                         rates[jt]["max"], len(prices), int(time.time())),
                    )

            conn.commit()
            return {"rates": rates, "timestamp": int(time.time())}
        finally:
            conn.close()

    def detect_price_manipulation(self, job_type: str, proposed_price: float) -> dict:
        """Check if a proposed price deviates significantly from market rates."""
        rates = self.get_fair_market_rates(job_type)
        if "error" in rates or job_type not in rates.get("rates", {}):
            return {"manipulated": False, "reason": "insufficient data"}

        r = rates["rates"][job_type]
        # Flag if price is >3x the average or <0.1x the minimum
        if proposed_price > r["avg"] * 3:
            return {"manipulated": True, "reason": "price_too_high",
                    "proposed": proposed_price, "market_avg": r["avg"]}
        if proposed_price < r["min"] * 0.1:
            return {"manipulated": True, "reason": "price_too_low",
                    "proposed": proposed_price, "market_min": r["min"]}
        return {"manipulated": False, "proposed": proposed_price,
                "market_avg": r["avg"]}


# ---------------------------------------------------------------------------
# Flask route registration (integrates with existing RustChain node)
# ---------------------------------------------------------------------------

def register_routes(app):
    """Register GPU Render Protocol routes with a Flask app."""
    protocol = GPURenderProtocol()

    @app.route("/gpu/attest", methods=["POST"])
    def gpu_attest():
        from flask import request, jsonify
        data = request.get_json(force=True)
        miner_id = data.get("miner_id")
        if not miner_id:
            return jsonify({"error": "miner_id required"}), 400
        result = protocol.attest_gpu(miner_id, data)
        status_code = 200 if "error" not in result else 400
        return jsonify(result), status_code

    @app.route("/gpu/nodes", methods=["GET"])
    def gpu_nodes():
        from flask import request, jsonify
        job_type = request.args.get("job_type")
        device_arch = request.args.get("device_arch")
        nodes = protocol.list_gpu_nodes(job_type, device_arch)
        return jsonify({"nodes": nodes, "count": len(nodes)})

    @app.route("/render/escrow", methods=["POST"])
    @app.route("/voice/escrow", methods=["POST"])
    @app.route("/llm/escrow", methods=["POST"])
    def create_escrow():
        from flask import request, jsonify
        data = request.get_json(force=True)
        # Infer job_type from path
        path = request.path
        if path.startswith("/voice"):
            job_type = data.get("job_type", "tts")  # tts or stt
        elif path.startswith("/llm"):
            job_type = "llm"
        else:
            job_type = data.get("job_type", "render")

        result = protocol.create_escrow(
            job_type=job_type,
            from_wallet=data.get("from_wallet", ""),
            to_wallet=data.get("to_wallet", ""),
            amount_rtc=data.get("amount_rtc", 0),
            metadata=data.get("metadata"),
        )
        status_code = 201 if "error" not in result else 400
        return jsonify(result), status_code

    @app.route("/render/release", methods=["POST"])
    @app.route("/voice/release", methods=["POST"])
    @app.route("/llm/release", methods=["POST"])
    def release_escrow():
        from flask import request, jsonify
        data = request.get_json(force=True)
        result = protocol.release_escrow(
            data.get("job_id", ""),
            actor_wallet=data.get("actor_wallet", ""),
            escrow_secret=data.get("escrow_secret", ""),
        )
        status_code = 200 if "error" not in result else 400
        return jsonify(result), status_code

    @app.route("/render/refund", methods=["POST"])
    def refund_escrow():
        from flask import request, jsonify
        data = request.get_json(force=True)
        result = protocol.refund_escrow(
            data.get("job_id", ""),
            actor_wallet=data.get("actor_wallet", ""),
            escrow_secret=data.get("escrow_secret", ""),
        )
        status_code = 200 if "error" not in result else 400
        return jsonify(result), status_code

    @app.route("/render/escrow/<job_id>", methods=["GET"])
    def get_escrow(job_id):
        from flask import jsonify
        result = protocol.get_escrow(job_id)
        status_code = 200 if "error" not in result else 404
        return jsonify(result), status_code

    @app.route("/render/pricing", methods=["GET"])
    def get_pricing():
        from flask import request, jsonify
        job_type = request.args.get("job_type")
        result = protocol.get_fair_market_rates(job_type)
        return jsonify(result)

    @app.route("/render/pricing/check", methods=["POST"])
    def check_pricing():
        from flask import request, jsonify
        data = request.get_json(force=True)
        result = protocol.detect_price_manipulation(
            data.get("job_type", "render"),
            data.get("price", 0),
        )
        return jsonify(result)

    logger.info("GPU Render Protocol routes registered")
    return protocol
