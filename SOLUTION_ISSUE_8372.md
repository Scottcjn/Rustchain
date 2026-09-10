# Solution for Issue #8372

## 🛠️ Proposed Solution (by Aditya Waghamare)

### Analysis
The `rustchain_bounties` MCP tool lists ordinary issues (like `[WALLET]` or `[Claim]` and `[RETIRED]`) as valid `BountyInfo` objects with zero rewards because `RustChainClient._parse_github_issue()` falls through on unlabeled issues and returns a default zero-reward `BountyInfo` instead of filtering them out (`return None`), and the GitHub API query does not filter for the `bounty` label.

### Fix
Update `RustChainClient._parse_github_issue()` to explicitly return `None` when an issue lacks a bounty label or reward pattern, and filter issues by label/criteria in the GitHub API request.

### Implementation
```python
class RustChainClient:
    @staticmethod
    def _parse_github_issue(issue: dict) -> Optional[BountyInfo]:
        labels = [l.get("name", "").lower() for l in issue.get("labels", [])]
        title = issue.get("title", "")
        body = issue.get("body", "") or ""
        
        # Check for explicit non-bounty prefixes or missing bounty indicators
        upper_title = title.upper()
        if any(tag in upper_title for tag in ["[WALLET]", "[CLAIM]", "[RETIRED]"]):
            if "bounty" not in labels and not any(k in upper_title for k in ["RTC", "BOUNTY"]):
                return None

        # Extract reward or return None if not a valid bounty
        reward = RustChainClient._extract_reward(title, body)
        if reward is None and "bounty" not in labels:
            return None
            
        return BountyInfo(
            issue_number=issue["number"],
            title=title,
            html_url=issue["html_url"],
            reward_rtc=reward or 0.0,
            tags=labels
        )
```

### Testing
Run issue parser tests with sample payload inputs containing `[WALLET]` and verify `None` is returned, while actual bounties with rewards parse correctly.
Signed-off-by: Aditya Waghamare <adityawaghamare7620@gmail.com>


---
*Submitted by Aditya Waghamare*
💰 **Payout Address (Base L2 / EVM):** `0xb61dBcdBc3407F71EaCb64D4CBFAcf9FFfe2415C`