# rustchain-tip-bot

GitHub bot for issuing RTC tips via `/tip` commands in issue and PR comments.

---

## How It Works

A maintainer posts a comment containing:

```
/tip @username <amount> RTC
```

The bot (triggered by GitHub Actions) validates the command, records it to a
persistent state file, posts a confirmation comment, and commits the updated
state back to the repo. In v1 (log-only mode) the maintainer manually processes
the actual RTC transfer using the logged data.

---

## Command Format

```
/tip @username <amount> RTC
```

| Field | Rules |
|-------|-------|
| `@username` | Valid GitHub username (1–39 chars, letters/numbers/hyphens) |
| `<amount>` | Positive number, min 1 RTC, max 10000 RTC |
| `RTC` | Must be the literal token symbol (case-insensitive) |

The command can appear anywhere in a comment body (inline or on its own line).

**Valid examples:**
```
/tip @contributor 50 RTC
Great fix! /tip @alice 25 RTC for the patch.
/tip @bob 12.5 RTC
```

**Rejected examples:**
```
/tip alice 50 RTC         # missing @ sign
/tip @alice RTC           # missing amount
/tip @alice 50 ETH        # wrong token
/tip @alice 0 RTC         # zero amount
/tip @alice 99999 RTC     # exceeds maximum
```

---

## Setup

### 1. Add this repo as a submodule (or copy files into your repo)

```bash
# Option A: standalone repo
git clone https://github.com/mtarcure/rustchain-tip-bot
cp -r rustchain-tip-bot/.github/workflows/tip-bot.yml your-repo/.github/workflows/
cp rustchain-tip-bot/{tip_bot.py,auth.py,state.py,config.yml,requirements.txt} your-repo/

# Option B: reference directly via workflow
# Point the workflow's checkout step to this repo
```

### 2. Initialize the state file

```bash
echo '{"processed_comment_ids":[],"tip_log":[],"version":1}' > tip_state.json
git add tip_state.json
git commit -m "chore: initialize tip bot state"
```

### 3. Configure maintainers

Edit `config.yml` and add the GitHub usernames that are allowed to issue tips:

```yaml
tip_bot:
  maintainers:
    - Scottcjn
    - your-username
```

### 4. Set GitHub repository secrets

Go to **Settings → Secrets and variables → Actions** and add:

| Secret | Required | Description |
|--------|----------|-------------|
| `TIP_BOT_WEBHOOK_SECRET` | Optional | HMAC secret for webhook signature verification (external webhook deployments only — **not needed for GitHub Actions**). Generate with: `openssl rand -hex 32` |
| `RUSTCHAIN_NODE_URL` | Optional | Override the default RustChain node URL |
| `WALLET_ADDRESS` | v2 only | Your RustChain wallet address (for auto-payout) |
| `WALLET_PRIVATE_KEY` | v2 only | Wallet private key — **never commit this** |

The `GITHUB_TOKEN` secret is provided automatically by GitHub Actions.

### 5. Grant the Action write access

In **Settings → Actions → General → Workflow permissions**, select
**Read and write permissions** (needed so the bot can post comments and commit
the state file).

---

## Payout Workflow (v1 — Log Only)

In v1, the bot **does not send RTC automatically**. It logs each tip to
`tip_state.json` with status `pending_payout`. The maintainer processes payouts
manually:

1. After the bot posts a confirmation, check `tip_state.json` for pending tips:

```bash
python3 - <<'EOF'
import json
with open("tip_state.json") as f:
    state = json.load(f)
pending = [t for t in state["tip_log"] if t["status"] == "pending_payout"]
for t in pending:
    print(f"  {t['timestamp'][:10]}  {t['sender']} → @{t['recipient']}  {t['amount']} {t['token']}")
    print(f"    Context: {t['context_url']}")
EOF
```

2. Send the RTC to the recipient's wallet via the RustChain interface.

3. Mark as paid (update `tip_state.json` manually or run the helper):

