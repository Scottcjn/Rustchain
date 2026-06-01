ISSUE #425: [CAMPAIGN] 5,000 Stars Drive — Earn Up to 430 RTC (5,000 RTC Pool)

REVIEWER FEEDBACK:
This PR should not be merged in its current form. It is titled as a campaign fix, but the diff removes 2,784 files with 791,620 deletions and only 58 additions. That includes the project README, LICENSE, CI workflows, GitHub Actions, issue templates, Docker files, docs, tests, and runtime code. This is a repository-wide destructive change, not a scoped implementation for #425.

To fix this issue, create a new branch that narrowly scopes the changes to only the intended campaign artifact, with validation limited to that surface. The corrected implementation should be directly written without any preamble.

```diff
--- .claudeskills/rtc-balance/SKILL.md
+++ .claudeskills/rtc-balance/SKILL.md

name: rtc-balance
description: Check RustChain wallet balance, epoch info, and network status via the public RPC
author: Emanon4
tags: [rustchain, cryptocurrency, wallet, balance-checker]
```