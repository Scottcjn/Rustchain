# RustChain Tools for OpenAI Agents SDK

Native integration giving any agent built with the **OpenAI Agents SDK** or **Swarm** full capability to query balances, inspect open bounties, check node health, and read epoch consensus state.

## Installation

```bash
pip install openai-agents  # or swarm
```

## Quickstart

```python
from integrations.rustchain_openai_agents import RustChainOpenAIAgentsTools
from agents import Agent, Runner

# Initialize tools
rc_tools = RustChainOpenAIAgentsTools()
tools = rc_tools.as_openai_agent_tools()

# Define autonomous agent
agent = Agent(
    name="RustChain Assistant",
    instructions="You help users navigate the RustChain Proof-of-Antiquity network.",
    tools=tools,
)

# Run agent
result = Runner.run_sync(agent, "Check current node health and recent bounties")
print(result.final_output)
```

## Standalone Usage (Zero Dependencies)

The tool functions can be called directly without any third-party framework installed:

```python
from integrations.rustchain_openai_agents import RustChainOpenAIAgentsTools

rc = RustChainOpenAIAgentsTools()

# Check confirmed wallet balance
balance = rc.check_balance("RTC8b1fb717791b0a7b72649342b5c7c7bd822786af")

# List open bounties
bounties = rc.list_bounties(limit=5)

# Query node health and epoch
health = rc.get_node_health()
epoch = rc.get_current_epoch()
```
