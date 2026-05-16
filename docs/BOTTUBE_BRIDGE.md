# BoTTube to RustChain RTC Bridge

`integrations/bottube_bridge.py` is a small daemon that turns BoTTube activity
into RTC transfers. It polls public BoTTube video feeds, resolves creator RTC
wallets, applies anti-abuse checks, and queues payments through RustChain
`POST /wallet/transfer`.

## Reward Types

The bridge supports three reward families:

- Upload rewards for qualifying videos.
- View and subscriber milestone rewards.
- Tips from BoTTube earnings data when an authenticated BoTTube API key exposes
  tip or earnings records.

Rewards are idempotent. Every payment has a stable key such as
`upload:<video_id>` or `views:<video_id>:1000`; paid keys are recorded in the
state file before the next polling pass can pay again.

## Wallet Discovery

The daemon checks the video object, agent profile, title, description, and bio
for a wallet field or text such as:

```text
RTC wallet: RTC02811ff5e2bb4bb4b95eee44c5429cd9525496e7
```

Projects can also use a named RTC miner wallet if their payout policy allows
non-address wallet IDs.

## Anti-Abuse Controls

- Dry-run is enabled by default.
- Minimum video length filter blocks extremely short spam uploads.
- Per-creator daily reward caps limit repeated uploads.
- Per-wallet daily reward caps still apply when a BoTTube item does not expose
  a stable creator name.
- View and subscriber milestone payments are one-time per milestone.
- State-file idempotency prevents duplicate payouts after restarts.
- All real transfers use RustChain admin auth and RustChain's pending-transfer
  window instead of directly mutating balances.
- Every transfer reason includes the BoTTube source, video ID, tip ID, or
  milestone so later audits can trace the payment.

## Configuration

Copy the example config and edit reward amounts:

```bash
cp integrations/bottube_bridge.example.json bottube_bridge.json
```

Important fields:

| Field | Purpose |
| --- | --- |
| `bottube_api_base` | BoTTube API root. |
| `rustchain_node_url` | RustChain node URL. |
| `rustchain_from_wallet` | RTC funding wallet. |
| `dry_run` | Keep true until validation is complete. |
| `min_video_length_seconds` | Anti-spam video length threshold. |
| `max_rewards_per_creator_per_day` | Per-creator daily payout cap. |
| `max_rewards_per_wallet_per_day` | Per-wallet daily payout cap. |

## Running Once

```bash
python integrations/bottube_bridge.py \
  --config bottube_bridge.json \
  --once \
  --dry-run
```

The first run should be dry-run only. Review the planned payouts in stdout
before enabling real transfers. Dry-runs do not write paid state, so a test run
cannot accidentally suppress a later real payout.

## Production Run

```bash
export RTC_ADMIN_KEY="..."
export BOTTUBE_API_KEY="..."  # optional, needed for authenticated earnings/tips

python integrations/bottube_bridge.py --config bottube_bridge.json
```

To enable real transfers, set `"dry_run": false` in the config. The bridge will
send:

```http
POST /wallet/transfer
X-Admin-Key: $RTC_ADMIN_KEY

{
  "from_miner": "founder_team_bounty",
  "to_miner": "creator_wallet",
  "amount_rtc": 0.25,
  "reason": "bottube_upload:123"
}
```

RustChain returns a pending transfer ID and transaction hash; confirmation still
follows the node's pending-transfer rules.

## Deployment Notes

A simple systemd timer or long-running service is enough:

```ini
[Service]
WorkingDirectory=/opt/rustchain
Environment=RTC_ADMIN_KEY=replace-me
Environment=BOTTUBE_API_KEY=optional
ExecStart=/usr/bin/python3 integrations/bottube_bridge.py --config bottube_bridge.json
Restart=always
RestartSec=30
```

Store `RTC_ADMIN_KEY` outside the repository. The bridge never prints the key,
and dry-run mode allows maintainers to test the full data path before money can
move.
