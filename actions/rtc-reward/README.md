# RTC Reward Action

Award RTC tokens to contributors when their PR is merged. Any open source project can add this GitHub Action to automatically reward contributors with RustChain crypto.

## Features

- **Automatic rewards**: Triggers on PR merge, no manual intervention
- **Configurable amount**: Set custom RTC reward per PR
- **PR comments**: Posts a thank-you comment with transaction details
- **Secure**: Wallet stored as GitHub Secret, never exposed in logs
- **GitHub Actions summary**: Rich job summary with reward details

## Usage

```yaml
# .github/workflows/rtc-reward.yml
name: RTC Reward

on:
  pull_request:
    types: [closed]

jobs:
  reward:
    if: github.event.pull_request.merged == true
    runs-on: ubuntu-latest
    steps:
      - name: Award RTC
        uses: Scottcjn/Rustchain/actions/rtc-reward@main
        with:
          rtc-wallet: ${{ secrets.RTC_WALLET }}
          amount: '1'
          rpc-url: 'https://rpc.rustchain.org'
          comment-on-pr: 'true'
```

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `rtc-wallet` | ✅ | — | Wallet address for sending RTC rewards |
| `amount` | ❌ | `1` | Amount of RTC to award per merged PR |
| `rpc-url` | ❌ | `https://rpc.rustchain.org` | RustChain RPC endpoint |
| `github-token` | ❌ | `${{ github.token }}` | Token for posting PR comments |
| `comment-on-pr` | ❌ | `true` | Post a reward comment on the merged PR |

## Outputs

| Output | Description |
|--------|-------------|
| `tx-hash` | Transaction hash of the RTC transfer |
| `status` | Reward status (success/failed/skipped) |

## Setup

1. Add your RTC wallet address as a repository secret: `RTC_WALLET`
2. Copy the workflow YAML above into `.github/workflows/rtc-reward.yml`
3. Merge a PR — the action runs automatically!

## Security

- Wallet address is stored as a GitHub Secret (never in code)
- Transfer payload is signed with SHA-256 for integrity
- Only triggers on merged PRs (not closed/rejected)
- Nonce prevents replay attacks

## License

MIT
