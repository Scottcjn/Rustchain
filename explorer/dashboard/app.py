#!/usr/bin/env python3
import os, requests
from flask import Flask, jsonify, render_template_string, request

API_BASE = os.environ.get('RUSTCHAIN_API_BASE', 'https://rustchain.org').rstrip('/')
TIMEOUT = float(os.environ.get('RUSTCHAIN_API_TIMEOUT', '8'))

app = Flask(__name__)

HTML = """
<!doctype html><html><head><meta charset='utf-8'><title>RustChain Explorer Dashboard</title>
<style>body{font-family:system-ui;max-width:1100px;margin:24px auto;padding:0 16px} .cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px} .c{border:1px solid #ddd;border-radius:10px;padding:12px} table{width:100%;border-collapse:collapse} td,th{border-bottom:1px solid #eee;padding:6px;text-align:left} code{background:#f4f4f4;padding:2px 4px;border-radius:4px}</style>
</head><body>
<h1>RustChain Explorer Dashboard</h1>
<p>API Base: <code id='base'></code></p>
<div class='cards'>
  <div class='c'><b>Network</b><div id='network'>-</div></div>
  <div class='c'><b>Active Miners</b><div id='miners'>-</div></div>
  <div class='c'><b>Current Epoch</b><div id='epoch'>-</div></div>
  <div class='c'><b>Transactions</b><div id='txcount'>-</div></div>
</div>
<h3>Top Miners</h3><table><thead><tr><th>Miner</th><th>Score</th><th>Multiplier</th></tr></thead><tbody id='minersTbl'></tbody></table>
<h3>Recent Transactions</h3><table><thead><tr><th>Time</th><th>From</th><th>To</th><th>Amount</th></tr></thead><tbody id='txTbl'></tbody></table>
<script>
async function j(u){const r=await fetch(u);return await r.json();}
function fmtTs(v){if(!v) return '-'; const n=Number(v); if(!Number.isFinite(n)) return String(v); const ms=n>1e12?n:n*1000; return new Date(ms).toLocaleString();}
async function load(){
  const d=await j('/api/dashboard');
  document.getElementById('base').textContent=d.base;
  document.getElementById('network').textContent=d.health?.status||'unknown';
  document.getElementById('miners').textContent=(d.miners||[]).length;
  document.getElementById('epoch').textContent=d.epoch?.epoch ?? '-';
  document.getElementById('txcount').textContent=(d.transactions||[]).length;
  document.getElementById('minersTbl').innerHTML=(d.miners||[]).slice(0,20).map(m=>`<tr><td>${m.miner_id||m.wallet||'-'}</td><td>${m.score||m.attestation_score||'-'}</td><td>${m.multiplier||m.antiquity_multiplier||'-'}</td></tr>`).join('');
  document.getElementById('txTbl').innerHTML=(d.transactions||[]).slice(0,30).map(t=>`<tr><td>${fmtTs(t.timestamp||t.created_at||t.time)}</td><td>${t.from||t.sender||'-'}</td><td>${t.to||t.recipient||'-'}</td><td>${t.amount||t.value||'-'}</td></tr>`).join('');
}
load(); setInterval(load, 30000);
</script></body></html>
"""

def fetch_json(path):
    try:
        r=requests.get(f"{API_BASE}{path}", timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {}

@app.get('/')
def home():
    return render_template_string(HTML)

@app.get('/api/dashboard')
def dashboard():
    return jsonify({
      'base': API_BASE,
      'health': fetch_json('/health'),
      'miners': fetch_json('/api/miners') or [],
      'epoch': fetch_json('/epoch'),
      'transactions': fetch_json('/api/transactions') or []
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT','8787')))
