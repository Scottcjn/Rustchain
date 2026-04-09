# RTC Auto-Bounty

A reusable GitHub Action that automatically awards RustChain (RTC) to contributors when their pull request is merged.

## Features

- **Automatic RTC awards** on PR merge — no manual intervention needed
- **Configurable amount** per merge, with per-PR override via `bounty:` directive in the PR body
- **Flexible wallet resolution** — reads from `wallet:` directive in PR body, `.rtc-wallet` file, or falls back to PR author username
- **Dry-run mode** — test the action safely without making real transfers
- **Duplicate prevention** — detects already-awarded PRs via comment markers
- **PR comment confirmation** — posts a formatted table with transfer details
- **Safety caps** — configurable maximum award amount to prevent accidental large transfers
- **Publishable to GitHub Marketplace** — follows composite action conventions

## Usage

### Basic

Add this step to your merge workflow:

```yaml
- name: Award RTC bounty
  uses: ./.github/actions/rtc-auto-bounty
  with:
    rtc-amount: '75'
    rtc-vps-host: ${{ secrets.RTC_VPS_HOST }}
    rtc-admin-key: ${{ secrets.RTC_ADMIN_KEY }}
```

### Full example workflow

```yaml
name: RTC Auto-Bounty

on:
  pull_request:
    types: [closed]

permissions:
  pull-requests: write
  contents: read

jobs:
  award-bounty:
    if: github.event.pull_request.merged == true
    runs-on: ubuntu-latest
    timeout-minutes: 5

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Award RTC bounty
        uses: ./.github/actions/rtc-auto-bounty
        with:
          # Default amount per merge (can be overridden per-PR)
          rtc-amount: '50'
          # RustChain node VPS host
          rtc-vps-host: ${{ secrets.RTC_VPS_HOST }}
          # Admin key for the /wallet/transfer endpoint
          rtc-admin-key: ${{ secrets.RTC_ADMIN_KEY }}
          # Source wallet (default: founder_community)
          from-wallet: 'founder_community'
          # Safety cap — transfers above this will fail
          max-amount: '10000'
          # Set to "true" to test without real transfers
          dry-run: 'false'
          # Post a confirmation comment on the PR
          post-comment: 'true'
          # GitHub token (auto-provided)
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

### Reusable workflow (for Marketplace publishing)

If you publish this action to the Marketplace, consumers can use it like:

```yaml
- name: Award RTC
  uses: Scottcjn/RustChain/.github/actions/rtc-auto-bounty@main
  with:
    rtc-amount: '100'
    rtc-vps-host: ${{ secrets.RTC_VPS_HOST }}
    rtc-admin-key: ${{ secrets.RTC_ADMIN_KEY }}
```

## How it works

1. **Merge guard** — Only runs when `github.event.pull_request.merged == true`
2. **Duplicate check** — Fetches existing PR comments and looks for `RTC-AutoBounty-Awarded` marker
3. **Wallet resolution** (in priority order):
   - `wallet: <address>` or `.rtc-wallet: <address>` directive in the PR body
   - `.rtc-wallet` file at the repository root
   - Falls back to the PR author's GitHub username
4. **Amount determination**:
   - Uses `rtc-amount` input as the default
   - Checks for `bounty: <amount> RTC` directive in the PR body to override
   - Validates against `max-amount` safety cap
5. **Transfer** — Calls `POST /wallet/transfer` on the RustChain VPS with `X-Admin-Key` auth
6. **Confirmation** — Posts a formatted comment on the PR with transfer details

## Inputs

| Input | Description | Default | Required |
|-------|-------------|---------|----------|
| `rtc-amount` | Default RTC amount per merge | `50` | No |
| `rtc-vps-host` | RustChain VPS host (IP or hostname) | — | Yes* |
| `rtc-admin-key` | Admin key for `/wallet/transfer` | — | Yes* |
| `from-wallet` | Source wallet for the transfer | `founder_community` | No |
| `dry-run` | Simulate without calling the API | `false` | No |
| `post-comment` | Post a confirmation comment on the PR | `true` | No |
| `github-token` | GitHub token for API access | `${{ github.token }}` | No |
| `repo-path` | Path to the checked-out repository | `.` | No |
| `max-amount` | Safety cap for transfer amount | `10000` | No |

\* Not required when `dry-run` is `true`.

## Outputs

| Output | Description |
|--------|-------------|
| `awarded` | `true` if an award was made, `false` otherwise |
| `amount` | RTC amount that was (or would be) awarded |
| `recipient_wallet` | Wallet address that received the award |
| `tx_hash` | Transaction hash from the transfer (empty in dry-run) |
| `pending_id` | Pending transfer ID from the node (empty in dry-run) |
| `skip-reason` | Reason the award was skipped (empty if not skipped) |

## Wallet specification

Contributors can specify their wallet in two ways:

### 1. PR body directive

Add a line anywhere in the PR body:

```
wallet: RTCxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Or using the `.rtc-wallet` alias:

```
.rtc-wallet: my-github-username
```

### 2. `.rtc-wallet` file

Create a file named `.rtc-wallet` at the repository root containing the wallet address:

```
RTCxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Lines starting with `#` are treated as comments and skipped.

## Per-PR bounty override

Repo owners can specify a custom amount for a specific PR by adding a directive in the PR body:

```
bounty: 200 RTC
```

This overrides the default `rtc-amount` input for that PR only.

## Dry-run mode

Set `dry-run: 'true'` to test the action without making real transfers. The action will:

- Resolve the wallet address
- Determine the award amount
- Log what it *would* do
- Post a comment marked as "(Dry-Run)"
- Exit successfully

This is useful for validating configuration and wallet resolution before enabling live transfers.

## Security considerations

- **Admin key** — The `rtc-admin-key` secret grants access to the admin transfer endpoint. Never expose it in logs or PR comments.
- **Safety cap** — The `max-amount` input prevents accidental large transfers. Set it conservatively.
- **Merge-only** — The action only runs when a PR is actually merged, not just closed.
- **Idempotent** — Duplicate runs on the same PR are detected via the comment marker.

## Testing

```bash
cd .github/actions/rtc-auto-bounty
python -m pytest test_award_rtc.py -v
# or
python test_award_rtc.py
```

## Comparison to shell-only approaches

This implementation is deliberately more robust than a quick shell script:

- **Structured wallet resolution** with regex-based parsing (not brittle `grep`)
- **Pagination** when fetching PR comments (handles PRs with 100+ comments)
- **Proper error handling** with distinct paths for network errors, HTTP errors, and API errors
- **Config validation** before attempting any external calls
- **Dry-run mode** built in, not bolted on
- **GitHub Actions outputs** for downstream step consumption
- **Unit tested** — not just smoke-tested
- **Duplicate prevention** via comment marker scanning
- **Safety caps** on transfer amounts
