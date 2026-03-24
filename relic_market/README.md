# Rent-a-Relic Market -- Bounty #2312

Bounty: 150 RTC
Wallet: C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg
Implemented by: kuanglaodi2-sudo (AI Agent)

## What This Is

A wRTC-powered reservation system for booking time on authenticated vintage
computing hardware. Each session generates a cryptographically signed provenance
receipt proving the computation ran on real silicon.

## Files

- relic_market/relic_market.py -- Flask API server
- relic_market/static/marketplace.html -- Marketplace UI

## Running

    cd relic_market
    pip install ecdsa flask
    python relic_market.py
    # Open http://localhost:5003

## API Endpoints

- GET /api/machines -- List all machines
- GET /api/machines/<id>/availability -- Check availability
- POST /api/reserve -- Book a machine
- GET /api/receipt/<id> -- Get receipt
- POST /api/receipt/<id>/submit -- Submit output, get signed receipt
- GET /api/marketplace/stats -- Marketplace statistics
