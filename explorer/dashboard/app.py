#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
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
function asObject(v){return v&&typeof v==='object'&&!Array.isArray(v)?v:{};}
function asArray(v){return Array.isArray(v)?v.filter(x=>x&&typeof x==='object'&&!Array.isArray(x)):[];}
function firstPresent(...values){return values.find(v=>v!==undefined&&v!==null&&v!=='');}
function text(v,f='-'){return v===undefined||v===null||v===''?f:String(v);}
function fmtTs(v){if(!v) return '-'; const n=Number(v); if(!Number.isFinite(n)) return String(v); const ms=n>1e12?n:n*1000; return new Date(ms).toLocaleString();}
function td(v){const cell=document.createElement('td');cell.textContent=text(v);return cell;}
function renderRows(tbodyId,rows,limit,mapper,emptyText){
  const tbody=document.getElementById(tbodyId);
  const body=asArray(rows).slice(0,limit).map(row=>{
    const tr=document.createElement('tr');
    tr.append(...mapper(row).map(td));
    return tr;
  });
  if(body.length===0){
    const tr=document.createElement('tr');
    const cell=td(emptyText);
    cell.colSpan=mapper({}).length;
    tr.appendChild(cell);
    body.push(tr);
  }
  tbody.replaceChildren(...body);
}
async function load(){
  const d=asObject(await j('/api/dashboard'));
  const miners=asArray(d.miners);
  const transactions=asArray(d.transactions);
  document.getElementById('base').textContent=text(d.base);
  document.getElementById('network').textContent=text(asObject(d.health).status,'unknown');
  document.getElementById('miners').textContent=miners.length;
  document.getElementById('epoch').textContent=text(asObject(d.epoch).epoch);
  document.getElementById('txcount').textContent=transactions.length;
  renderRows('minersTbl',miners,20,m=>[firstPresent(m.miner_id,m.wallet),firstPresent(m.score,m.attestation_score),firstPresent(m.multiplier,m.antiquity_multiplier)],'No miners');
  renderRows('txTbl',transactions,30,t=>[fmtTs(firstPresent(t.timestamp,t.created_at,t.time)),firstPresent(t.from,t.sender),firstPresent(t.to,t.recipient),firstPresent(t.amount,t.value)],'No transactions');
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
