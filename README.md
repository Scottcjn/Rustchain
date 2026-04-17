# Autonomous Bounty Hunter Agent

An AI agent that autonomously browses, evaluates, and claims RustChain bounties.

## Features

- 🔍 **Auto Browse**: Scans RustChain bounty repository for open issues
- 🧠 **Evaluate**: Uses LLM to assess if the agent can complete the task
- 🛠️ **Implement**: Forks repo, implements solution, creates PR
- 💰 **Claim**: Submits bounty claim with wallet address
- 📊 **Track**: Maintains earnings and success rate

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Bounty Scanner │───▶│  LLM Evaluator  │───▶│  Task Executor  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
        │                       │                       │
        ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ GitHub API      │    │ Claude/OpenAI   │    │ Git Operations  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Components

### 1. BountyScanner
- Lists open bounty issues
- Filters by labels, complexity, reward
- Extracts requirements and acceptance criteria

### 2. LLMEvaluator  
- Analyzes task complexity
- Estimates implementation time
- Predicts success probability
- Recommends go/no-go decision

### 3. TaskExecutor
- Forks target repository
- Implements solution using LLM
- Runs tests and validation
- Creates clean PR with proper commit messages

### 4. BountyClaimer
- Submits bounty claim
- Tracks wallet earnings
- Maintains agent reputation

## Setup

```bash
# Install dependencies
pip install anthropic PyGithub python-dotenv

# Configure API keys
export ANTHROPIC_API_KEY="your-claude-key"
export OPENAI_API_KEY="your-openai-key"
export GITHUB_TOKEN="your-github-token"

# Configure wallet
export RTC_WALLET="your-rustchain-wallet"

# Run agent
python src/main.py
```

## Configuration

Create `.env` file:

```env
# API Keys
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GITHUB_TOKEN=ghp_...

# Agent Settings
RTC_WALLET=zhaog100
MIN_BOUNTY_RTC=25
MAX_COMPLEXITY=8
TARGET_REPOSITORY=Scottcjn/rustchain-bounties

# LLM Settings
LLM_PROVIDER=claude  # claude, openai, local
LLM_MODEL=claude-3-5-sonnet-20240620
MAX_TOKENS=4000
TEMPERATURE=0.7
```

## Usage

```bash
# Run full autonomous mode
python src/main.py --autonomous

# Run with specific bounty
python src/main.py --bounty 2867

# Dry run (evaluate without implementing)
python src/main.py --dry-run

# Debug mode
python src/main.py --debug
```

## Quality Assurance

- ✅ Code follows RustChain contribution guidelines
- ✅ PRs include proper tests
- ✅ Commit messages are meaningful
- ✅ Respects GitHub rate limits
- ✅ Maintains clean git history

## Safety Features

- 🛡️ Rate limiting (max 1 PR/hour)
- 🛡️ Wallet validation before claiming
- 🛡️ Code review before submission
- 🛡️ Rollback on failure
- 🛡️ Logging and monitoring

## Roadmap

- [ ] Phase 1: Browse and evaluate bounties (✅ Done)
- [ ] Phase 2: Implement simple text-based tasks
- [ ] Phase 3: Implement code-based tasks
- [ ] Phase 4: Auto-iterate and improve based on feedback
- [ ] Phase 5: Multi-agent collaboration

## Wallet

zhaog100

## License

MIT