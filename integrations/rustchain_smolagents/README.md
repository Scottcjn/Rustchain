# RustChain smolagents Tools

This focused integration exposes four public RustChain reads as Hugging Face
`smolagents` tools:

- `rustchain_check_balance(wallet_id)`
- `rustchain_list_bounties(limit)`
- `rustchain_get_node_health()`
- `rustchain_get_current_epoch()`

The HTTP client uses only the Python standard library. `smolagents` is imported
only when `as_smolagents_tools()` is called, so the client remains usable and
testable without installing the framework.

## Usage

```python
from smolagents import CodeAgent
from integrations.rustchain_smolagents import RustChainSmolagentsTools

rustchain = RustChainSmolagentsTools()
tools = rustchain.as_smolagents_tools()

agent = CodeAgent(tools=tools, model=...)

# Direct calls are also available for tests or non-agent scripts.
print(rustchain.check_balance("my-agent-wallet"))
print(rustchain.list_bounties(5))
```

Install the adapter dependency with:

```bash
pip install smolagents
```

Public node reads use `https://rustchain.org`. Open bounties are read from the
public [`Scottcjn/rustchain-bounties`](https://github.com/Scottcjn/rustchain-bounties)
issue board because the node does not expose a bounty-list endpoint. Node health
uses `/health` with the public Explorer `/api/stats` as a fallback, current epoch
uses `/epoch`, and balances use `/wallet/balance?miner_id=...`.

All network failures return structured `{ok: false, error: ...}` dictionaries.
The smolagents adapters serialize those dictionaries as JSON strings because
smolagents tools declare a string output type.
