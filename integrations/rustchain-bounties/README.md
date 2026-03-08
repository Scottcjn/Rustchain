# RustChain GitHub Tip Bot

A practical GitHub integration for managing RTC bounty payouts via `/tip` commands in issue comments.

## Features

- **Simple Tip Commands**: Send RTC tips with `/tip @username <amount> RTC`
- **Bounty Tracking**: Track bounty claims and payouts
- **Automated Responses**: Bot responds to tip commands with confirmation
- **State Persistence**: All tips are recorded in a JSON state file
- **Dry Run Mode**: Test without actual processing
- **Webhook Integration**: GitHub Actions workflow for automatic processing

## Quick Start

### 1. Install Dependencies

```bash
cd integrations/rustchain-bounties
pip install -r requirements.txt
```

### 2. Configure Environment

Set the following environment variables:

```bash
export GITHUB_TOKEN="your_github_token"
export TIP_BOT_WALLET="RTC1d48d848a5aa5ecf2c5f01aa5fb64837daaf2f35"
export TIP_BOT_ADMINS="admin1,admin2"  # Optional
```

### 3. Test the Bot

```bash
# Test command parsing
python tip_bot.py --test-parse "/tip @contributor 50 RTC"

# Check status
python tip_bot.py --status

# Run in dry-run mode
python tip_bot.py --dry-run --status
```

## Usage

### Tip Commands

Post a comment on any issue with:

```
/tip @username 50 RTC
```

Or with claim syntax:

```
/tip claim @username 100 RTC
```

### Other Commands

```
/tip status    - Show bot statistics
/tip help      - Show help message
```

### Examples

```
# Tip a contributor
/tip @scottcjn 75 RTC

# Check status
/tip status

# Get help
/tip help
```

## GitHub Actions Integration

The tip bot automatically processes comments via the GitHub Actions workflow:

1. User posts `/tip` comment on an issue
2. Workflow triggers on `issue_comment` event
3. Bot processes the command and posts a response

### Workflow Configuration

The workflow is defined in `.github/workflows/tip-bot.yml`.

### Required Secrets

Add these secrets to your repository:

| Secret | Description | Example |
|--------|-------------|---------|
| `TIP_BOT_WALLET` | Payout wallet address | `RTC1d48d848a5aa5ecf2c5f01aa5fb64837daaf2f35` |
| `TIP_BOT_ADMINS` | Comma-separated admin list | `admin1,admin2` |
| `TIP_BOT_DRY_RUN` | Enable dry-run mode | `true` or `false` |

## Bounty Tracker

The bounty tracker manages bounty issues and claims:

```bash
# Scan for bounty issues
python bounty_tracker.py --token $GITHUB_TOKEN --scan

# Show summary
python bounty_tracker.py --token $GITHUB_TOKEN --summary

# Show pending claims
python bounty_tracker.py --token $GITHUB_TOKEN --pending
```

## State Files

The bot maintains two state files:

- `bounty_state.json`: Tip transaction records
- `bounty_tracker_state.json`: Bounty issue tracking

## Testing

Run the test suite:

```bash
cd integrations/rustchain-bounties
pytest test_tip_bot.py -v
```

## Payout Wallet

**Default Payout Wallet**: `RTC1d48d848a5aa5ecf2c5f01aa5fb64837daaf2f35`

This is the split createkr-wallet address for RustChain bounty distributions.

## Security

- Webhook signatures are verified using HMAC-SHA256
- Only issue authors and collaborators can issue tips
- Tip amounts are capped at 1000 RTC per transaction
- Admin override available via `TIP_BOT_ADMINS`

## Troubleshooting

### Bot not responding to commands

1. Check that the workflow is enabled in repository settings
2. Verify `GITHUB_TOKEN` has write permissions for issues
3. Check workflow runs in Actions tab

### Tips not being recorded

1. Ensure state file directory is writable
2. Check for JSON parsing errors in state file
3. Run in dry-run mode to test without persistence

## License

MIT License - See main RustChain repository for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

---

**Related**: [RustChain Bounties](../../bounties/dev_bounties.json) | [Bounty Claim Template](../../.github/ISSUE_TEMPLATE/bounty-claim.yml)
