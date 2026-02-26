# RustChain Block Explorer Dashboard

Self-hostable dashboard for RustChain network visibility.

## Features
- Health summary from `/health`
- Active miner table from `/api/miners`
- Epoch metadata from `/epoch`
- Transaction history table (when `/epoch` includes tx data)

## Run
```bash
cd dashboard/block-explorer
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
Then open: `http://localhost:8080`

## Config
- `RUSTCHAIN_API_BASE` (default `https://rustchain.org`)
- `RUSTCHAIN_API_TIMEOUT` (default `8`)
- `PORT` (default `8080`)
