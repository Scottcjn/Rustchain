# `langchain-rustchain` — Native LangChain Tool for RustChain (`#3074`)

First-class LangChain tool integration for the **RustChain Proof-of-Antiquity (RIP-PoA)** blockchain and the [`Scottcjn/rustchain-bounties`](https://github.com/Scottcjn/rustchain-bounties) agent economy (`Bounty #3074`).

## Features

- **`RustChainTool` (`BaseTool` subclass)**:
  - `check_balance(wallet_id: str) -> float`: Queries live RTC balance for any `RTC...` wallet or miner ID.
  - `list_bounties(limit: int = 10) -> list[dict]`: Fetches open `bounty`-labeled issues from `Scottcjn/rustchain-bounties` with parsed RTC rewards.
  - `get_node_health() -> dict`: Queries `/health` on the RustChain Mainnet node (`version`, `ok`, `db_rw`, `uptime_s`, `tip_age_slots`).
  - `get_current_epoch() -> dict`: Queries `/epoch` (`epoch`, `slot`, `enrolled_miners`, `epoch_pot`, `total_supply_rtc`).
- **`RustChainToolkit`**: Returns focused individual LangChain tools (`rustchain_check_balance`, `rustchain_list_bounties`, `rustchain_node_health`, `rustchain_current_epoch`) ready to bind to any LangChain / LangGraph agent.

## Installation

```bash
pip install -e integrations/langchain-rustchain
```

## Quickstart

```python
from langchain_rustchain import RustChainTool, RustChainToolkit

tool = RustChainTool()
print("Node health:", tool.get_node_health())
print("Current epoch:", tool.get_current_epoch())
print("Wallet balance:", tool.check_balance("RTCfe0ac752b80e543048c0d91e7dddd1277678b8a5"))
print("Open bounties:", tool.list_bounties(limit=5))
```

## Example Agent Script

Run the included autonomous bounty-discovery & balance-check agent:

```bash
python integrations/langchain-rustchain/examples/bounty_hunter_agent.py
```

## Links

- **RustChain Bounties**: <https://github.com/Scottcjn/rustchain-bounties/issues/3074>
- **RustChain Mainnet**: <https://rustchain.org>
