# rustchain-crewai-tool

A small, dependency-light [CrewAI](https://github.com/crewAIInc/crewAI) tool
that wraps the public [RustChain](https://rustchain.org) HTTP API so any
CrewAI agent can:

- check a wallet's RTC balance
- list open bounties from the public bounty board
- read node health
- read the current epoch

This package is the **CrewAI** submission for the
[Native RustChain Tool for CrewAI / AutoGen / Phidata / smolagents](https://github.com/Scottcjn/rustchain-bounties/issues/13952)
bounty (25 RTC per framework). The same shape is shared with the merged
LangChain reference at `langchain_rustchain_tool.py` (bounty #3074).

## Install

```bash
pip install crewai requests
# Then drop this file into your project (or `pip install -e .` from this
# integrations/ folder if you vendor it as a package).
```

## Quick start

```python
from rustchain_crewai_tool import RustChainCrewAITool
from crewai import Agent, Task, Crew

tool = RustChainCrewAITool()

# Direct method calls
balance = tool.check_balance("jdjioe5-cpu")
print(balance)
# -> {"ok": True, "wallet_id": "jdjioe5-cpu", "balance_rtc": 100.0, ...}

# Or dispatch by name (mirrors the LangChain RustChainTool shape)
epoch = tool.run({"action": "get_current_epoch"})
print(epoch)
# -> {"ok": True, "epoch": 191, "chain_id": "rustchain-mainnet-v2", ...}
```

## Use inside a CrewAI agent

```python
from rustchain_crewai_tool import RustChainCrewAITool
from crewai import Agent, Task, Crew

agent = Agent(
    role="RustChain bounty hunter",
    goal="Find open RustChain bounties and report their RTC totals",
    backstory="You monitor the RustChain public bounty board.",
    tools=[RustChainCrewAITool()],
)

task = Task(
    description=(
        "List the 5 highest-paying open RustChain bounties and "
        "summarise each one (title, link, RTC)."
    ),
    agent=agent,
    expected_output="A markdown table with title, link, and RTC per bounty.",
)

crew = Crew(agents=[agent], tasks=[task])
print(crew.kickoff())
```

## Public endpoints used

| Action            | URL pattern                                | Live (2026-06-12) |
|-------------------|--------------------------------------------|-------------------|
| `check_balance`   | `GET /api/wallet/<wallet_id>`              | ✅ 200 on `explorer.rustchain.org` |
| `get_node_health` | `GET /api/stats` (falls back to `/health`) | ✅ 200 on both hostnames |
| `get_current_epoch` | `GET /api/stats`                         | ✅ 200 on `explorer.rustchain.org` |
| `list_bounties`   | `GET https://api.github.com/repos/Scottcjn/rustchain-bounties/issues?labels=bounty&state=open` | ✅ public GitHub API |

The RustChain node itself does not currently expose a public
`/api/bounties` endpoint; bounty listing is therefore sourced from the
public bounty-board repo on GitHub. The error path is fully graceful: if
GitHub is unreachable, the tool returns a structured error dict and never
raises inside an agent loop.

## License

Same as the parent RustChain repository (MIT-style).
