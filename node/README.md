# RustChain Node

## Main Active Node
- `rustchain_v2_integrated_v2.2.1_rip200.py` - Production node with RIP-200 consensus

## Key Components
- `hardware_binding_v2.py` - Serial + entropy binding
- `fingerprint_checks.py` - 6-point hardware fingerprint
- `rewards_implementation_rip200.py` - Time-aged rewards
- `rip_200_round_robin_1cpu1vote.py` - 1 CPU = 1 Vote consensus
- `state_pruning.py` - Opt-in SQLite pruning for spent UTXO history and expired mempool rows

## Running a node: roles and the P2P secret

- **Sync node** (external operators): set `RC_NODE_ROLE=sync`. No fleet secrets.
  Serves the public read API, accepts attestations, does not settle epochs,
  does not join the authenticated P2P mesh. Leave `RC_P2P_SECRET` unset; the node logs
  `[P2P] RC_P2P_SECRET is not set: running as a SYNC node ...` and starts.
- **Settlement node** (the default if `RC_NODE_ROLE` is unset; verified operators,
  credentials issued privately): requires the issued `RC_P2P_SECRET` and fleet
  `RC_ADMIN_KEY`, and refuses to start without them (fail closed).
- `/p2p/state`, `/p2p/attestation_state`, `/p2p/peers` (and `/p2p/gossip`) on
  fleet nodes answer `401 {"error":"unauthorized","message":"valid X-P2P-Key required"}`
  to anyone without the fleet secret. That is expected for a sync node -- it is
  not a misconfiguration on your side and there is no key to request for it.
- DB path env var is `RUSTCHAIN_DB_PATH` (fallback `DB_PATH`), default `./rustchain_v2.db`.

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
