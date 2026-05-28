# Proposer Duty Calendar Demo

The proposer duty calendar is available from:

```bash
curl "http://localhost:5000/epoch/proposer-duty-calendar?lookahead=2&history_limit=0"
```

With `RC_NODE_ID=node2` and `RC_P2P_PEERS=node1=https://node1.example,node3=https://node3.example`, epoch `4` returns a deterministic round-robin schedule:

```json
{
  "current_epoch": 4,
  "current_proposer": "node2",
  "current_node_is_proposer": true,
  "node_count": 3,
  "schedule": [
    {"epoch": 4, "proposer": "node2", "offset": 0, "is_current": true},
    {"epoch": 5, "proposer": "node3", "offset": 1, "is_current": false},
    {"epoch": 6, "proposer": "node1", "offset": 2, "is_current": false}
  ]
}
```

The TUI dashboard reads the same endpoint and renders the upcoming duties in a `Proposer Duties` panel next to recent blocks.
