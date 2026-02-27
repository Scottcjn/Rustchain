# Dreamcast SH4 Port Plan

## Phase 1 (this PR)
- Create SH4 miner scaffold
- Keep deterministic integer-only core loop
- Add build placeholders for cross-target path

## Phase 2
- Implement HTTP transport/attestation shim with constrained buffers
- Add parity tests between host-sim and target profile

## Phase 3
- Real hardware or accurate SH4 runtime validation
- Performance and stability tuning notes
