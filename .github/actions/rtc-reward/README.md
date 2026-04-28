# rtc-reward-action

**Bounty #2864 — 20 RTC**
**Wallet:** `RTC52d4fe5e93bda2349cb848ee33ffebeca9b2f68f`

Reusable GitHub Action that automatically awards RTC tokens when a PR is merged.

---

## TL;DR

```yaml
# .github/workflows/rtc-reward.yml
on:
  pull_request:
    types: [closed]

jobs:
  reward:
    if: github.event.pull_request.merged == true
    runs-on: ubuntu-latest
    steps:
      - uses: universe7creator/rtc-reward-action@v1
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          node-url: https://50.28.86.131
          amount: 5
          wallet-from: project-treasury
          cooldowns-minutes: 60
```

---

## Setup

### 1. Add the workflow

```bash
mkdir -p .github/workflows
```

```yaml
# .github/workflows/rtc-reward.yml
on:
  pull_request:
    types: [closed]

jobs:
  reward:
    if: github.event.pull_request.merged == true
    runs-on: ubuntu-latest
    steps:
      - uses: universe7creator/rtc-reward-action@v1
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          amount: 5
```

### 2. Fund the reward wallet

Transfer RTC to `wallet-from`. The default `wallet-from` is the contributor's GitHub username (must be registered on-chain).

### 3. Contributor registration (optional)

Contributors add one line anywhere in their PR body:

```
Wallet: <miner_id>
```

Supported formats:
```
Wallet: my-miner-id
wallet: RTCxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
/wallet my-miner-id
/register my-miner-id
```

If no wallet is found in the PR body, the action looks up the contributor's GitHub username in the on-chain registry.

---

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `github-token` | ✅ | `${{ github.token }}` | GitHub token for API access |
| `node-url` | | `https://50.28.86.131` | RustChain node RPC URL |
| `amount` | | `5` | RTC amount per merged PR |
| `wallet-from` | | (contributor username) | Sender wallet miner_id |
| `admin-key` | | — | Admin key for RPC transfer (WARNING: avoid in public repos) |
| `dry-run` | | `false` | Simulate without making real transfers |
| `cooldowns-minutes` | | `60` | Anti-abuse cooldown between same-wallet transfers |
| `registry-url` | | `{node-url}/wallet/registry` | Registry API for wallet lookups |

---

## Workflow Examples

### Minimal (no admin key needed)

```yaml
on:
  pull_request:
    types: [closed]

jobs:
  reward:
    if: github.event.pull_request.merged == true
    runs-on: ubuntu-latest
    steps:
      - uses: universe7creator/rtc-reward-action@v1
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

### With treasury wallet + 10 RTC + 24h cooldown

```yaml
on:
  pull_request:
    types: [closed]

jobs:
  reward:
    if: github.event.pull_request.merged == true
    runs-on: ubuntu-latest
    steps:
      - uses: universe7creator/rtc-reward-action@v1
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          node-url: https://50.28.86.131
          amount: 10
          wallet-from: my-project-treasury
          cooldowns-minutes: 1440
```

### Dry-run (for testing)

```yaml
jobs:
  reward:
    if: github.event.pull_request.merged == true
    runs-on: ubuntu-latest
    steps:
      - uses: universe7creator/rtc-reward-action@v1
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          amount: 5
          dry-run: true
```

---

## Security Notes

- **Never hard-code the admin key** in the workflow file. Use `wallet-from` with a pre-funded, pre-registered wallet instead.
- The admin key input exists for self-hosted nodes that require it — but for `https://50.28.86.131`, a registered wallet name is sufficient.
- Set `dry-run: true` to validate the workflow before going live.
- The cooldown artifact is stored with 1-day retention and is scoped to the same repository.

---

## Deployment

1. Fork this repo or copy `tip.js` and `action.yml` into your project.
2. Tag a release: `git tag v1 && git push --tags`
3. Reference via `@v1` or `@v1.0.0` in your workflow.
4. Optionally submit to GitHub Marketplace for discoverability.

---

## Proof of Work

- `action.yml` — action manifest with all required inputs
- `tip.js` — full Node.js action implementing the reward logic
- `README.md` — this file with setup + security notes
- Live test PR: submit a PR with `Wallet: universe7creator` to confirm dry-run output
