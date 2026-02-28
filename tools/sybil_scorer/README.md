# Sybil/Farming Risk Scorer

Flags likely bounty farming/Sybil behavior in claim triage.

## Features

- Account age heuristic
- Claim velocity (burst detection)
- Text similarity/template detection
- Wallet pattern detection
- Duplicate proof link detection

## Usage

```bash
python sybil_scorer.py --claims claims.json --output report.txt
```

## Test Fixtures

Includes 8 test fixtures:
- 3 benign claims
- 3 suspicious claims  
- 2 edge cases

## Reason Codes

| Code | Description |
|------|-------------|
| account_age_under_7_days | Account < 7 days |
| account_age_under_30_days | Account < 30 days |
| burst_claims_1_hour | 3+ claims in 1 hour |
| burst_claims_24_hours | 5+ claims in 24 hours |
| high_text_similarity | >80% similarity |
| generic_wallet_name | Generic pattern |
| duplicate_proof_link | Same URL as another |

## Reward

Implements **Bounty #476** - Sybil/Farming Risk Scorer (83 RTC)

## License

MIT
