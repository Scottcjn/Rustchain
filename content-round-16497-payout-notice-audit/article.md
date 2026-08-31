# Auditing RustChain Payout Notices Without Mistaking a Promise for Payment

RustChain contributors often encounter several different kinds of evidence during a bounty payout: an issue comment that mentions an amount, a project-issued pending transfer identifier, a transaction hash, a confirmation time, and eventually a confirmed transfer. Those are not interchangeable. A message that says “payment is on the way” is weaker than a project-authorized payout record, and a pending record is still not the same thing as settled funds.

This tutorial builds a small, dependency-free Python tool that performs a conservative first-pass audit of payout notices. It is designed to answer one narrow question: **does this message contain the minimum identity and field signals needed for a human to verify it against project records?** It deliberately does not claim to prove that a transaction exists, that a hash is valid, or that RTC has settled.

The canonical RustChain repository is [Scottcjn/Rustchain](https://github.com/Scottcjn/Rustchain). Its [payment-authority policy](https://github.com/Scottcjn/Rustchain/blob/main/SECURITY.md#payment-authority-impersonation) says that payout authority belongs to `@Scottcjn` or clearly labeled project automation accounts acting on his behalf. A legitimate notice also includes details such as the amount, recipient wallet, `pending_id`, `tx_hash`, and confirmation timing. The policy warns contributors not to treat similar language from an unrelated account as authorization.

## What the checker does

The runnable file is [`payout_notice_audit.py`](https://github.com/Aming9303/Rustchain/blob/bounty-16497-payout-verifier/content-round-16497-payout-notice-audit/payout_notice_audit.py). It accepts a JSON array in which each object has an `author` and a `body`. For every notice it:

1. checks the author against the project accounts documented in `SECURITY.md`;
2. extracts the documented payout fields without trying to interpret or validate their values;
3. reports any missing fields; and
4. assigns one of three preflight statuses.

The statuses are intentionally cautious:

- `reject_unauthorized_author` means the author is not in the documented authority list, even when the message contains convincing-looking identifiers;
- `hold_missing_fields` means the author is recognized but the notice is incomplete; and
- `ready_for_project_record_verification` means the message has enough structure for the next verification step.

Every result also contains `"settled": false`. That invariant is important. Offline text parsing cannot establish that a project database contains the pending record or that a transfer has reached its confirmation state.

## Run the reproducible sample

The directory includes [`sample_notices.json`](https://github.com/Aming9303/Rustchain/blob/bounty-16497-payout-verifier/content-round-16497-payout-notice-audit/sample_notices.json) with three synthetic examples. No real wallet, transfer identifier, or transaction hash is used. From the repository root, run:

```bash
python content-round-16497-payout-notice-audit/payout_notice_audit.py \
  content-round-16497-payout-notice-audit/sample_notices.json
```

The first example has a documented authority and all five fields, so it is ready for record verification. The second contains every field but comes from an unrelated account, so it is rejected. The third comes from an authorized automation account but lacks the wallet, transaction hash, and confirmation time, so it is held.

Run the focused tests with:

```bash
python -m unittest discover -s content-round-16497-payout-notice-audit \
  -p "test_payout_notice_audit.py" -v
```

The tests cover all three classifications and reject a malformed top-level JSON object. They also assert that even a complete authorized notice remains unsettled at this stage.

## Where real verification begins

After the preflight passes, a contributor should compare the `pending_id` and `tx_hash` with the project-issued record or documented public API response. The wallet and amount must match the intended recipient and bounty. Confirmation timing should be preserved rather than rounded into an immediate “paid” status. Only the final confirmed project or chain evidence should update an accounting ledger as settled.

This separation prevents two common errors. The first is social engineering: a stranger can copy the vocabulary of a legitimate payout notice. The second is premature accounting: even a genuine project account may announce a pending transfer before its confirmation window closes. Identity checks address the first problem; lifecycle-aware verification addresses the second.

The example is small enough to audit and adapt. A production version could load the authority list from a signed project policy, fetch the corresponding pending record, validate field formats, and store a checkpoint so the same transfer is not counted twice. Those additions should preserve the same conservative rule: text is a lead, a project record is evidence, and confirmation is settlement.

Assistance disclosure: this tutorial and code were prepared with AI assistance, then checked against RustChain's public `SECURITY.md` payment-authority policy. The examples are synthetic, and the tests were run locally before submission.
