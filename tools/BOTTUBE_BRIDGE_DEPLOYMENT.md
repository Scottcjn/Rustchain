# RustChain <-> BoTTube Bridge Deployment Guide

## Overview
The \`bottube_bridge.py\` daemon monitors content upload events and viewer tipping interactions on BoTTube, autonomously settling creator disbursements on the RustChain ledger.

## Requirements
- Python 3.10+
- \`sqlite3\`, \`requests\`
- Node credentials / wallet signing keys

## Deployment Steps
1. Configure \`bridge_config.json\` with desired milestone payouts and anti-abuse caps.
2. Run unit & integration test:
   \`\`\`bash
   python3 bottube_bridge.py
   \`\`\`
3. Run as a background systemd service or cron daemon:
   \`\`\`bash
   python3 bottube_bridge.py --daemon --config bridge_config.json
   \`\`\`

## Anti-Abuse Architecture
- **Cryptographic Provenance Gate**: Every video must supply a valid \`canonical_asset.sha256\` and model provenance metadata hash.
- **Duration Floor**: Reject synthetic micro-clips under 8.0 seconds.
- **Dynamic Payout Rate Limits**: Hard limits of 5.0 RTC/hour and 25.0 RTC/day per creator wallet to eliminate Sybil scraping attacks.
