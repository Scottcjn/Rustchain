"""Flask blueprint for SophiaCore Attestation Inspector.

Provides REST endpoints for hardware fingerprint inspection,
verdict queries, admin override, and batch processing.
"""
import json
import hashlib
from flask import Blueprint, request, jsonify, render_template_string

from .db import (
    save_inspection,
    get_latest_verdict,
    get_history,
    get_queue,
    override_verdict,
)
from .inspector import evaluate_fingerprint, compute_fingerprint_hash
from .batch import run_batch

sophia_bp = Blueprint("sophia", __name__)


# ─── Inspect ────────────────────────────────────────────────────────────────

@sophia_bp.route("/inspect", methods=["POST"])
def inspect():
    """Inspect a hardware fingerprint and return a verdict.

    POST body (JSON):
        miner_id: str        — unique miner identifier
        fingerprint: dict    — hardware metadata
        test_mode: bool      — optional, deterministic test verdicts

    Returns:
        JSON {verdict, confidence, reasoning, signature, miner_id}
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    miner_id = data.get("miner_id")
    fingerprint = data.get("fingerprint", {})
    test_mode = bool(data.get("test_mode", False))

    if not miner_id:
        return jsonify({"error": "miner_id is required"}), 400

    if not fingerprint:
        return jsonify({"error": "fingerprint data is required"}), 400

    verdict, confidence, reasoning = evaluate_fingerprint(fingerprint, test_mode=test_mode)

    # Generate signature (deterministic hash of verdict components)
    sig_input = f"{miner_id}:{verdict.value}:{confidence}:{fingerprint.get('cpu_arch','')}"
    signature = hashlib.sha256(sig_input.encode()).hexdigest()

    # Persist to DB
    save_inspection(
        miner_id=miner_id,
        verdict=verdict.value,
        confidence=confidence,
        reasoning=reasoning,
        signature=signature,
        fingerprint_data=json.dumps(fingerprint),
        test_mode=test_mode,
    )

    return jsonify({
        "verdict": verdict.value,
        "confidence": round(confidence, 4),
        "reasoning": reasoning,
        "signature": signature,
        "miner_id": miner_id,
        "test_mode": test_mode,
    })


# ─── Status ─────────────────────────────────────────────────────────────────

@sophia_bp.route("/status/<miner_id>", methods=["GET"])
def status(miner_id: str):
    """Get the latest inspection verdict for a miner."""
    record = get_latest_verdict(miner_id)
    if not record:
        return jsonify({"error": "No inspection found for miner"}), 404

    return jsonify({
        "miner_id": record["miner_id"],
        "verdict": record["verdict"],
        "confidence": record["confidence"],
        "reasoning": record["reasoning"],
        "signature": record["signature"],
        "inspected_at": record["inspected_at"],
    })


# ─── History ────────────────────────────────────────────────────────────────

@sophia_bp.route("/history/<miner_id>", methods=["GET"])
def history(miner_id: str):
    """Get the last N inspection records for a miner (default 30)."""
    limit = request.args.get("limit", 30, type=int)
    records = get_history(miner_id, limit=limit)
    return jsonify({
        "miner_id": miner_id,
        "count": len(records),
        "records": [
            {
                "verdict": r["verdict"],
                "confidence": r["confidence"],
                "reasoning": r["reasoning"],
                "inspected_at": r["inspected_at"],
            }
            for r in records
        ],
    })


# ─── Queue ──────────────────────────────────────────────────────────────────

@sophia_bp.route("/queue", methods=["GET"])
def queue():
    """Get miners with CAUTIOUS or SUSPICIOUS verdicts pending review."""
    status_filter = request.args.get("status", None)
    if status_filter and status_filter.upper() in ("CAUTIOUS", "SUSPICIOUS"):
        items = get_queue(status=status_filter.upper())
    else:
        items = get_queue()

    return jsonify({
        "count": len(items),
        "items": [
            {
                "miner_id": r["miner_id"],
                "verdict": r["verdict"],
                "confidence": r["confidence"],
                "reasoning": r["reasoning"],
                "latest_at": r["latest_at"],
            }
            for r in items
        ],
    })


# ─── Override ───────────────────────────────────────────────────────────────

@sophia_bp.route("/override", methods=["POST"])
def override():
    """Admin override for a miner's verdict.

    POST body (JSON):
        miner_id: str
        new_verdict: str (APPROVED, CAUTIOUS, SUSPICIOUS, REJECTED)
        reason: str          — explanation for the override
        admin_key: str       — admin authentication
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    miner_id = data.get("miner_id")
    new_verdict = data.get("new_verdict")
    reason = data.get("reason", "")
    admin_key = data.get("admin_key", "")

    if not miner_id or not new_verdict or not reason:
        return jsonify({"error": "miner_id, new_verdict, and reason are required"}), 400

    valid_verdicts = {"APPROVED", "CAUTIOUS", "SUSPICIOUS", "REJECTED"}
    if new_verdict.upper() not in valid_verdicts:
        return jsonify({"error": f"new_verdict must be one of {valid_verdicts}"}), 400

    success = override_verdict(miner_id, new_verdict.upper(), reason, admin_key)
    if not success:
        return jsonify({"error": "Override failed — invalid admin_key"}), 403

    return jsonify({
        "success": True,
        "miner_id": miner_id,
        "new_verdict": new_verdict.upper(),
        "reason": reason,
    })


