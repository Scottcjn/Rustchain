# langchain-rustchain

LangChain tools for the [RustChain](https://rustchain.org) DePIN blockchain — Proof of Antiquity mining on vintage hardware.

## Quick Start

```bash
pip install langchain-rustchain
```

Then use with any LangChain agent:

```python
from langchain_rustchain import get_tools

tools = get_tools()
agent = create_react_agent(llm, tools)  # or any LangChain agent
```

## Tools

| Tool | Description | Source |
|------|-------------|--------|
| `rustchain_check_balance` | Check RTC balance of any wallet (`/wallet/balance`) | Node API |
| `rustchain_list_bounties` | List open ecosystem bounties (GitHub issues) | GitHub API |
| `rustchain_get_node_health` | Read node health status (`/health`) | Node API |
| `rustchain_get_current_epoch` | Read current epoch / slot (`/epoch`) | Node API |

All tools are read-only, no auth required, wallet = any string.

## Why RustChain?

- **Agent-native**: no auth, no captcha, wallet = any string, same-day RTC payout.
- **DePIN for vintage hardware**: old machines outmine new ones (Proof of Antiquity).
- **Solana bridge (wRTC)**: cross-chain liquidity.
- 55+ ecosystem repos, 5+ languages, 15+ CPU architectures.

## Example

See [example.py](example.py) for a complete agent script.

## Links

- [RustChain](https://rustchain.org)
- [Bounties](https://github.com/Scottcjn/rustchain-bounties)
- [Source](https://github.com/Scottcjn/Rustchain)