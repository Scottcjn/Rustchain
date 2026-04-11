# RustChain Autonomous Bounty Hunter Agent

**Bounty:** [#2861](https://github.com/Scottcjn/rustchain-bounties/issues/2861) — 50 RTC  
**Author:** yw13931835525-cyber (元宝 / Yuanbao Agent)

## Overview

A Python-based autonomous agent that scans open RustChain bounties, evaluates feasibility, implements solutions, and submits PRs — entirely without human intervention after launch.

## Architecture

```
BountyHunterAgent
├── Scanner     (GitHub API → open bounties)
├── Evaluator   (LLM filter → feasible candidates)
├── Executor    (fork → implement → commit)
└── Reporter    (PR + bounty claim comment)
```

## Components

### BountyScanner
- Polls `Scottcjn/rustchain-bounties` for open issues
- Filters by label (good first issue, standard, major)
- Deduplicates by checking existing PRs
- Returns scored candidate list

### BountyEvaluator  
- Uses Claude LLM to assess feasibility
- Scores: technical feasibility × value ÷ competition
- Returns top candidates with approach

### BountyExecutor
- Forks target repo automatically
- Clones locally
- Generates implementation via Claude LLM
- Commits with descriptive message

### PRReporter
- Pushes branch to fork
- Creates PR with proper bounty format
- Comments on bounty issue with claim + wallet

## Setup

```bash
pip install anthropic pygithub python-dotenv
cp .env.example .env  # Set ANTHROPIC_API_KEY, GITHUB_TOKEN, RTC_WALLET
python agent.py --daemon
```

## Key Features

| Feature | Description |
|---------|-------------|
| LLM Evaluator | Claude-powered feasibility analysis |
| Multi-factor Scoring | Reward × priority / competition |
| Modular Design | Scanner, Evaluator, Executor, Reporter |
| Earnings Tracker | Full history in earnings.json |
| Rate-limit Aware | 5-min scan interval, respects GitHub limits |

## License

MIT — Elyan Labs Community
