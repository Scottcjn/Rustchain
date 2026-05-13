#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
BCOS v2 — RustChain Node Endpoints.

Adds /bcos/* routes to the RustChain Flask application:
  POST /bcos/attest            Submit BCOS attestation on-chain
  GET  /bcos/verify/<cert_id>  Verify certificate + return proof
  GET  /bcos/cert/<cert_id>.pdf  Download PDF certificate
  GET  /bcos/badge/<cert_id>.svg Embeddable SVG badge
  GET  /bcos/directory         List all certified repos

Usage in main node file:
    from bcos_routes import register_bcos_routes
    register_bcos_routes(app, DB_PATH)
"""

from __future__ import annotations

import io
import json
import hmac
import os
import sqlite3
import time
from hashlib import blake2b

from flask import Blueprint, Response, jsonify, request, send_file

# Try to import PDF generator (optional — only needed for cert endpoint)
try:
    from bcos_pdf import generate_certificate
    HAVE_PDF = True
except ImportError:
    HAVE_PDF = False

# Try to import Ed25519 verification
try:
    from nacl.signing import VerifyKey
    from nacl.exceptions import BadSignatureError
    HAVE_NACL = True
except ImportError:
    HAVE_NACL = False


bcos_bp = Blueprint("bcos", __name__)

# Module-level ref to DB_PATH, set by register_bcos_routes
_DB_PATH = None


def _get_admin_key():
    return os.environ.get("RC_ADMIN_KEY", "")


def _parse_trust_score(raw_score) -> int:
    """Validate BCOS trust scores before they are stored or rendered."""
    if isinstance(raw_score, bool):
        raise ValueError("trust_score must be a number")

    try:
        score = int(raw_score)
    except (TypeError, ValueError) as exc:
        raise ValueError("trust_score must be a number") from exc

    if not (0 <= score <= 100):
        raise ValueError("trust_score must be between 0 and 100")

    return score


def _parse_bounded_int_arg(name: str, default: int, maximum: int):
    """Parse a bounded integer query arg for public BCOS endpoints."""
    raw = request.args.get(name, str(default))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None, jsonify({"error": "invalid_pagination", "message": f"{name} must be an integer"}), 400

    if value < 0:
        return None, jsonify({"error": "invalid_pagination", "message": f"{name} must be non-negative"}), 400

    return min(value, maximum), None, None


def _verify_commitment(report_json_str: str, claimed_commitment: str) -> bool:
    """Recompute BLAKE2b commitment and compare."""
    try:
        # Reparse and re-serialize to canonical form
        report = json.loads(report_json_str)
        # Remove cert_id and commitment before recomputing
        # (they were added after the commitment was computed)
        report_copy = {k: v for k, v in report.items()
                       if k not in ("cert_id", "commitment")}
        canonical = json.dumps(report_copy, sort_keys=True, separators=(",", ":"))
        computed = blake2b(canonical.encode(), digest_size=32).hexdigest()
        return computed == claimed_commitment
    except Exception:
        return False


def _verify_ed25519(commitment: str, signature_hex: str, pubkey_hex: str) -> bool:
    """Verify Ed25519 signature over commitment string."""
    if not HAVE_NACL:
        return False
    try:
        vk = VerifyKey(bytes.fromhex(pubkey_hex))
        vk.verify(commitment.encode(), bytes.fromhex(signature_hex))
        return True
    except (BadSignatureError, Exception):
        return False


# ── Database ──────────────────────────────────────────────────────

def init_bcos_table(conn):
    """Create bcos_attestations table. Call from init_db()."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bcos_attestations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cert_id TEXT UNIQUE NOT NULL,
            commitment TEXT NOT NULL,
            repo TEXT NOT NULL,
            commit_sha TEXT NOT NULL,
            tier TEXT NOT NULL,
            trust_score INTEGER NOT NULL,
            reviewer TEXT,
            report_json TEXT NOT NULL,
            signature TEXT,
            signer_pubkey TEXT,
            anchored_epoch INTEGER,
            created_at INTEGER NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_bcos_repo ON bcos_attestations(repo)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_bcos_commit ON bcos_attestations(commit_sha)"
    )


# ── SVG Badge Template ────────────────────────────────────────────

BADGE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="20">
  <linearGradient id="g" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r"><rect width="{width}" height="20" rx="3"/></clipPath>
  <g clip-path="url(#r)">
    <rect width="50" height="20" fill="#555"/>
    <rect x="50" width="{right_width}" height="20" fill="{color}"/>
    <rect width="{width}" height="20" fill="url(#g)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">
    <text x="25" y="15" fill="#010101" fill-opacity=".3">BCOS</text>
    <text x="25" y="14">BCOS</text>
    <text x="{text_x}" y="15" fill="#010101" fill-opacity=".3">{label}</text>
    <text x="{text_x}" y="14">{label}</text>
  </g>
</svg>"""


def _generate_badge_svg(tier: str, score: int) -> str:
    """Generate SVG badge for a BCOS certification."""
    # Color by tier
    colors = {
        "L0": "#4c1",     # Green
        "L1": "#08c",     # Blue
        "L2": "#93c",     # Purple
    }
    if score < 40:
        color = "#e05d44"  # Red
    else:
        color = colors.get(tier, "#08c")

    label = f"{tier} {score}/100"
    right_width = max(70, len(label) * 7 + 10)
    width = 50 + right_width
    text_x = 50 + right_width // 2

    return BADGE_SVG.format(
        width=width,
        right_width=right_width,
        color=color,
        text_x=text_x,
        label=label,
    )


# ── Routes ────────────────────────────────────────────────────────

@bcos_bp.route("/bcos/attest", methods=["POST"])
def bcos_attest():
    """Submit a BCOS attestation to the on-chain ledger.

    Requires either:
    - X-Admin-Key header matching RC_ADMIN_KEY, OR
    - Valid Ed25519 signature in the report
    """
    admin_key = request.headers.get("X-Admin-Key", "")
    is_admin = admin_key and hmac.compare_digest(admin_key, _get_admin_key() or "")

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    # Extract fields from report or from wrapper
    report = data.get("report", data)
    cert_id = report.get("cert_id")
    commitment = report.get("commitment")
    repo = report.get("repo_name", report.get("repo", ""))
    commit_sha = report.get("commit_sha", "")
    tier = report.get("tier", "L1")
    raw_trust_score = report.get("trust_score", 0)
    reviewer = report.get("reviewer", "")
    signature = data.get("signature", report.get("signature", ""))
    signer_pubkey = data.get("signer_pubkey", report.get("signer_pubkey", ""))

    # Validation
    if not cert_id or not commitment:
        return jsonify({"error": "cert_id and commitment required"}), 400
    if not repo:
        return jsonify({"error": "repo_name or repo required"}), 400
    try:
        trust_score = _parse_trust_score(raw_trust_score)
    except ValueError as e:
        return jsonify({"error": "invalid_trust_score", "message": str(e)}), 400
    report["trust_score"] = trust_score

    # Auth: admin key OR valid Ed25519 signature
    sig_valid = False
    if signature and signer_pubkey:
        sig_valid = _verify_ed25519(commitment, signature, signer_pubkey)

    if not is_admin and not sig_valid:
        return jsonify({
            "error": "Unauthorized - admin key or valid Ed25519 signature required",
            "hint": "Use X-Admin-Key header or sign the commitment with Ed25519",
        }), 401

    # Verify commitment matches report
    report_json_str = json.dumps(report, sort_keys=True, separators=(",", ":"))

    # Store
    now = int(time.time())
    try:
        with sqlite3.connect(_DB_PATH) as conn:
            # Calculate current epoch for anchoring
            epoch = None
            try:
                from rip_200_round_robin_1cpu1vote import current_slot
                epoch = current_slot()
            except Exception:
                pass

            conn.execute("""
                INSERT OR REPLACE INTO bcos_attestations
                (cert_id, commitment, repo, commit_sha, tier, trust_score,
                 reviewer, report_json, signature, signer_pubkey,
                 anchored_epoch, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cert_id, commitment, repo, commit_sha, tier, trust_score,
                reviewer, report_json_str,
                signature or None, signer_pubkey or None,
                epoch, now,
            ))
            conn.commit()

        return jsonify({
            "ok": True,
            "cert_id": cert_id,
            "commitment": commitment,
            "repo": repo,
            "tier": tier,
            "trust_score": trust_score,
            "anchored_epoch": epoch,
            "verify_url": f"https://rustchain.org/bcos/verify/{cert_id}",
            "badge_url": f"https://50.28.86.131/bcos/badge/{cert_id}.svg",
        })
    except sqlite3.IntegrityError:
        return jsonify({"error": f"Certificate {cert_id} already exists"}), 409
    except Exception as e:
        import logging
        logging.exception("bcos_handler failed")
        return jsonify({"error": "internal_error"}), 500


@bcos_bp.route("/bcos/verify/<cert_id>", methods=["GET"])
def bcos_verify(cert_id):
    """Verify a BCOS certificate by ID. Returns full attestation + proof."""
    try:
        with sqlite3.connect(_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM bcos_attestations WHERE cert_id = ?",
                (cert_id,)
            ).fetchone()

        if not row:
            return jsonify({
                "ok": False,
                "error": f"No certificate found for {cert_id}",
                "hint": "Check the cert_id format: BCOS-xxxxxxxx",
            }), 404

        # Recompute commitment from stored report
        report = json.loads(row["report_json"])
        report_copy = {k: v for k, v in report.items()
                       if k not in ("cert_id", "commitment")}
        canonical = json.dumps(report_copy, sort_keys=True, separators=(",", ":"))
        recomputed = blake2b(canonical.encode(), digest_size=32).hexdigest()
        commitment_valid = recomputed == row["commitment"]

        # Verify Ed25519 signature if present
        sig_valid = None
        if row["signature"] and row["signer_pubkey"]:
            sig_valid = _verify_ed25519(
                row["commitment"], row["signature"], row["signer_pubkey"]
            )

        return jsonify({
            "ok": True,
            "verified": commitment_valid and (sig_valid is not False),
            "cert_id": row["cert_id"],
            "commitment": row["commitment"],
            "commitment_valid": commitment_valid,
            "signature_valid": sig_valid,
            "repo": row["repo"],
            "commit_sha": row["commit_sha"],
            "tier": row["tier"],
            "trust_score": row["trust_score"],
            "tier_met": row["trust_score"] >= {"L0": 40, "L1": 60, "L2": 80}.get(row["tier"], 60),
            "reviewer": row["reviewer"],
            "anchored_epoch": row["anchored_epoch"],
            "created_at": row["created_at"],
            "score_breakdown": report.get("score_breakdown", {}),
            "checks": report.get("checks", {}),
            "engine_version": report.get("engine_version", "unknown"),
            "badge_url": f"https://50.28.86.131/bcos/badge/{cert_id}.svg",
            "pdf_url": f"https://50.28.86.131/bcos/cert/{cert_id}.pdf",
        })
    except Exception as e:
        import logging
        logging.exception("bcos_handler failed")
        return jsonify({"error": "internal_error"}), 500


@bcos_bp.route("/bcos/cert/<cert_id>.pdf", methods=["GET"])
def bcos_certificate_pdf(cert_id):
    """Generate and serve a PDF certificate."""
    if not HAVE_PDF:
        return jsonify({"error": "PDF generation not available (install fpdf2)"}), 501

    try:
        with sqlite3.connect(_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM bcos_attestations WHERE cert_id = ?",
                (cert_id,)
            ).fetchone()

        if not row:
            return jsonify({"error": f"Certificate {cert_id} not found"}), 404

        # Build attestation dict for PDF generator
        report = json.loads(row["report_json"])
        attestation = {
            **report,
            "cert_id": row["cert_id"],
            "commitment": row["commitment"],
            "signature": row["signature"] or "",
            "signer_pubkey": row["signer_pubkey"] or "",
            "anchored_epoch": row["anchored_epoch"],
        }

        pdf_bytes = generate_certificate(attestation)

        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"{cert_id}.pdf",
        )
    except Exception as e:
        import logging
        logging.exception("bcos_handler failed")
        return jsonify({"error": "internal_error"}), 500


@bcos_bp.route("/bcos/badge/<cert_id>.svg", methods=["GET"])
def bcos_badge_svg(cert_id):
    """Generate SVG badge for a BCOS-certified repo."""
    # Strip .svg extension if present in cert_id
    cert_id = cert_id.replace(".svg", "")

    try:
        with sqlite3.connect(_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT tier, trust_score FROM bcos_attestations WHERE cert_id = ?",
                (cert_id,)
            ).fetchone()

        if not row:
            # Return a "not found" badge
            svg = _generate_badge_svg("??", 0)
        else:
            svg = _generate_badge_svg(row["tier"], row["trust_score"])

        return Response(svg, mimetype="image/svg+xml",
                        headers={"Cache-Control": "max-age=300"})
    except Exception as e:
        return Response(
            _generate_badge_svg("ERR", 0),
            mimetype="image/svg+xml",
        )


@bcos_bp.route("/bcos/directory", methods=["GET"])
def bcos_directory():
    """List all BCOS-certified repos with latest attestation."""
    tier_filter = request.args.get("tier", "").upper()
    limit, error_response, status = _parse_bounded_int_arg("limit", 100, 500)
    if error_response is not None:
        return error_response, status
    offset, error_response, status = _parse_bounded_int_arg("offset", 0, 10_000)
    if error_response is not None:
        return error_response, status

    try:
        with sqlite3.connect(_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row

            query = """
                SELECT cert_id, repo, commit_sha, tier, trust_score,
                       reviewer, anchored_epoch, created_at
                FROM bcos_attestations
            """
            params = []

            if tier_filter in ("L0", "L1", "L2"):
                query += " WHERE tier = ?"
                params.append(tier_filter)

            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            rows = conn.execute(query, params).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM bcos_attestations"
            ).fetchone()[0]

        certs = []
        for row in rows:
            certs.append({
                "cert_id": row["cert_id"],
                "repo": row["repo"],
                "commit_sha": row["commit_sha"][:12],
                "tier": row["tier"],
                "trust_score": row["trust_score"],
                "reviewer": row["reviewer"],
                "anchored_epoch": row["anchored_epoch"],
                "created_at": row["created_at"],
                "verify_url": f"https://rustchain.org/bcos/verify/{row['cert_id']}",
                "badge_url": f"https://50.28.86.131/bcos/badge/{row['cert_id']}.svg",
            })

        return jsonify({
            "ok": True,
            "total": total,
            "count": len(certs),
            "offset": offset,
            "certificates": certs,
        })
    except Exception as e:
        import logging
        logging.exception("bcos_handler failed")
        return jsonify({"error": "internal_error"}), 500


# ── Registration ──────────────────────────────────────────────────

def register_bcos_routes(app, db_path: str):
    """Register BCOS blueprint with the Flask app."""
    global _DB_PATH
    _DB_PATH = db_path
    app.register_blueprint(bcos_bp)
