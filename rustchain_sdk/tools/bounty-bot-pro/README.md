# 🦾 Bounty Verification Bot PRO

A staff-level automation suite for the RustChain ecosystem.

## Features
- **GitHub Star/Follow Verification**: Pure API-based validation of org-wide engagement.
- **Star King Detection**: Automated calculation of the 100+ star bonus.
- **RustChain Node Integration**: Direct wallet balance and existence checks.
- **AI-Powered Quality Scoring**: Uses Gemini 1.5 Pro to evaluate contribution depth and clarity.
- **GitHub Actions Native**: Zero-config deployment as a repo workflow.

## Setup
1. Copy this directory into your repository.
2. Add secrets:
   - `GITHUB_TOKEN`: PAT with `user` and `repo` scopes.
   - `GEMINI_API_KEY`: API key for content quality analysis.
3. Done! The bot will now auto-verify all comments containing 'Claiming' or 'Wallet:'.

## Manual CLI Usage
```bash
python verifier.py --user <github_user> --wallet <rtc_wallet> --article <link>
```
