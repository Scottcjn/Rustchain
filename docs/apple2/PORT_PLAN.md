# Apple II (6502) Port Plan

## Phase 1 (this PR)
- Establish miner scaffold
- Keep integer-only, tiny-memory-friendly loop
- Define toolchain path (host-sim now, cc65 next)

## Phase 2
- Implement transport shim for attestation/enroll over constrained network stack
- Add compact proof payload construction
- Add deterministic test vectors for host-vs-target parity

## Phase 3
- Real hardware bring-up + logs/screenshots
- Performance and stability notes
