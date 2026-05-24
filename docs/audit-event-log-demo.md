# Audit Event Log Demo

This change adds an append-only `audit_events` table that records core state transitions with a hash chain. The event log can be inspected directly from the node SQLite database:

```sql
SELECT id, event_type, subject_type, subject_id, epoch, previous_event_hash, event_hash
FROM audit_events
ORDER BY id;
```

Expected event types from the wired paths:

- `miner_attestation_recorded` when `/attest/submit` records attestation history
- `miner_epoch_enrolled` when auto-enroll or `/epoch/enroll` inserts a new epoch enrollment
- `epoch_finalized` when `finalize_epoch()` marks an epoch settled
- `beacon_envelope_stored` when `/beacon/submit` stores a signed Beacon envelope

Validation run:

```bash
.venv-bounty-validation/bin/python -m pytest -q node/tests/test_audit_event_log.py node/tests/test_beacon_anchor_signature.py
.venv-bounty-validation/bin/python -m py_compile node/audit_event_log.py node/beacon_anchor.py node/rustchain_v2_integrated_v2.2.1_rip200.py node/tests/test_audit_event_log.py
git diff --check
```
