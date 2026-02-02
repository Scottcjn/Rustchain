# RTC x402 Payment Protocol

Implementation of the HTTP 402 Payment Required protocol for RustChain micropayments.

## Overview

The x402 protocol enables machine-to-machine micropayments over HTTP:

1. Client requests a resource
2. Server returns `402 Payment Required` with payment details
3. Client automatically pays via RTC
4. Client retries with payment proof
5. Server verifies payment and serves the resource

This enables AI agents, IoT devices, and automated services to transact without human intervention.

## Installation

```bash
pip install flask requests pynacl
# Optional for BIP39 support:
pip install mnemonic
```

## Quick Start

### Server Side

```python
from flask import Flask
from rtc_payment_middleware import require_rtc_payment

app = Flask(__name__)

@app.route('/api/data')
@require_rtc_payment(amount=0.001, recipient='your_wallet_id')
def get_data():
    return {'data': 'premium content'}
```

### Client Side

```python
from rtc_payment_client import RTCClient

client = RTCClient(
    wallet_seed='your-24-word-seed-phrase',
    max_payment=1.0  # Safety limit
)

# Automatic 402 handling
response = client.get('https://api.example.com/api/data')
# Client detects 402 → signs RTC payment → retries → returns 200
```

## Protocol Specification

### 402 Response Headers

| Header | Description | Example |
|--------|-------------|---------|
| `X-Payment-Amount` | Payment amount required | `0.001` |
| `X-Payment-Currency` | Currency code | `RTC` |
| `X-Payment-Address` | Recipient wallet | `gurgguda` |
| `X-Payment-Network` | Network identifier | `rustchain` |
| `X-Payment-Nonce` | Unique payment nonce | `a1b2c3d4...` |
| `X-Payment-Endpoint` | Payment submission URL | `https://50.28.86.131/wallet/transfer/signed` |

### Payment Proof Headers

| Header | Description |
|--------|-------------|
| `X-Payment-TX` | Transaction hash |
| `X-Payment-Signature` | Ed25519 signature of `nonce:tx_hash` |
| `X-Payment-Sender` | Sender's public key (hex) |
| `X-Payment-Nonce` | Original nonce from 402 response |

## Components

### `rtc_payment_middleware.py`

Flask middleware for payment-gated endpoints.

```python
from rtc_payment_middleware import require_rtc_payment

@app.route('/premium')
@require_rtc_payment(
    amount=0.001,       # RTC amount
    recipient='wallet', # Recipient wallet ID
    rate_limit=100      # Max requests per minute
)
def premium_endpoint():
    # g.rtc_sender contains payer's address
    return {'data': 'paid content'}
```

### `rtc_payment_client.py`

HTTP client with automatic payment handling.

```python
from rtc_payment_client import RTCClient

client = RTCClient(
    wallet_seed='...',  # BIP39 seed phrase
    max_payment=1.0,    # Max auto-pay amount
    auto_pay=True       # Enable automatic 402 handling
)

# All HTTP methods supported
response = client.get(url)
response = client.post(url, json=data)

# Check spending
print(client.total_spent)  # Total RTC spent
print(client.payment_history)  # List of receipts
```

## Security Considerations

1. **Max Payment Limit**: Always set `max_payment` to prevent runaway spending
2. **SSL Verification**: Enable in production with trusted certificates
3. **Nonce Replay**: Server caches nonces to prevent replay attacks
4. **Rate Limiting**: Built-in rate limiting per sender

## Examples

### Run the Demo Server

```bash
export RTC_PAYMENT_ADDRESS=gurgguda
python example_app.py
```

### Test with curl

```bash
# Get 402 response
curl http://localhost:5000/api/data

# Response:
# HTTP/1.1 402 Payment Required
# X-Payment-Amount: 0.001
# X-Payment-Currency: RTC
# X-Payment-Address: gurgguda
# ...
```

### Run the Demo Client

```bash
python example_client.py
```

## API Reference

### `require_rtc_payment(amount, recipient, rate_limit)`

Decorator to require RTC payment for Flask endpoints.

**Parameters:**
- `amount` (float): Payment amount in RTC
- `recipient` (str): Wallet address to receive payment
- `rate_limit` (int): Max requests per minute per sender (default: 100)

### `RTCClient(wallet_seed, max_payment, auto_pay)`

HTTP client with automatic payment handling.

**Parameters:**
- `wallet_seed` (str): BIP39 24-word seed phrase
- `max_payment` (float): Maximum auto-pay amount (default: 1.0)
- `auto_pay` (bool): Enable automatic 402 handling (default: True)

**Properties:**
- `wallet_address`: Client's wallet address
- `total_spent`: Total RTC spent
- `payment_history`: List of PaymentReceipt objects

## License

MIT License - Part of the RustChain ecosystem.

## Links

- [RustChain Repository](https://github.com/Scottcjn/Rustchain)
- [x402 Protocol Spec](https://github.com/x402/spec)
- [HTTP 402 RFC](https://tools.ietf.org/html/rfc7231#section-6.5.2)
