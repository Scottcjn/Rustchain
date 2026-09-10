# Solution for Issue #8374

## 🛠️ Proposed Solution (by Aditya Waghamare)

### Analysis
The RustChain Bounties MCP title parser uses `re.search(r"(\d+)\s*RTC", title, re.IGNORECASE)` to extract RTC rewards from issue titles. For decimal values like `0.1 RTC`, the regex only captures the integer digits following the decimal point or strips the decimal, causing `0.1 RTC` to be incorrectly parsed as `1` or `1.0`.

### Fix
Update the regular expression in `_parse_github_issue()` to support optional decimal points and fractional digits (e.g. `\d+(?:\.\d+)?`).

### Implementation
```python
import re

# Before:
# match = re.search(r"(\d+)\s*RTC", title, re.IGNORECASE)

# After:
match = re.search(r"(\d+(?:\.\d+)?)\s*RTC", title, re.IGNORECASE)
```

### Testing
Verify via test cases covering integer, decimal, and whitespace variations:
```python
import re

def parse_reward(title):
    match = re.search(r"(\d+(?:\.\d+)?)\s*RTC", title, re.IGNORECASE)
    return float(match.group(1)) if match else None

assert parse_reward("[MICRO-BOUNTY: 0.1 RTC] Fix parser") == 0.1
assert parse_reward("[BOUNTY: 50 RTC] Feature") == 50.0
assert parse_reward("[BOUNTY: 10.5 RTC] Test decimal") == 10.5
print("All test cases passed successfully.")
```

Signed-off-by: Aditya Waghamare <adityawaghamare7620@gmail.com>


---
*Submitted by Aditya Waghamare*
💰 **Payout Address (Base L2 / EVM):** `0xb61dBcdBc3407F71EaCb64D4CBFAcf9FFfe2415C`