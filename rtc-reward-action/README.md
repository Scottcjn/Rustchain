# RustChain RTC Reward Action

Automatically awards RTC tokens to contributors when a pull request is merged into your repository.

## 🚀 How it Works

This action listens for `pull_request` events. When a PR is merged, it:
1. Searches the PR body for a wallet identifier (e.g., `Wallet: my-wallet-name`).
2. Falls back to the GitHub username of the PR author if no wallet is specified.
3. Calls the RustChain node API to transfer the specified amount of RTC from a project fund.
4. Posts a confirmation comment on the PR.

## 🛠 Usage

Add this workflow to your repository at `.github/workflows/rtc-reward.yml`:

```yaml
name: RTC Rewards
on:
  pull_request:
    types: [closed]

jobs:
  reward:
    if: github.event.pull_request.merged == true
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: nkar123412-hub/rtc-reward-action@v1
        with:
          node-url: 'https://rustchain.org'
          amount: '5'
          wallet-from: 'project-fund'
          admin-key: ${{ secrets.RTC_ADMIN_KEY }}
          dry-run: 'false'
```

## ⚙️ Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `node-url` | RustChain node URL | Yes | `https://rustchain.org` |
| `amount` | RTC amount to reward | Yes | `5` |
| `wallet-from` | Wallet to send funds from | Yes | - |
| `admin-key` | Admin API key for the node | Yes | - |
| `dry-run` | Simulate transfer (no real tokens sent) | No | `false` |
| `wallet-field` | Field name to look for in PR body | No | `Wallet` |

## 📋 Requirements

- The `RTC_ADMIN_KEY` must be stored in your repository's **GitHub Secrets**.
- The `wallet-from` must be a valid RustChain wallet with sufficient funds.

## 📄 License

MIT