```bash
python3 - <<'EOF'
import json
TIP_ID = "org/repo/COMMENT_ID"
TX_REF = "your-tx-hash-or-ref"

with open("tip_state.json") as f:
    state = json.load(f)
for tip in state["tip_log"]:
    if tip["id"] == TIP_ID:
        tip["status"] = "paid"
        tip["tx_ref"] = TX_REF
with open("tip_state.json", "w") as f:
    json.dump(state, f, indent=2)
print("Marked as paid.")
EOF
git add tip_state.json && git commit -m "chore: mark tip paid [skip ci]"
```

---

## Wallet / Payout Configuration

The bot is designed to work with the RustChain ecosystem:

- **Node API:** `https://bulbous-bouffant.metalseed.net` (default, override via `RUSTCHAIN_NODE_URL`)
- **Balance check:** `GET /wallet/balance?miner_id=<wallet_id>`
- **Miners list:** `GET /api/miners`

> **SSL note:** The default node uses a self-signed certificate. The bot uses
> `verify=False` for node queries (consistent with existing RustChain tooling).
> Do **not** disable SSL verification for the GitHub API calls.

For auto-payout (v2), you will need:
- `WALLET_ADDRESS` — the maintainer/project wallet address that funds tips
- `WALLET_PRIVATE_KEY` — kept in GitHub Secrets, never in code or state files

---

## Security

### Webhook Signature Verification

When `TIP_BOT_WEBHOOK_SECRET` is set **and** an `HTTP_X_HUB_SIGNATURE_256` header
is present, the bot verifies the HMAC-SHA256 signature before processing. This
prevents forged webhooks from triggering tip commands.

**Important:** This is only relevant for **external webhook deployments** (e.g.,
running the bot as a standalone server). When using **GitHub Actions**, the payload
comes from GitHub's own infrastructure via `GITHUB_EVENT_PATH` — there is no HTTP
signature header. **Do not set `TIP_BOT_WEBHOOK_SECRET` for GitHub Actions** as
it is unnecessary and has no effect.

For external webhook deployments, configure the same secret in both:
- Environment variable: `WEBHOOK_SECRET`
- GitHub webhook settings → Secret

### Maintainer Allowlist

Only users listed in `config.yml` under `maintainers` can issue `/tip` commands.
All other users receive an unauthorized error comment. The check is
case-insensitive.

### Idempotency

Each comment is identified by its GitHub comment ID. The bot records processed
comment IDs in `tip_state.json`. If the same comment ID is seen again (e.g., a
workflow retry), the tip is not recorded twice and a duplicate notice is posted.

### Rate Limiting

Each maintainer is limited to 20 tip commands per hour (configurable in
`config.yml`). This prevents accidental spam.

---

## Configuration Reference (`config.yml`)

```yaml
tip_bot:
  maintainers:            # GitHub usernames allowed to issue /tip
    - Scottcjn

  token_symbol: RTC       # Token symbol (case-insensitive in commands)
  min_amount: 1           # Minimum tip amount
  max_amount: 10000       # Maximum tip amount

  rate_limit:
    max_per_hour: 20      # Max tips per maintainer per hour

  rustchain_node_url: "https://bulbous-bouffant.metalseed.net"
  payout_mode: log_only   # "log_only" (v1) or "auto" (v2, future)
  state_file: "tip_state.json"
```

---

## Running Tests

```bash
pip install -r requirements.txt
pytest test_tip_bot.py -v
```

60 tests covering: command parsing, validation, authorization, idempotency,
state persistence, end-to-end event processing, webhook verification,
rate limiting, and comment formatting.

---

## File Structure

```
.github/workflows/tip-bot.yml   GitHub Action (triggers on issue_comment)
tip_bot.py                      Main bot — parsing, validation, event loop
auth.py                         Webhook verification + maintainer allowlist
state.py                        JSON state persistence + idempotency
config.yml                      Bot configuration
tip_state.json                  Live tip log (committed by the bot)
test_tip_bot.py                 Full test suite (60 tests)
requirements.txt                Python dependencies
README.md                       This file
```
