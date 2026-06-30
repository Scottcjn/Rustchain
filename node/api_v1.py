# SPDX-License-Identifier: MIT
"""Canonical `/api/v1/*` read API.

Closes the nginx-404 gap reported across #7251/#7252/#7297-#7307: the canonical
read paths any explorer / client expects (blocks, epochs, miners, anchors,
attestations, chain status, health) were never bound, so they fell through to an
nginx 404. This blueprint serves them as JSON, read-only, mapped to the existing
tables.

Every response under /api/v1 is JSON, always — the @json_safe guard turns a
db-busy/lock into a 503 and any other failure into a 500 JSON body, and the
catch-all turns an unknown path into a 404 JSON body. Clients never get an
HTML/nginx error page from this surface.

Registered via register_api_v1(app, ...) with its dependencies injected (DB path,
slot helpers, constants) to avoid importing the monolith (circular import).
"""

import sqlite3
import time
from functools import wraps

from flask import Blueprint, jsonify, request


def register_api_v1(app, *, db_path, current_slot, slot_to_epoch,
                    app_version, app_start_ts, per_epoch_rtc,
                    epoch_slots, total_supply_rtc):
    bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")

    def _ro():
        # Read-only connection; never mutates. timeout lets it wait out a writer
        # rather than failing instantly under load.
        return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)

    def json_safe(fn):
        """Guarantee a JSON response for any failure (no HTML 500/nginx page)."""
        @wraps(fn)
        def wrapper(*a, **k):
            try:
                return fn(*a, **k)
            except sqlite3.OperationalError:
                return jsonify({"error": "temporarily_unavailable",
                                "hint": "database busy, retry"}), 503
            except Exception:
                return jsonify({"error": "internal_error"}), 500
        return wrapper

    def _rows(sql, params=()):
        with _ro() as c:
            c.row_factory = sqlite3.Row
            return [dict(r) for r in c.execute(sql, params).fetchall()]

    def _one(sql, params=()):
        with _ro() as c:
            row = c.execute(sql, params).fetchone()
            return row[0] if row else None

    def _limit(default=50, cap=200):
        try:
            n = int(request.args.get("limit", default))
        except (TypeError, ValueError):
            return default
        return max(1, min(n, cap))

    ENDPOINTS = [
        "/api/v1/health", "/api/v1/info", "/api/v1/status", "/api/v1/chain/status",
        "/api/v1/epoch", "/api/v1/miners", "/api/v1/blocks", "/api/v1/blocks/latest",
        "/api/v1/blocks/<slot>", "/api/v1/anchors", "/api/v1/attestations",
        "/api/v1/leaderboard", "/api/v1/governance/proposals",
    ]

    @bp.route("/")
    @bp.route("")
    @json_safe
    def v1_index():
        return jsonify({"ok": True, "api": "rustchain v1", "endpoints": ENDPOINTS})

    @bp.route("/health")
    @bp.route("/healthz")
    @bp.route("/health/check")
    @json_safe
    def v1_health():
        try:
            with _ro() as c:
                c.execute("SELECT 1 FROM schema_version LIMIT 1")
            db_ok = True
        except Exception:
            db_ok = False
        return jsonify({
            "ok": db_ok, "version": app_version,
            "uptime_s": int(time.time() - app_start_ts), "db_ok": db_ok,
        }), (200 if db_ok else 503)

    @bp.route("/info")
    @bp.route("/status")
    @bp.route("/chain")
    @bp.route("/chain/info")
    @bp.route("/chain/status")
    @json_safe
    def v1_info():
        slot = current_slot()
        epoch = slot_to_epoch(slot)
        tip = _one("SELECT MAX(slot) FROM headers")
        miners_24h = _one(
            "SELECT COUNT(*) FROM miner_attest_recent WHERE ts_ok > ?",
            (int(time.time()) - 86400,),
        ) or 0
        return jsonify({
            "ok": True, "version": app_version, "slot": slot, "epoch": epoch,
            "tip_height": tip or 0, "blocks_per_epoch": epoch_slots,
            "epoch_pot_rtc": per_epoch_rtc, "total_supply_rtc": total_supply_rtc,
            "active_miners_24h": miners_24h,
        })

    @bp.route("/epoch")
    @bp.route("/epoch/current")
    @bp.route("/epoch/info")
    @json_safe
    def v1_epoch():
        slot = current_slot()
        epoch = slot_to_epoch(slot)
        enrolled = _one("SELECT COUNT(*) FROM epoch_enroll WHERE epoch = ?", (epoch,)) or 0
        settled = _one("SELECT settled FROM epoch_state WHERE epoch = ?", (epoch,))
        return jsonify({
            "ok": True, "epoch": epoch, "slot": slot, "epoch_pot_rtc": per_epoch_rtc,
            "enrolled_miners": enrolled, "blocks_per_epoch": epoch_slots,
            "settled": bool(settled), "total_supply_rtc": total_supply_rtc,
        })

    @bp.route("/miners")
    @json_safe
    def v1_miners():
        rows = _rows(
            "SELECT miner, device_family, device_arch, ts_ok, "
            "fingerprint_passed FROM miner_attest_recent ORDER BY ts_ok DESC LIMIT ?",
            (_limit(),),
        )
        return jsonify({"ok": True, "count": len(rows), "miners": rows})

    @bp.route("/blocks")
    @bp.route("/blocks/recent")
    @json_safe
    def v1_blocks():
        rows = _rows(
            "SELECT slot, miner_id, ts FROM headers ORDER BY slot DESC LIMIT ?",
            (_limit(),),
        )
        return jsonify({"ok": True, "count": len(rows), "blocks": rows})

    @bp.route("/blocks/latest")
    @json_safe
    def v1_block_latest():
        rows = _rows("SELECT slot, miner_id, ts FROM headers ORDER BY slot DESC LIMIT 1")
        if not rows:
            return jsonify({"ok": False, "error": "no_blocks"}), 404
        return jsonify({"ok": True, "block": rows[0]})

    @bp.route("/blocks/<int:slot>")
    @json_safe
    def v1_block_by_slot(slot):
        rows = _rows("SELECT slot, miner_id, ts FROM headers WHERE slot = ?", (slot,))
        if not rows:
            return jsonify({"ok": False, "error": "block_not_found", "slot": slot}), 404
        return jsonify({"ok": True, "block": rows[0]})

    @bp.route("/anchors")
    @bp.route("/anchors/recent")
    @json_safe
    def v1_anchors():
        rows = _rows(
            "SELECT id, commitment, miner_count, tx_id, status, ergo_height, "
            "created_at FROM ergo_anchors ORDER BY id DESC LIMIT ?",
            (_limit(),),
        )
        return jsonify({"ok": True, "count": len(rows), "anchors": rows})

    @bp.route("/attestations")
    @bp.route("/attestations/recent")
    @json_safe
    def v1_attestations():
        rows = _rows(
            "SELECT miner, device_family, device_arch, ts_ok, fingerprint_passed "
            "FROM miner_attest_recent ORDER BY ts_ok DESC LIMIT ?",
            (_limit(),),
        )
        return jsonify({"ok": True, "count": len(rows), "attestations": rows})

    @bp.route("/leaderboard")
    @json_safe
    def v1_leaderboard():
        rows = _rows(
            "SELECT miner_id, amount_i64 FROM balances "
            "WHERE amount_i64 > 0 ORDER BY amount_i64 DESC LIMIT ?",
            (_limit(),),
        )
        out = [{**r, "balance_rtc": (r.get("amount_i64") or 0) / 1_000_000.0} for r in rows]
        return jsonify({"ok": True, "count": len(out), "leaderboard": out})

    @bp.route("/governance/proposals")
    @bp.route("/governance/list")
    @json_safe
    def v1_governance():
        rows = _rows(
            "SELECT id, proposer_wallet, title, status, created_at, ends_at, "
            "yes_weight, no_weight FROM governance_proposals "
            "ORDER BY id DESC LIMIT ?",
            (_limit(),),
        )
        return jsonify({"ok": True, "count": len(rows), "proposals": rows})

    # Clean JSON 404 for any other /api/v1/* path (no nginx HTML 404).
    @bp.route("/<path:_unknown>")
    @json_safe
    def v1_not_found(_unknown):
        return jsonify({
            "ok": False, "error": "not_found", "path": "/api/v1/" + _unknown,
            "hint": "see GET /api/v1/ for available endpoints",
        }), 404

    app.register_blueprint(bp)
    return bp
