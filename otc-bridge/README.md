# RustChain OTC Bridge

Peer-to-peer RTC trading with on-chain escrow via RIP-302 Agent Economy.

## Features

### Tier 1: OTC Order Book
- Web-based order book showing buy/sell orders for RTC
- POST endpoint to create orders (wallet, amount, price, direction)
- Match display with aggregated bids/asks and spread
- Auto-refresh every 15 seconds
- SQLite persistence -- shared order book between all users
- Dark theme matching RustChain branding

### Tier 2: Escrow & Settlement
- **RTC escrow via RIP-302**: Sell orders lock RTC in Agent Economy escrow
- **HTLC smart contract** (Solidity): Hash Time-Locked Contract for ETH/USDC side on Base
- **Near-atomic settlement**: HTLC secret reveal links RTC release to quote currency payment
- **Transaction history & audit trail**: All trades recorded with timestamps and TX hashes
- **Rate limiting**: 10 requests/minute per IP

### Supported Pairs
| Pair | Quote Currency |
|------|---------------|
| RTC/USDC | USDC on Base |
| RTC/ETH | ETH |
| RTC/ERG | ERG (private Ergo chain) |

## Architecture

```
Seller posts sell order
  → Backend locks RTC in RIP-302 escrow (/agent/jobs)
  → Order appears in order book

Buyer matches order
  → Buyer locks ETH/USDC in HTLC smart contract (hashlock = seller's htlc_hash)

Seller confirms (reveals HTLC secret)
  → RTC escrow releases to buyer
  → Buyer uses revealed secret to claim ETH/USDC from HTLC

Timeout (no confirmation within 24h)
  → Buyer reclaims ETH/USDC from HTLC
  → RTC escrow cancels, returns to seller
```

## Quick Start

```bash
pip install -r requirements.txt
python otc_bridge.py
# → Running on http://0.0.0.0:5580
```

Or with Docker:
```bash
docker build -t otc-bridge .
docker run -p 5580:5580 otc-bridge
```

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/orders | Create buy/sell order |
| GET | /api/orders | List open orders (filter by pair, side) |
| GET | /api/orders/{id} | Order detail |
| POST | /api/orders/{id}/match | Match an order (counterparty) |
| POST | /api/orders/{id}/confirm | Confirm settlement |
| POST | /api/orders/{id}/cancel | Cancel open order |
| GET | /api/trades | Trade history |
| GET | /api/orderbook | Aggregated book (bids/asks/spread) |
| GET | /api/stats | Market stats |

### Create Order
```bash
curl -X POST http://localhost:5580/api/orders \
  -H "Content-Type: application/json" \
  -d '{"side":"sell","pair":"RTC/USDC","wallet":"my-wallet","amount_rtc":100,"price_per_rtc":0.10}'
```

### Match Order
```bash
curl -X POST http://localhost:5580/api/orders/otc_abc123/match \
  -H "Content-Type: application/json" \
  -d '{"wallet":"RTC...","eth_address":"0x...","wallet_auth":{"public_key":"<ed25519-public-key-hex>","signature":"<signature-hex>","timestamp":1760000000}}'
```

`match` and `cancel` require `wallet_auth` for the wallet performing the action.
Sign this canonical JSON payload with the wallet's Ed25519 key:
`{"action":"match_order","order_id":"otc_abc123","timestamp":1760000000,"wallet":"RTC..."}`
Use `"cancel_order"` for cancellations. The timestamp must be within 5 minutes.

## HTLC Contract (Base)

The Solidity HTLC contract (`contracts/HTLC.sol`) supports both ETH and ERC20 (USDC) swaps:

- `createSwapETH()` -- Lock ETH with hashlock + timelock
- `createSwapERC20()` -- Lock USDC/ERC20 with hashlock + timelock
- `claim()` -- Seller reveals preimage to claim funds
- `refund()` -- Buyer reclaims after timeout

Uses OpenZeppelin ReentrancyGuard and SafeERC20. Minimum timelock: 1 hour. Maximum: 7 days.

## Tests

```bash
python -m pytest test_otc_bridge.py -v
# 23 tests, all passing
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| RUSTCHAIN_NODE | https://50.28.86.131 | RustChain node URL |
| OTC_DB_PATH | otc_bridge.db | SQLite database path |
| OTC_PORT | 5580 | Server port |

## License

MIT

---

Built by [WireWork](https://wirework.dev) for RustChain Bounty #695.
Wallet: wirework
