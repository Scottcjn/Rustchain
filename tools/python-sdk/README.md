# RustChain Python SDK

Lightweight Python wrapper for the [RustChain](https://github.com/Scottcjn/Rustchain) node API.
Uses the `requests` library and covers every public endpoint documented in the
Postman collection and API walkthrough.

## Installation

```bash
pip install -e tools/python-sdk
```

Or from the SDK directory:

```bash
cd tools/python-sdk
pip install .
```

## Quick Start

```python
from rustchain import RustChainClient

client = RustChainClient()          # defaults to mainnet node

# Health check
print(client.get_health())
# {'ok': True, 'version': '2.2.1-rip200', 'uptime_s': ...}

# Epoch info
print(client.get_epoch())
# {'epoch': 95, 'slot': 13365, 'height': 67890}

# Wallet balance
print(client.get_balance("Ivan-houzhiwen"))
# {'amount_rtc': 155.0, 'amount_i64': 155000000, 'miner_id': 'Ivan-houzhiwen'}

# Active miners
miners = client.get_miners()
print(f"{len(miners)} miners online")

# Chain tip
print(client.get_chain_tip())
```

## Signed Transfer

```python
client.submit_transaction(
    from_wallet="sender_wallet_id",
    to_wallet="recipient_wallet_id",
    amount=1000000,           # 1 RTC (smallest units)
    fee=0.001,
    signature="hex_ed25519_signature",
    timestamp=1700000000,
)
```

## All Available Methods

| Category | Method | Endpoint |
|----------|--------|----------|
| Health | `get_health()` | `GET /health` |
| Health | `get_ready()` | `GET /ready` |
| Health | `get_stats()` | `GET /api/stats` |
| Health | `get_metrics()` | `GET /metrics` |
| Epoch | `get_epoch()` | `GET /epoch` |
| Epoch | `enroll_epoch(payload)` | `POST /epoch/enroll` |
| Lottery | `get_eligibility(miner_id)` | `GET /lottery/eligibility` |
| Chain | `get_chain_tip()` | `GET /headers/tip` |
| Chain | `get_bounty_multiplier()` | `GET /api/bounty-multiplier` |
| Miners | `get_miners()` | `GET /api/miners` |
| Miners | `get_nodes()` | `GET /api/nodes` |
| Miners | `get_miner_badge(miner_id)` | `GET /api/badge/{miner_id}` |
| Miners | `get_miner_dashboard(miner_id)` | `GET /api/miner_dashboard/{miner_id}` |
| Miners | `get_miner_attestations(miner_id)` | `GET /api/miner/{id}/attestations` |
| Wallet | `get_balance(miner_id)` | `GET /wallet/balance` |
| Wallet | `get_balance_by_pk(pk)` | `GET /balance/{pk}` |
| Wallet | `get_all_balances()` | `GET /wallet/balances/all` |
| Wallet | `get_wallet_history(miner_id)` | `GET /wallet/history` |
| Wallet | `get_wallet_ledger(miner_id)` | `GET /wallet/ledger` |
| Wallet | `resolve_wallet(address)` | `GET /wallet/resolve` |
| Tx | `submit_transaction(...)` | `POST /wallet/transfer/signed` |
| Attest | `get_attest_challenge()` | `POST /attest/challenge` |
| Attest | `submit_attestation(payload)` | `POST /attest/submit` |
| Fees | `get_fee_pool()` | `GET /api/fee_pool` |
| Rewards | `get_epoch_rewards(epoch)` | `GET /rewards/epoch/{n}` |
| Rewards | `settle_rewards(payload)` | `POST /rewards/settle` |
| Pending | `list_pending(status, limit)` | `GET /pending/list` |
| Pending | `confirm_pending(payload)` | `POST /pending/confirm` |
| Pending | `void_pending(payload)` | `POST /pending/void` |
| Withdraw | `register_withdrawal(payload)` | `POST /withdraw/register` |
| Withdraw | `request_withdrawal(payload)` | `POST /withdraw/request` |
| Withdraw | `get_withdrawal_status(id)` | `GET /withdraw/status/{id}` |
| Withdraw | `get_withdrawal_history(pk)` | `GET /withdraw/history/{pk}` |
| Gov | `create_proposal(payload)` | `POST /governance/propose` |
| Gov | `list_proposals()` | `GET /governance/proposals` |
| Gov | `get_proposal(id)` | `GET /governance/proposal/{id}` |
| Gov | `vote(payload)` | `POST /governance/vote` |
| P2P | `get_p2p_stats()` | `GET /p2p/stats` |
| P2P | `p2p_ping()` | `GET /p2p/ping` |
| P2P | `get_p2p_blocks(start, limit)` | `GET /p2p/blocks` |
| Beacon | `submit_beacon(payload)` | `POST /beacon/submit` |
| Beacon | `get_beacon_digest()` | `GET /beacon/digest` |
| Beacon | `get_beacon_envelopes(limit)` | `GET /beacon/envelopes` |
| Genesis | `export_genesis()` | `GET /genesis/export` |
| Mining | `mine(payload)` | `POST /api/mine` |

## Configuration

```python
client = RustChainClient(
    base_url="https://50.28.86.131",   # node URL
    verify_ssl=False,                   # self-signed cert
    timeout=30,                         # seconds
    retries=3,                          # auto-retry count
    retry_delay=1.0,                    # backoff base (seconds)
    admin_key="YOUR_KEY",               # for admin endpoints
)
```

The client implements a context manager:

```python
with RustChainClient() as client:
    print(client.get_health())
```

## Running Tests

```bash
cd tools/python-sdk
pip install -e ".[dev]"
python -m pytest tests/ -v
```

## License

MIT
