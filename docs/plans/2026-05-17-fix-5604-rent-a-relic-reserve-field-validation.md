# Plan: Fix #5604 Rent-a-Relic Reserve Field Validation

Created: 2026-05-17

## Scope
- Fix `POST /relic/reserve` so malformed JSON object field types return stable `400` responses instead of `500`.
- Ensure non-string `agent_id` / `machine_id` are rejected before normalization.
- Ensure boolean values for numeric fields are rejected before numeric business rules.

## Non-Goals
- No API redesign.
- No database schema change.
- No payout or reservation flow behavior changes for valid payloads.

## Implementation Units
1. `tools/rent_a_relic/server.py`
   - Add explicit type validation before `.strip()` for `agent_id` and `machine_id`.
   - Reject boolean values for `duration_hours` and `rtc_amount`.
   - Keep existing success and business-rule semantics unchanged for valid input.

2. `tests/` regression coverage for `/relic/reserve`
   - Add/extend tests for non-string and boolean malformed JSON field payloads.
   - Assert `400` with deterministic error payload.

## Test Scenarios
- JSON object with `agent_id: ["x"]` returns `400` and no insert.
- JSON object with `machine_id: {"id":"x"}` returns `400` and no insert.
- JSON object with `duration_hours: true` returns `400`.
- JSON object with `rtc_amount: false` returns `400`.
- Valid payload still returns success and preserves reservation behavior.

## Risks
- Error message drift can break existing clients if they parse exact strings.
- Guardrail: keep response shape stable and only tighten malformed input paths.

## Done Criteria
- Code path no longer throws `AttributeError` on malformed field types.
- Regression tests added for each malformed field case.
- PR opened against `Scottcjn/Rustchain` referencing `#5604`.
