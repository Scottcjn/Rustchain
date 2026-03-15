# Comment Moderation Bot

A production-ready GitHub App for detecting and moderating low-quality, spam, and bot-generated issue comments.

## Features

- **FastAPI Webhook Receiver**: High-performance webhook endpoint with signature verification
- **GitHub App Authentication**: JWT-based app authentication with installation token exchange
- **Hybrid Scoring Engine**: Rule-based scoring with optional semantic classifier integration
- **Feature Extraction**: Comprehensive comment analysis (links, mentions, repetition, spam keywords, etc.)
- **Configurable Thresholds**: Fine-tune auto-delete and flag thresholds
- **Whitelist Support**: Exempt trusted users, organizations, repositories, and labeled issues
- **Dry-Run Mode**: Test and tune without actually deleting comments
- **Auto-Delete Mode**: Automatically remove high-risk comments when enabled
- **Audit Logging**: JSONL-formatted logs for compliance and analysis
- **Replay-Safe Delivery**: Idempotency protection against duplicate webhook deliveries

## Architecture

```
┌─────────────────┐     ┌──────────────────────┐     ┌─────────────────────┐
│   GitHub        │────▶│  FastAPI Webhook     │────▶│  Moderation         │
│   Webhooks      │     │  Receiver            │     │  Service            │
└─────────────────┘     └──────────────────────┘     └─────────────────────┘
                                                        │
         ┌──────────────────────────────────────────────┼──────────────────────────────────────────────┐
         │                                              │                                              │
         ▼                                              ▼                                              ▼
┌─────────────────┐                          ┌─────────────────────┐                        ┌─────────────────────┐
│  GitHub Auth    │                          │  Feature Extractor  │                        │  Scoring Engine     │
│  (JWT + Token)  │                          │  (Links, Mentions,  │                        │  (Rules + Semantic) │
│                 │                          │   Repetition, etc.) │                        │                     │
└─────────────────┘                          └─────────────────────┘                        └─────────────────────┘
         │                                              │                                              │
         │                                              ▼                                              │
         │                                      ┌─────────────────────┐                                │
         │                                      │  Whitelist Checker  │                                │
         │                                      │  (Users, Orgs,      │                                │
         │                                      │   Repos, Labels)    │                                │
         │                                      └─────────────────────┘                                │
         │                                              │                                              │
         ▼                                              ▼                                              ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                           Decision & Action                                             │
│                              (Allow / Flag / Delete with Audit Logging)                                 │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

## Installation

### Prerequisites

- Python 3.10+
- GitHub App credentials (see Setup below)

### Install Dependencies

```bash
cd tools/comment-moderation-bot

# Install with dev dependencies
pip install -e ".[dev]"

# Or just production dependencies
pip install -e .
```

## GitHub App Setup

### 1. Create a GitHub App

1. Go to **Settings** → **Developer settings** → **GitHub Apps** → **New GitHub App**
2. Fill in the app details:
   - **Name**: `Comment Moderation Bot` (or your choice)
   - **Homepage URL**: Your service URL (e.g., `https://your-domain.com`)
   - **Webhook URL**: `https://your-domain.com/webhook`
   - **Webhook secret**: Generate a random secret (save this!)

### 2. Configure Permissions

Under **Permissions & Webhooks**, set the following:

#### Repository Permissions

| Permission | Access | Reason |
|------------|--------|--------|
| Issues | Read & Write | Read issues, delete comments |
| Metadata | Read-only | Required for all apps |

#### Organization Permissions (if applicable)

| Permission | Access | Reason |
|------------|--------|--------|
| Members | Read-only | Check org membership for whitelist |

### 3. Subscribe to Events

Enable these webhook events:

- ✅ **Issues**
- ✅ **Issue comment**

### 4. Generate Private Key

1. Click **Generate a private key** under **Private keys**
2. Save the `.pem` file securely

### 5. Install the App

1. Go to your app's main page
2. Click **Install App**
3. Select the repositories to install on
4. Note the **Installation ID** (visible in the URL after installation)

## Configuration

Copy the example config and fill in your values:

```bash
cp .env.example .env
```

### Required Settings

```ini
# GitHub App credentials
GITHUB_APP_APP_ID=12345
GITHUB_APP_CLIENT_ID=Iv1.abc123
GITHUB_APP_CLIENT_SECRET=your_client_secret
GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"
GITHUB_APP_WEBHOOK_SECRET=your_webhook_secret

# Operational mode
MODERATION_BOT_DRY_RUN=true  # Start with true!
MODERATION_BOT_ENABLED=true
```

### Tuning Thresholds

Start with conservative thresholds and adjust based on audit logs:

```ini
# Higher = more aggressive deletion
SCORE_AUTO_DELETE_THRESHOLD=0.85
SCORE_FLAG_THRESHOLD=0.60
```

### Whitelist Configuration

