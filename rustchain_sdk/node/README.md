# RustChain Node

## Main Active Node
- `rustchain_v2_integrated_v2.2.1_rip200.py` - Production node with RIP-200 consensus

## Key Components
- `hardware_binding_v2.py` - Serial + entropy binding
- `fingerprint_checks.py` - 6-point hardware fingerprint
- `rewards_implementation_rip200.py` - Time-aged rewards
- `rip_200_round_robin_1cpu1vote.py` - 1 CPU = 1 Vote consensus

## RIP-200 Features
- Round-robin block production
- Antiquity multipliers (G4: 2.5x, G5: 2.0x, etc.)
- Hardware binding anti-spoof
- Ergo blockchain anchoring