# ─── Batch ──────────────────────────────────────────────────────────────────

@sophia_bp.route("/batch", methods=["POST"])
def batch():
    """Trigger batch inspection on all known miners."""
    # Optional: require admin key for batch
    admin_key = request.headers.get("X-Admin-Key", "")
    if admin_key != "SOPHIA_ADMIN_KEY":
        return jsonify({"error": "Unauthorized"}), 403

    results = run_batch()
    return jsonify({"success": True, "results": results})


# ─── Dashboard HTML ─────────────────────────────────────────────────────────

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SophiaCore — Attestation Inspector</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #0f1117; color: #e0e0e0; padding: 2rem; }
  h1 { color: #7c6af7; margin-bottom: 1.5rem; }
  h2 { color: #a090ff; margin: 1.5rem 0 0.75rem; font-size: 1.1rem; }
  .card { background: #1a1d27; border: 1px solid #2a2d3a; border-radius: 8px;
          padding: 1.25rem; margin-bottom: 1rem; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 4px;
           font-size: 0.75rem; font-weight: bold; }
  .APPROVED { background: #0d3d1e; color: #4ade80; }
  .CAUTIOUS { background: #3d2e0d; color: #fbbf24; }
  .SUSPICIOUS { background: #3d1a0d; color: #fb923c; }
  .REJECTED { background: #3d0d0d; color: #f87171; }
  table { width: 100%%; border-collapse: collapse; margin-top: 0.75rem; font-size: 0.875rem; }
  th { text-align: left; padding: 6px 10px; border-bottom: 1px solid #2a2d3a; color: #888; }
  td { padding: 6px 10px; border-bottom: 1px solid #1f2230; }
  tr:hover td { background: #1f2230; }
  .mono { font-family: monospace; font-size: 0.8rem; color: #888; }
  form { display: grid; gap: 0.75rem; }
  label { font-size: 0.85rem; color: #888; }
  input, select { background: #0f1117; border: 1px solid #2a2d3a; border-radius: 4px;
                  color: #e0e0e0; padding: 6px 10px; font-size: 0.875rem; width: 100%%; }
  button { background: #7c6af7; color: white; border: none; border-radius: 4px;
           padding: 8px 16px; cursor: pointer; font-size: 0.875rem; }
  button:hover { background: #6b5ce7; }
  button.danger { background: #dc2626; }
  button.danger:hover { background: #b91c1c; }
  .msg { padding: 8px 12px; border-radius: 4px; margin-top: 0.75rem; font-size: 0.85rem; }
  .msg.ok { background: #0d3d1e; color: #4ade80; }
  .msg.err { background: #3d0d0d; color: #f87171; }
  .row { display: flex; gap: 1rem; flex-wrap: wrap; }
  .col { flex: 1; min-width: 300px; }
  #queue-table td:first-child { max-width: 150px; overflow: hidden; text-overflow: ellipsis; }
</style>
</head>
<body>
<h1>SophiaCore Attestation Inspector</h1>

<div class="row">
  <div class="col">
    <div class="card">
      <h2>Queue — Pending Review</h2>
      <div id="queue-msg">Loading...</div>
      <table id="queue-table" style="display:none">
        <thead><tr><th>Miner ID</th><th>Verdict</th><th>Confidence</th><th>Latest At</th></tr></thead>
        <tbody id="queue-body"></tbody>
      </table>
    </div>
  </div>
  <div class="col">
    <div class="card">
      <h2>Admin Override</h2>
      <form id="override-form">
        <div>
          <label>Miner ID</label>
          <input type="text" id="ov-miner" required>
        </div>
        <div>
          <label>New Verdict</label>
          <select id="ov-verdict">
            <option value="APPROVED">APPROVED</option>
            <option value="CAUTIOUS">CAUTIOUS</option>
            <option value="SUSPICIOUS">SUSPICIOUS</option>
            <option value="REJECTED">REJECTED</option>
          </select>
        </div>
        <div>
          <label>Reason</label>
          <input type="text" id="ov-reason" required>
        </div>
        <div>
          <label>Admin Key</label>
          <input type="password" id="ov-key" required>
        </div>
        <button type="submit">Apply Override</button>
        <div id="ov-msg"></div>
      </form>
    </div>
    <div class="card">
      <h2>Batch Inspection</h2>
      <button id="batch-btn">Run Batch</button>
      <div id="batch-msg"></div>
    </div>
  </div>
</div>

<div class="card">
  <h2>Recent Inspection History</h2>
  <div id="hist-msg">Loading...</div>
  <table id="hist-table" style="display:none">
    <thead><tr><th>Miner ID</th><th>Verdict</th><th>Confidence</th><th>Reasoning</th><th>Inspected At</th></tr></thead>
    <tbody id="hist-body"></tbody>
  </table>
</div>

<script>
const API = '/sophia';
async function jsonFetch(url, opts) {
  const r = await fetch(url, opts);
  const j = await r.json();
  if (!r.ok) throw new Error(j.error || 'Request failed');
  return j;
}

async function loadQueue() {
  try {
    const d = await jsonFetch(API + '/queue');
    const tbl = document.getElementById('queue-table');
    const body = document.getElementById('queue-body');
    if (d.count === 0) {
      document.getElementById('queue-msg').textContent = 'No pending items.';
      return;
    }
    document.getElementById('queue-msg').textContent = '';
    tbl.style.display = '';
    body.innerHTML = '';
    d.items.forEach(r => {
      body.innerHTML += `<tr>
        <td title="${r.miner_id}">${r.miner_id}</td>
        <td><span class="badge ${r.verdict}">${r.verdict}</span></td>
        <td>${(r.confidence*100).toFixed(1)}%%</td>
        <td class="mono">${r.latest_at}</td>
      </tr>`;
    });
  } catch(e) { document.getElementById('queue-msg').textContent = e.message; }
}

document.getElementById('override-form').onsubmit = async e => {
  e.preventDefault();
  const msg = document.getElementById('ov-msg');
  try {
    const r = await jsonFetch(API + '/override', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        miner_id: document.getElementById('ov-miner').value,
        new_verdict: document.getElementById('ov-verdict').value,
        reason: document.getElementById('ov-reason').value,
        admin_key: document.getElementById('ov-key').value,
      })
    });
    msg.className = 'msg ok';
    msg.textContent = 'Override applied: ' + r.new_verdict;
    loadQueue();
  } catch(e) { msg.className = 'msg err'; msg.textContent = e.message; }
};

document.getElementById('batch-btn').onclick = async () => {
  const msg = document.getElementById('batch-msg');
  msg.className = 'msg';
  msg.textContent = 'Running batch...';
  try {
    const r = await jsonFetch(API + '/batch', {
      method: 'POST',
      headers: {'X-Admin-Key': 'SOPHIA_ADMIN_KEY'}
    });
    const rr = r.results;
    msg.className = 'msg ok';
    msg.textContent = `Batch done: ${rr.total} miners — APPROVED=${rr.APPROVED} CAUTIOUS=${rr.CAUTIOUS} SUSPICIOUS=${rr.SUSPICIOUS} REJECTED=${rr.REJECTED} errors=${rr.errors}`;
    loadQueue();
  } catch(e) { msg.className = 'msg err'; msg.textContent = e.message; }
};

loadQueue();
</script>
</body>
</html>"""


@sophia_bp.route("/dashboard", methods=["GET"])
def dashboard():
    """Serve the SophiaCore admin dashboard HTML."""
    return render_template_string(DASHBOARD_HTML)
