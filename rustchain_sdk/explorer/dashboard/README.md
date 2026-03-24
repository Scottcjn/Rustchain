# RustChain Block Explorer Dashboard

Self-hostable dashboard for RustChain network stats.

## Features
- Health status from `/health`
- Active miners from `/api/miners`
- Current epoch snapshot from `/epoch`
- Transaction list from `/api/transactions` (if available)

## Run
```bash
cd explorer/dashboard
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export RUSTCHAIN_API_BASE="https://rustchain.org"
python app.py
```

Open: `http://localhost:8787`
