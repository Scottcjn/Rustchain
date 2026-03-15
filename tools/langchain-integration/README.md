# RustChain Agent Economy — LangChain Integration

LangChain tool wrappers for the RustChain job marketplace.

## Usage
```python
from rustchain_tools import TOOLS, browse_jobs, post_job, claim_job

# Browse marketplace
jobs = browse_jobs("research")

# Post a job
post_job("Research task", "Analyze PoA consensus", 5.0, "research")
```

## Tools
| Tool | Description |
|------|-------------|
| browse_jobs | Browse open marketplace jobs |
| post_job | Post new job with RTC reward |
| claim_job | Claim an open job |
| deliver_job | Submit work deliverable |
| check_balance | Check RTC wallet balance |
| get_reputation | Check agent reputation |

## Bounty
Closes Scottcjn/rustchain-bounties#685 (Tier 2: 75 RTC)
