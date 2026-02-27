# Ergo Mainnet Bridge (Scaffold)

This scaffold starts RTC↔ERG bridge implementation in staged form.

## Included

- Bridge intent/event data model stubs
- Dry-run daemon skeleton for bridge lifecycle simulation
- Helper script: `scripts/ergo_bridge_dryrun.py`

## Security considerations (next steps)

- replay protection via nonce ledger
- min-confirmation threshold for source-chain events
- bounded slippage/fee controls
- idempotent settlement execution

## Rollout

1. Scaffold + dry-run
2. Testnet endpoint wiring + deterministic tests
3. Mainnet guarded rollout with observability
