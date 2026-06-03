# Slashing Penalty Core Demo

This snippet shows the focused slashing penalty core applying double-vote
evidence to a validator balance and future epoch enrollment rows.

```bash
PYTHONPATH=node python - <<'PY'
import sqlite3
from slashing_penalties import apply_slashing_evidence, filter_slashed_validators

db = sqlite3.connect(":memory:")
db.executescript("""
CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER NOT NULL);
CREATE TABLE epoch_enroll (
    epoch INTEGER NOT NULL,
    miner_pk TEXT NOT NULL,
    weight REAL NOT NULL,
    PRIMARY KEY (epoch, miner_pk)
);
INSERT INTO balances VALUES ('validator-a', 1000000);
INSERT INTO epoch_enroll VALUES (10, 'validator-a', 1.0);
INSERT INTO epoch_enroll VALUES (11, 'validator-a', 1.0);
INSERT INTO epoch_enroll VALUES (12, 'validator-a', 1.0);
""")

result = apply_slashing_evidence(
    db,
    {
        "validator_id": "validator-a",
        "offense_type": "double_vote",
        "epoch": 10,
        "details": {"vote_a": "root-a", "vote_b": "root-b"},
    },
    current_epoch=10,
    slash_fraction=0.10,
    exclusion_epochs=2,
    now_ts=1234,
)
print(result["penalty_urtc"], result["slashed_until_epoch"], result["removed_future_enrollments"])
print(db.execute("SELECT amount_i64 FROM balances WHERE miner_id='validator-a'").fetchone()[0])
print(filter_slashed_validators(db, ["validator-a", "validator-b"], 11))
PY
```

Expected output:

```text
100000 12 2
900000
['validator-b']
```
