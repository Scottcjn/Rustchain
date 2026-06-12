# RustChain Agno / Phidata Tools

This focused integration exposes four public RustChain reads to
[Agno](https://github.com/agno-agi/agno) and legacy Phidata agents:

- `check_balance(wallet_id)`
- `list_bounties(limit)`
- `get_node_health()`
- `get_current_epoch()`

The HTTP client uses only the Python standard library. Agno or Phidata is
imported only when `as_agno_toolkit()` is called, so the client remains usable
and testable without installing either framework.

## Usage

```python
from integrations.rustchain_agno import RustChainAgnoTools

rustchain = RustChainAgnoTools()
toolkit = rustchain.as_agno_toolkit()

# Pass `toolkit` to an Agno Agent, or call the methods directly.
print(rustchain.check_balance("my-agent-wallet"))
print(rustchain.list_bounties(5))
```

Install an adapter dependency with one of:

```bash
pip install agno
pip install phidata
```

Public node reads use `https://rustchain.org`. Open bounties are read from the
public [`Scottcjn/rustchain-bounties`](https://github.com/Scottcjn/rustchain-bounties)
issue board because the node does not expose a bounty-list endpoint. Node health
uses `/health` with the public Explorer `/api/stats` as a fallback, current epoch
uses `/epoch`, and balances use `/wallet/balance?miner_id=...`.

All network failures return structured `{ok: false, error: ...}` dictionaries
instead of raising into an agent loop.
