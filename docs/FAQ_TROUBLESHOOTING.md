# RustChain FAQ and Troubleshooting

This guide covers common setup and runtime issues for miners and node users.

## FAQ

### 1) What is the difference between RTC and wRTC?

- `RTC` is native to RustChain.
- `wRTC` is the wrapped Solana representation used for bridge/swap workflows.
- Official wRTC mint:
  `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X`

### 2) How do I check if the network is online?

```bash
curl -sk https://rustchain.org/health | jq .
```

You should see a JSON response. If the command times out repeatedly, check local firewall/VPN and retry.

### 3) How do I verify my miner is visible?

```bash
curl -sk https://rustchain.org/api/miners | jq .
```

If your miner is missing, wait a few minutes after startup and re-check logs.

### 4) How do I check wallet balance?

```bash
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET_NAME" | jq .
```

### 5) Is self-signed TLS expected on the node API?

Yes. Existing docs use `-k`/`--insecure` for this reason:

```bash
curl -sk https://rustchain.org/health
```

## Troubleshooting

### Installer script fails immediately

Symptoms:
- install script exits during dependency or venv stage

Checks:
```bash
python3 --version
curl --version
bash --version
```

Fix:
1. Ensure `python3`, `curl`, and `bash` are available in `PATH`.
2. Re-run install script with a clean shell session.

### Miner starts but no rewards appear

Checks:
1. Confirm wallet/miner id is the one you query.
2. Confirm node health and miners endpoint are reachable.
3. Keep miner online long enough for epoch settlement.

Commands:
```bash
curl -sk https://rustchain.org/health | jq .
curl -sk https://rustchain.org/api/miners | jq .
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET_NAME" | jq .
```

### API calls fail with SSL/certificate errors

Use `-k` as shown in official docs:

```bash
curl -sk https://rustchain.org/api/miners | jq .
```

### Bridge/swap confusion (RTC vs wRTC)

- Bridge URL: <https://bottube.ai/bridge>
- Raydium swap URL:
  <https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X>
- Always verify mint:
  `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X`

### Wrong wallet/address format submitted

- Do not reuse addresses across incompatible chains without bridge flow.
- Recheck destination before signing.
- If unsure, perform a small test transfer first.

## Quick Incident Checklist

1. Confirm service health endpoint.
2. Confirm miner appears in `/api/miners`.
3. Confirm wallet query uses exact miner id.
4. Confirm bridge direction and token mint.
5. Capture command output and timestamps for support.

## Security Notes

- Never share seed phrases or private keys.
- Avoid links from unknown DMs.
- Bookmark official RustChain and BoTTube URLs.
