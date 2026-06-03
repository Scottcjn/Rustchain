# Slasher Core Demo

This example shows the focused slasher core added for issue #2369. It detects
double proposals, double votes, and surround votes from observed proposal and
vote records.

```bash
python - <<'PY'
from node.slasher import build_slashing_report

report = build_slashing_report(
    proposals=[
        {"validator_id": "validator-a", "slot": 7, "block_root": "p1"},
        {"validator_id": "validator-a", "slot": 7, "block_root": "p2"},
    ],
    votes=[
        {"validator_id": "validator-b", "source_epoch": 1, "target_epoch": 6, "root": "outer"},
        {"validator_id": "validator-b", "source_epoch": 3, "target_epoch": 4, "root": "inner"},
    ],
)

print(report["slashable"])
print(report["offense_counts"])
PY
```

Expected output:

```text
True
{'double_proposal': 1, 'double_vote': 0, 'surround_vote': 1}
```

Focused validation:

```bash
python -m pytest -q node/tests/test_slasher.py
```
