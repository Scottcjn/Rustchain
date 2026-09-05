# RustChain Testnet Faucet

The supported testnet faucet is **`faucet_service/faucet_service.py`**. It is the
only faucet in this repository that transfers RTC.

> **Do not deploy the root `faucet.py`.** It is a demo: it records drip requests
> and never calls the node, so every caller is told the request succeeded while
> nothing is sent (issue #8243). It is kept in-tree only as a small reference for
> the rate-limiting and wallet-validation logic, and it now labels itself as a
> demo in its startup banner, in its web page and in its JSON payload
> (`"sent": false`).

| | `faucet_service/faucet_service.py` | `faucet.py` (root) |
|---|---|---|
| Transfers RTC | yes, `POST /wallet/transfer` on the node | **no** |
| Records `tx_hash` | yes | no (always `null`) |
| Rate limiting | ip / wallet / hybrid, optional Redis | ip + wallet, SQLite only |
| Config file | `faucet_config.yaml` | constants in the source |
| Shipped as a service | `testnet/systemd/rustchain-testnet-faucet.service` | no |
| Supported | **yes** | no — demo only |

## Installation

```bash
cd faucet_service
pip install -r requirements.txt

# X-Admin-Key used for POST /wallet/transfer on the node.
export RC_ADMIN_KEY="your-admin-key"

python faucet_service.py --config faucet_config.yaml
```

The faucet starts on `http://<host>:<port><base_path>` (default
`http://0.0.0.0:8090/faucet`).

For a full testnet deployment use `testnet/deploy_testnet.sh`, which generates
`faucet_config.yaml`, writes `RC_ADMIN_KEY` into the environment file and
installs `rustchain-testnet-faucet.service`.

## Configuration

The full annotated configuration lives in
[`faucet_service/faucet_config.yaml`](faucet_service/faucet_config.yaml); the
service-level documentation is in
[`faucet_service/README.md`](faucet_service/README.md). The settings that decide
whether the faucet actually pays:

```yaml
distribution:
  amount: 0.5
  mock_mode: false                    # true = record only, transfer nothing
  node_url: "http://127.0.0.1:8198"   # node exposing POST /wallet/transfer
  faucet_wallet: "testnet_faucet"     # wallet the node debits
  admin_key: null                     # prefer the RC_ADMIN_KEY env variable
```

`mock_mode` defaults to **false**. It used to default to true, which meant a
faucet started without an explicit setting recorded drips, answered `ok`, and
paid nobody (issue #8243).

The service audits this configuration at startup, before it binds a port:

- `mock_mode: true` → a warning banner is logged
  (`FAUCET IS IN MOCK MODE - NO RTC WILL BE SENT`) and the faucet starts anyway,
  because mock mode is a legitimate local-development choice.
- `mock_mode: false` with no `RC_ADMIN_KEY` and no `distribution.admin_key` →
  startup fails with `FaucetConfigError`, instead of accepting traffic and
  returning a 500 on every drip.

## API

### `GET <base_path>`

Serves the faucet web interface.

### `POST <base_path>/drip`

Request test tokens.

**Request:**

```json
{ "wallet": "RTC0123456789abcdef0123456789abcdef01234567" }
```

**Response (success):**

```json
{
  "ok": true,
  "amount": 0.5,
  "wallet": "RTC0123456789abcdef0123456789abcdef01234567",
  "tx_hash": "0x...",
  "next_available": "2026-03-08T14:20:00"
}
```

`tx_hash` is `null` when the service is running in mock mode — that is the field
to check if you need to know whether a transfer actually happened.

**Response (rate limited):**

```json
{
  "ok": false,
  "error": "Rate limit exceeded",
  "next_available": "2026-03-08T14:20:00"
}
```

### `GET <base_path>/status`

Faucet statistics, including the current `mock_mode` value.

### `GET <base_path>/health`

Health check endpoint.

## Rate limits

Configured under `rate_limit` (`ip`, `wallet` or `hybrid`); the deployed testnet
faucet uses `hybrid` with 0.5 RTC per 24 h. Redis can be enabled for distributed
rate limiting.

## Production notes

1. Keep `mock_mode: false` and supply `RC_ADMIN_KEY` through the environment,
   not the config file.
2. Fund `distribution.faucet_wallet` — the node debits it on every drip.
3. Terminate TLS in front of the service (nginx + Let's Encrypt).
4. Monitor `GET <base_path>/status`: `mock_mode: true` on a public faucet means
   users are being told they were paid when they were not.

## License

Apache License 2.0 — see LICENSE file in RustChain root.
