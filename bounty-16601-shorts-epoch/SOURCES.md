# Sources

Primary source:
- RustChain Unified API Reference — `GET /epoch`: https://github.com/Scottcjn/Rustchain/blob/main/docs/API_REFERENCE.md

Claim map:
- Public endpoint path `/epoch` → API reference `GET /epoch` section.
- `blocks_per_epoch` example value `144` → API reference example response.
- `144 = ~24h` → API reference field description for `blocks_per_epoch`.
- Response fields `epoch`, `slot`, `epoch_pot`, `enrolled_miners`, `total_supply_rtc` → API reference example response and field table.
- The script does **not** claim `epoch_pot` is an individual miner payout; that caution is editorial clarification to avoid overstating a network-level field.

All factual product claims are traceable to the public repository above.