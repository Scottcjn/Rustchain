# RustChain Testnet Faucet

A Flask-based testnet faucet that dispenses free test RTC tokens to developers building on RustChain.

## Features

- **IP-based Rate Limiting**: Prevents abuse by limiting requests to 0.5 RTC per 24 hours per IP
- **SQLite Backend**: Simple, reliable storage for tracking drip requests
- **Simple HTML UI**: Easy-to-use web interface for requesting test tokens
- **REST API**: Programmatic access via JSON API

## Installation

```bash
# Install Flask if not already installed
pip install flask

# Run the faucet
python faucet.py
```

The faucet will start on `http://0.0.0.0:8090/faucet`

## API Endpoints

### GET /faucet

Serves the faucet web interface.

### POST /faucet/drip

Request test tokens.

**Request:**
```json
{
  "wallet": "0x9683744B6b94F2b0966aBDb8C6BdD9805d207c6E"
}
```

**Response (Success):**
```json
{
  "ok": true,
  "amount": 0.5,
  "wallet": "0x9683744B6b94F2b0966aBDb8C6BdD9805d207c6E",
  "next_available": "2026-03-08T14:20:00"
}
```

**Response (Rate Limited):**
```json
{
  "ok": false,
  "error": "Rate limit exceeded",
  "next_available": "2026-03-08T14:20:00"
}
```

## Rate Limits

| Auth Method | Limit |
|--------------|-------|
| IP only | 0.5 RTC per 24 hours |

## Configuration

Edit the following constants in `faucet.py`:

```python
MAX_DRIP_AMOUNT = 0.5  # RTC per request
RATE_LIMIT_HOURS = 24  # Hours between requests
DATABASE = 'faucet.db' # SQLite database file
PORT = 8090           # Server port
```

## Production Notes

For production deployment:

1. **Connect to RustChain node**: Replace the mock `record_drip()` with actual token transfer using the admin transfer API
2. **Use faucet wallet**: Create a dedicated wallet with test tokens for dispensing
3. **Add GitHub OAuth**: Implement GitHub authentication to increase limits (1-2 RTC per 24 hours)
4. **Add SSL/TLS**: Use nginx with Let's Encrypt for HTTPS
5. **Logging**: Add proper logging for monitoring and debugging

## License

Apache License 2.0 - See LICENSE file in RustChain root.
