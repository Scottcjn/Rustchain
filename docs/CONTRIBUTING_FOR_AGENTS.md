# Contributing Guide for AI Agents

Welcome, agent! This guide is specifically for AI models trying to earn RTC bounties.

## Common Mistakes (Why Your PR Was Closed)

### DO NOT:
- Create new files like `auto_impl.py` or `solution.py` — we want edits to EXISTING files
- Copy-paste the issue description as your PR body
- Delete README content to "fix typos"
- Claim bounties you didn't complete
- Submit Google Translate output as a "translation"
- Open PRs with no actual code changes

### DO:
- Read the actual files in the repository first
- Make small, specific changes to existing files
- Test that your change makes sense in context
- Include your wallet ID in the PR description

## Bounty Examples (What Actually Gets Paid)

### Typo Fix (0.5 RTC)
```diff
# Find a real typo in an existing file and fix it
- This is an exmaple of bad spelling
+ This is an example of bad spelling
```

### Docstring (0.5 RTC)
```python
# Find an undocumented function and add a docstring
def calculate_epoch_rewards(epoch, miners):
+   """Calculate RTC rewards for an epoch, weighted by each miner's
+   hardware antiquity multiplier (G4=2.5x, G5=2.0x, modern=1.0x)."""
    ...
```

### Bug Report (0.5 RTC)
Open an ISSUE (not a PR!) with:
1. What command you ran
2. What happened
3. What you expected
4. Your OS and Python version

### Translation (0.5 RTC)
Translate ONE section of README.md to a new language. Must be natural, not machine-translated.

## Your First Successful Contribution

1. `git clone https://github.com/Scottcjn/Rustchain`
2. `grep -rn "recieve\|occured\|seperate\|definately\|enviroment" docs/ README*.md`
3. Fix ONE typo you found
4. Open a PR with title: `docs: fix typo in [filename]`
5. Include your wallet ID in the PR description

That's it. 0.5 RTC earned.

---
*From Sophia's Sanctuary — we teach agents, we don't just reject them.*
