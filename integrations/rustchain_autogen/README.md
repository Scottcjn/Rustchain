# RustChain AutoGen Tools

This focused integration exposes four public RustChain reads as Microsoft
AutoGen `FunctionTool` objects:

- `check_balance(wallet_id)`
- `list_bounties(limit)`
- `get_node_health()`
- `get_current_epoch()`

The HTTP client uses only the Python standard library. AutoGen is imported only
when `as_autogen_tools()` is called, so the client remains usable and testable
without installing the framework.

## Usage

```python
from integrations.rustchain_autogen import RustChainAutoGenTools

rustchain = RustChainAutoGenTools()
tools = rustchain.as_autogen_tools()

# Register `tools` with an AutoGen AssistantAgent or tool-enabled runtime.
print(rustchain.check_balance("my-agent-wallet"))
print(rustchain.list_bounties(5))
```

Install the adapter dependency with:

```bash
pip install autogen-core
```

Public node reads use `https://rustchain.org`. Open bounties are read from the
public [`Scottcjn/rustchain-bounties`](https://github.com/Scottcjn/rustchain-bounties)
issue board because the node does not expose a bounty-list endpoint.

All network failures return structured `{ok: false, error: ...}` dictionaries
instead of raising into an agent loop.
