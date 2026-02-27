# RTC/ERG on Spectrum DEX (Scaffold)

This document defines the first integration scaffold for enabling RTC/ERG pair workflows.

## Goals

- Pair discovery
- Quote retrieval
- Swap-intent construction

## Files

- `integrations/spectrum/client.py`
- `scripts/spectrum_pair_check.py`

## Rollout Plan

1. Scaffold interfaces and config
2. Wire real API endpoints + normalization
3. Add test vectors and failure-mode handling
4. Add transaction assembly + signing workflow docs

## Safety

- Start with dry-run only
- validate slippage bounds before swap assembly
- enforce network/token ID checks
