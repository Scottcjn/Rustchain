# GitHub Tip Bot for RTC

A GitHub Action that monitors comments for `/tip` commands and processes RTC tips directly in GitHub.

## Features

### Required (25 RTC)
- `/tip @user AMOUNT RTC [memo]` - Send RTC to a user
- Validates sender is repo admin/maintainer
- Validates recipient has registered wallet
- Queues transfer via RustChain API
- Posts confirmation comment

### Bonus (40 RTC)
- `/balance` - Check your RTC balance
- `/leaderboard` - Top tipped contributors
- `/register WALLET_NAME` - Register your wallet
- Daily digest of all tips

## Usage

1. Add this workflow to `.github/workflows/tip-bot.yml`:

```yaml
name: RTC Tip Bot
on:
  issue_comment:
    types: [created]
  pull_request_review_comment:
    types: [created]

jobs:
  tip-bot:
    runs-on: ubuntu-latest
    steps:
      - uses: Scottcjn/github-tip-bot@main
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          rpc-url: ${{ secrets.RUSTCHAIN_RPC_URL }}
          admin-key: ${{ secrets.TIP_BOT_ADMIN_KEY }}
```

2. Set required secrets in your repo settings

## Commands

| Command | Description |
|---------|-------------|
| `/tip @user 5 RTC Great work!` | Tip 5 RTC to user |
| `/balance` | Check your RTC balance |
| `/register your-wallet-address` | Register your wallet |
| `/leaderboard` | Show top tippers |

## Example Response

```
✅ Queued: 5 RTC → noxxxxybot
From: Scottcjn | Memo: Great work!
Status: Pending (confirms in 24h)
```
