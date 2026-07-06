# RustChain Bounty Claim Helper

This script helps you claim the **0.5 RTC bounty** by:
1. Starring the [Scottcjn/Rustchain](https://github.com/Scottcjn/Rustchain) repository.
2. Posting a review comment on the bounty issue with your wallet ID and FTC-required disclosure.

## Prerequisites
- Python 3.6+
- A GitHub personal access token with `public_repo` scope (set as environment variable `GITHUB_TOKEN`)
- Install PyGithub: `pip install PyGithub`

## Usage
```bash
export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
python claim_bounty.py <wallet_id> "<review comment>"
```

### Example
```bash
python claim_bounty.py 0xAbC123 \
  "I reviewed the mining module in src/miner.rs. The proof-of-work implementation is clean and well-documented. I received RTC compensation for this review."
```

## Compliance Note
Your comment must:
- Mention what you reviewed (link to a file, PR, or feature).
- Give a specific, non-generic reason.
- Include the line: `I received RTC compensation for this review.`
- Include your wallet ID.

The script appends the disclosure and wallet ID automatically if missing.

## Disclaimer
This tool is provided for convenience. Ensure that your review is genuine and complies with the bounty rules. Automated or recycled comments will not be paid.
