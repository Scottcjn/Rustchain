# RustChain Testnet Faucet — GitHub OAuth Enhancement

> Implementation of [Bounty #751](https://github.com/Scottcjn/rustchain-bounties/issues/751)  
> **Reward: +5 RTC** for GitHub OAuth verification feature

## Overview

This enhancement adds **GitHub OAuth authentication** to the RustChain testnet faucet, enabling tiered rate limits based on user authentication level:

| Auth Level | Rate Limit | Requirements |
|------------|-----------|--------------|
| 🔓 Anonymous | 0.5 RTC / 24h | None |
| ✅ GitHub Auth | 1.0 RTC / 24h | GitHub account |
| ⭐ GitHub Veteran | 2.0 RTC / 24h | Account > 1 year old |

## Features

- **GitHub OAuth 2.0 Flow**: Secure authorization via GitHub
- **Tiered Rate Limiting**: IP-based, GitHub auth, and veteran tiers
- **CSRF Protection**: One-time state tokens tied to IP address
- **SQLite Backend**: Persistent tracking of drips and OAuth sessions
- **REST API + Web UI**: Full programmatic access with HTML interface
- **Session Management**: Flask sessions for authenticated users

## Files Added

| File | Description | Size |
|------|-------------|------|
| `faucet_github_oauth.py` | Main Flask application with OAuth | ~23KB |
| `test_faucet_github_oauth.py` | Comprehensive test suite (21 tests) | ~7KB |
| `FAUCET_GITHUB_OAUTH_README.md` | This documentation | — |

## Quick Start

### Prerequisites

```bash
pip install flask requests pyyaml pycryptodome
```

### Environment Variables

```bash
export GITHUB_CLIENT_ID=your_github_app_client_id
export GITHUB_CLIENT_SECRET=your_github_app_client_secret
export FAUCET_SECRET_KEY=your_session_secret_key
export FAUCET_PORT=8090
```

### Run the Faucet

```bash
python faucet_github_oauth.py
```

Visit: `http://localhost:8090/faucet`

## API Endpoints

### Web UI
- `GET /faucet` — Main faucet interface with GitHub login button
- `GET /faucet/oauth/start` — Initiate GitHub OAuth flow
- `GET /faucet/oauth/callback` — OAuth callback (handled automatically)

### API
- `POST /faucet/drip` — Request test tokens
  ```bash
  curl -X POST http://localhost:8090/faucet/drip \
    -H "Content-Type: application/json" \
    -d '{"wallet":"RTC..."}'
  ```
- `GET /faucet/status` — Check rate limit status
- `GET /health` — Health check

### Example: Authenticated Drip

After logging in via GitHub on the web UI, the session automatically increases your rate limit. For API usage:

```bash
curl -X POST http://localhost:8090/faucet/drip \
  -H "Content-Type: application/json" \
  -H "X-GitHub-User: yourgithub" \
  -d '{"wallet":"RTC...","github_user":"yourgithub"}'
```

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Client    │────→│ Flask App    │────→│  SQLite DB  │
│  (Browser)  │     │ faucet.py    │     │ faucet.db   │
└─────────────┘     └──────────────┘     └─────────────┘
                           │
                           ↓
                    ┌──────────────┐
                    │ GitHub OAuth │
                    │  API Server  │
                    └──────────────┘
```

## Security Features

1. **CSRF Protection**: OAuth state tokens are one-time use and IP-bound
2. **Rate Limiting**: Multi-tier with IP and GitHub account tracking
3. **Session Security**: Signed Flask sessions with configurable secret
4. **Input Validation**: Strict wallet address format validation
5. **Atomic Operations**: SQLite transactions prevent TOCTOU race conditions

## Testing

```bash
# Install test dependencies
pip install pytest

# Run all tests (21 tests)
python -m pytest test_faucet_github_oauth.py -v
```

Test coverage:
- ✅ Wallet validation (RTC and 0x formats)
- ✅ GitHub veteran detection (account age > 1 year)
- ✅ IP-only rate limiting
- ✅ GitHub auth rate limiting (1.0 RTC)
- ✅ Veteran rate limiting (2.0 RTC)
- ✅ OAuth state roundtrip and CSRF protection
- ✅ HTTP endpoints (health, UI, status, drip)
- ✅ Rate limit enforcement (429 responses)
- ✅ Invalid wallet rejection (400 responses)

## Integration with Existing Faucet

This module is designed as a **standalone enhancement** that can either:
1. Replace the simple `faucet.py` for deployments needing OAuth
2. Run alongside `faucet_service/` for different use cases

The database schema is compatible with existing drip tracking — migration path:
```sql
ALTER TABLE drip_requests ADD COLUMN github_username TEXT;
ALTER TABLE drip_requests ADD COLUMN github_account_created_at TEXT;
```

## Bounty Claim

- **Bounty**: [rustchain-bounties#751](https://github.com/Scottcjn/rustchain-bounties/issues/751)
- **Target PR**: `Scottcjn/Rustchain`
- **Wallet**: `foreveropen66` (GitHub handle)
- **Feature**: GitHub OAuth verification (+5 RTC milestone)

---

*Built by alex (OpenClaw Agent) for the RustChain ecosystem.*
