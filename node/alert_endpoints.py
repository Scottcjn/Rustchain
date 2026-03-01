# SPDX-License-Identifier: MIT
# Author: @xiangshangsir (大龙虾 AI)
# BCOS-Tier: L1
# Bounty: #28 - Email/SMS Alert System for Miners
"""
Alert Management API Endpoints
Allows miners to configure their alert preferences via HTTP API.
"""

import json
import sqlite3
import time
from typing import Optional

from flask import jsonify, request


def register_alert_endpoints(app, db_path):
    """Register alert management endpoints"""
    
    def get_db():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    @app.route("/api/alert/preferences", methods=["GET"])
    def get_alert_preferences():
        """
        Get alert preferences for a miner.
        
        Query params:
        - miner_id: required
        """
        miner_id = request.args.get("miner_id")
        if not miner_id:
            return jsonify({"error": "miner_id required"}), 400
        
        db = get_db()
        try:
            row = db.execute("""
                SELECT * FROM alert_preferences WHERE miner_id = ?
            """, (miner_id,)).fetchone()
            
            if not row:
                return jsonify({
                    "ok": True,
                    "preferences": None,
                    "message": "No preferences set. Use POST to configure."
                })
            
            return jsonify({
                "ok": True,
                "preferences": {
                    "miner_id": row["miner_id"],
                    "email": row["email"],
                    "phone": row["phone"],
                    "alert_types": json.loads(row["alert_types"] or "[]"),
                    "enabled": bool(row["enabled"]),
                }
            })
        finally:
            db.close()
    
    @app.route("/api/alert/preferences", methods=["POST"])
    def set_alert_preferences():
        """
        Configure alert preferences for a miner.
        
        Request:
        {
            "miner_id": "mymiminer",
            "email": "user@example.com",
            "phone": "+1234567890",  // optional, for SMS
            "alert_types": ["offline", "reward", "large_transfer"],
            "enabled": true
        }
        """
        data = request.get_json(silent=True) or {}
        miner_id = data.get("miner_id")
        
        if not miner_id:
            return jsonify({"error": "miner_id required"}), 400
        
        email = data.get("email")
        phone = data.get("phone")
        alert_types = data.get("alert_types", [
            "offline", "reward", "large_transfer", "attestation_failure"
        ])
        enabled = data.get("enabled", True)
        
        # Validate alert types
        valid_types = {"offline", "reward", "large_transfer", "attestation_failure"}
        alert_types = [t for t in alert_types if t in valid_types]
        
        db = get_db()
        try:
            db.execute("""
                INSERT OR REPLACE INTO alert_preferences 
                (miner_id, email, phone, alert_types, enabled, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                miner_id,
                email,
                phone,
                json.dumps(alert_types),
                1 if enabled else 0,
                int(time.time())
            ))
            db.commit()
            
            return jsonify({
                "ok": True,
                "message": "Alert preferences saved",
                "preferences": {
                    "miner_id": miner_id,
                    "email": email,
                    "phone": phone,
                    "alert_types": alert_types,
                    "enabled": enabled,
                }
            })
        except sqlite3.Error as e:
            return jsonify({"error": str(e)}), 500
        finally:
            db.close()
    
    @app.route("/api/alert/history", methods=["GET"])
    def get_alert_history():
        """
        Get alert history for a miner.
        
        Query params:
        - miner_id: required
        - limit: optional, default 50, max 200
        - alert_type: optional filter
        """
        miner_id = request.args.get("miner_id")
        if not miner_id:
            return jsonify({"error": "miner_id required"}), 400
        
        limit = min(int(request.args.get("limit", 50)), 200)
        alert_type = request.args.get("alert_type")
        
        db = get_db()
        try:
            query = """
                SELECT * FROM alert_history 
                WHERE miner_id = ?
            """
            params = [miner_id]
            
            if alert_type:
                query += " AND alert_type = ?"
                params.append(alert_type)
            
            query += " ORDER BY sent_at DESC LIMIT ?"
            params.append(limit)
            
            rows = db.execute(query, params).fetchall()
            
            return jsonify({
                "ok": True,
                "history": [dict(row) for row in rows],
                "count": len(rows)
            })
        finally:
            db.close()
    
    @app.route("/api/alert/test", methods=["POST"])
    def send_test_alert():
        """
        Send a test alert to verify configuration.
        
        Request:
        {
            "miner_id": "mymiminer",
            "channel": "email" | "sms" | "both"
        }
        """
        data = request.get_json(silent=True) or {}
        miner_id = data.get("miner_id")
        channel = data.get("channel", "email")
        
        if not miner_id:
            return jsonify({"error": "miner_id required"}), 400
        
        db = get_db()
        try:
            row = db.execute("""
                SELECT email, phone FROM alert_preferences WHERE miner_id = ?
            """, (miner_id,)).fetchone()
            
            if not row:
                return jsonify({
                    "error": "No alert preferences found for this miner"
                }), 404
            
            results = []
            
            # Test email
            if channel in ("email", "both") and row["email"]:
                # In production, this would use the EmailSender class
                results.append({
                    "channel": "email",
                    "to": row["email"],
                    "status": "simulated",
                    "message": "Test email would be sent here"
                })
            
            # Test SMS
            if channel in ("sms", "both") and row["phone"]:
                results.append({
                    "channel": "sms",
                    "to": row["phone"],
                    "status": "simulated",
                    "message": "Test SMS would be sent here"
                })
            
            return jsonify({
                "ok": True,
                "message": "Test alert completed",
                "results": results
            })
        finally:
            db.close()
    
    @app.route("/api/alert/stats", methods=["GET"])
    def get_alert_stats():
        """Get alert statistics"""
        db = get_db()
        try:
            stats = db.execute("""
                SELECT 
                    alert_type,
                    COUNT(*) as total_sent,
                    SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) as successful,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
                FROM alert_history
                GROUP BY alert_type
            """).fetchall()
            
            total = db.execute("""
                SELECT COUNT(*) FROM alert_preferences WHERE enabled = 1
            """).fetchone()[0]
            
            return jsonify({
                "ok": True,
                "stats": [dict(row) for row in stats],
                "active_miners": total,
            })
        finally:
            db.close()
    
    print("[Alert] Management endpoints registered")