```ini
# Trusted users (comma-separated)
WHITELIST_TRUSTED_USERS=octocat,dependabot[bot]

# Trusted organizations
WHITELIST_TRUSTED_ORGS=myorg,trusted-org

# Exempt repositories
WHITELIST_EXEMPT_REPOS=myorg/docs,myorg/examples

# Exempt issue labels
WHITELIST_EXEMPT_LABELS=bug,security,critical
```

## Running Locally

### Development Server

```bash
# With auto-reload
uvicorn src.webhook:app --reload --host 0.0.0.0 --port 8000

# Or using the module
python -m uvicorn src.webhook:app --reload
```

### Production Server

```bash
# With multiple workers
uvicorn src.webhook:app --host 0.0.0.0 --port 8000 --workers 4

# Or with gunicorn
gunicorn src.webhook:app -w 4 -k uvicorn.workers.UvicornWorker
```

### Docker (Optional)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

COPY src/ ./src/

EXPOSE 8000

CMD ["uvicorn", "src.webhook:app", "--host", "0.0.0.0", "--port", "8000"]
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with service stats |
| `/ready` | GET | Readiness probe |
| `/webhook` | POST | GitHub webhook receiver |
| `/stats` | GET | Service statistics |

## Testing Webhooks Locally

### Using ngrok

```bash
# Install ngrok
brew install ngrok

# Start your server
uvicorn src.webhook:app --reload

# In another terminal, expose it
ngrok http 8000

# Use the ngrok URL as your webhook URL in GitHub App settings
```

### Using GitHub's Test Delivery

1. Go to your GitHub App settings
2. Under **Advanced**, find a recent delivery
3. Click **Redeliver** to test

## Audit Logs

Logs are stored in JSONL format in the configured log directory:

```bash
# View today's logs
cat logs/moderation_audit_$(date +%Y-%m-%d).jsonl | jq .

# Filter by action
cat logs/*.jsonl | jq 'select(.action == "deleted")'

# Filter by risk score
cat logs/*.jsonl | jq 'select(.risk_score > 0.8)'
```

### Log Entry Example

```json
{
  "timestamp": "2024-01-15T10:30:00.000000+00:00",
  "action": "deleted",
  "comment_id": 1234567890,
  "repo": "myorg/myrepo",
  "issue_number": 42,
  "risk_score": 0.92,
  "author": "spammer123",
  "decision": "auto",
  "dry_run": false,
  "delivery_id": "abc123-def456",
  "score_breakdown": {
    "spam_keywords": 0.8,
    "link_ratio": 0.6,
    "length_penalty": 0.1,
    "repetition": 0.2,
    "mention_spam": 0.3,
    "semantic": 0.0,
    "factors": [
      "spam_keywords (3 matches: crypto, giveaway, click here)",
      "link_ratio (5 links, 8.5/100 chars)",
      "suspicious_domains (bit.ly)"
    ]
  }
}
```

## Scoring Rules

The hybrid scoring engine evaluates comments based on:

| Factor | Weight | Description |
|--------|--------|-------------|
| Spam Keywords | 25% | Detection of common spam phrases |
| Link Ratio | 20% | Density of links in comment |
| Length Penalty | 10% | Very short or very long comments |
| Repetition | 20% | Character/word repetition, excessive caps |
| Mention Spam | 15% | Excessive @mentions |
| Semantic | 10% | ML-based classification (optional) |

### Spam Keywords

The detector looks for patterns like:
- Crypto/investment spam ("bitcoin", "giveaway", "earn money")
- Marketing spam ("seo service", "backlink", "hire me")
- Generic spam ("click here", "dm me", "telegram")

### Link Analysis

- High link density (>5 links per 100 chars)
- Suspicious domains (URL shorteners, ad networks)
- Multiple unique domains

## Troubleshooting

### Webhook Not Receiving Events

1. Check GitHub App webhook URL is correct
2. Verify webhook secret matches
3. Check server is accessible (ngrok for local dev)
4. Review GitHub's delivery logs in App settings

### Signature Verification Failed

1. Ensure `GITHUB_APP_WEBHOOK_SECRET` is set correctly
2. Check for trailing whitespace in the secret
3. Verify the secret matches GitHub App settings exactly

### Comments Not Being Deleted

1. Ensure `MODERATION_BOT_DRY_RUN=false`
2. Check risk score meets `SCORE_AUTO_DELETE_THRESHOLD`
3. Verify app has Issues write permission
4. Check audit logs for errors

### False Positives

1. Add users to `WHITELIST_TRUSTED_USERS`
2. Add labels to `WHITELIST_EXEMPT_LABELS`
3. Increase `SCORE_AUTO_DELETE_THRESHOLD`
4. Review audit logs to understand scoring

## Security Considerations

- **Private Key**: Store securely, never commit to version control
- **Webhook Secret**: Use a strong random value
- **Client Secret**: Treat as sensitive credential
- **Audit Logs**: May contain sensitive data, secure appropriately

## License

MIT License - See LICENSE file for details.
