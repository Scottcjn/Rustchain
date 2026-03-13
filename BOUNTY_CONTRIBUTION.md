# Bounty Contribution

This addresses issue #908: [BOUNTY: 15 RTC] Implement /wallet/history endpoint (fixes #775, #886)

## Description
## Implement the /wallet/history Endpoint

**Reward: 15 RTC**

### Background
The `/wallet/history` endpoint is documented in the API spec but returns 404. Multiple bug reports have been filed (#775, #886). Time to fix it.

### Task
Add a `/wallet/history` endpoint to `rustchain_v2_integrated_v2.2.1_rip200.py` that returns transaction history for a given wallet/miner ID.

### Expected Behavior
```
GET /wallet/history?miner_id=dual-g4-125&limit=50

Response:
{
  "ok": true,
  "miner_id": "dual-g4

## Payment
0x4F666e7b4F63637223625FD4e9Ace6055fD6a847
