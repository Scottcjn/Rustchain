# RustChain Apple II Miner Scaffold (6502)

This directory contains an initial scaffold for an Apple II-targeted miner implementation.

## Goals

- Keep runtime compatible with 6502-era constraints
- Avoid floating point and heavy dependencies
- Separate mining loop, transport, and attestation adapters

## Layout

- `miner6502.c` — minimal miner loop skeleton (portable C subset for cc65 path)
- `Makefile` — host-sim build + placeholder cc65 target

## Status

Scaffold phase only. This is not yet a full production miner.
