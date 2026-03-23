# RustChain Node Status Dashboard

Real-time monitoring dashboard for RustChain's 4 attestation nodes. Tracks node health, response times, uptime, and incidents.

**Bounty**: [#2300](https://github.com/Scottcjn/rustchain-bounties/issues/2300) — 50 RTC

## Features
- ⚡ Polls all 4 nodes every 60 seconds
- 📊 Response time graphs (24h history)
- 🔔 Automatic incident detection (node up/down events)
- 📱 Mobile-friendly UI
- 🟢/🔴 Color-coded status indicators

## Deploy
```bash
cd status_dashboard
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python dashboard.py
```
Dashboard runs at `http://localhost:8090`

## Deploy Target
`rustchain.org/status` (nginx config provided separately)

## Nodes Monitored
| Node | Endpoint | Location |
|------|----------|----------|
| Node 1 | https://50.28.86.131/health | LiquidWeb US |
| Node 2 | https://50.28.86.153/health | LiquidWeb US |
| Node 3 | http://76.8.228.245:8099/health | Ryan's Proxmox |
| Node 4 | http://38.76.217.189:8099/health | Hong Kong |

## RTC Wallet
`edisonlv` (on RustChain)
