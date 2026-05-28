# RustChain Node

## Main Active Node
- `rustchain_v2_integrated_v2.2.1_rip200.py` - Production node with RIP-200 consensus

## Key Components
- `hardware_binding_v2.py` - Serial + entropy binding
- `fingerprint_checks.py` - 6-point hardware fingerprint
- `rewards_implementation_rip200.py` - Time-aged rewards
- `rip_200_round_robin_1cpu1vote.py` - 1 CPU = 1 Vote consensus
- `state_pruning.py` - Opt-in SQLite pruning for spent UTXO history and expired mempool rows

## RIP-200 Features
- Round-robin block production
- Antiquity multipliers (G4: 2.5x, G5: 2.0x, etc.)
- Hardware binding anti-spoof
- Ergo blockchain anchoring

## State Pruning

Run a dry-run first to see what would be pruned while keeping the most recent
100,000 blocks of spent UTXO history:

```bash
python3 node/state_pruning.py --db rustchain_v2.db --retain-blocks 100000
```

Apply pruning and archive removed spent UTXOs into `archive_utxo_boxes`:

```bash
python3 node/state_pruning.py --db rustchain_v2.db --retain-blocks 100000 --archive --apply
```

The tool does not delete blocks, balances, epoch state, or unspent UTXOs.
