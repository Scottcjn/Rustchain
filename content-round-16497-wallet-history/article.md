# Auditing RustChain Wallet History with a Small Python Report

RustChain exposes a public wallet-history endpoint that makes it possible to inspect transfer state without holding an admin credential or private key. That is useful for contributors, bounty earners, and developers who need to distinguish a transfer that merely exists from one that is actually confirmed. The important point is that a wallet history is not just a list of amounts: every row carries state, direction, counterparties, timestamps, and confirmation information. A good report should preserve those distinctions rather than collapsing everything into a single balance number.

The canonical RustChain API reference is here:

- Repository: https://github.com/Scottcjn/Rustchain
- API reference: https://github.com/Scottcjn/Rustchain/blob/main/docs/API_REFERENCE.md

According to the public API reference, `GET /wallet/history` accepts a `miner_id` (or backward-compatible `address`) and returns recent transfer records. Rows can include `tx_id`, sender and recipient addresses, `amount_rtc`, creation time, confirmation timing, `status`, `direction`, counterparty, and an optional memo. The documented status values include `pending`, `confirmed`, and `failed`. That status distinction matters: a pending transfer should not be treated as settled money simply because an amount is visible.

This tutorial includes a dependency-free Python script, `wallet_history_report.py`, that can either fetch the public endpoint or read a checked-in JSON file. The local-file mode makes the example reproducible even when you do not want a tutorial run to depend on network availability.

## What the script does

The script reads the array returned by `/wallet/history` and produces six simple outputs:

1. total transaction count;
2. counts grouped by status;
3. counts grouped by direction;
4. total received RTC;
5. total sent RTC; and
6. net flow, calculated as received minus sent.

That last figure is intentionally called **net flow**, not profit and not balance. Wallet history can contain transfers for many reasons: bounty payments, internal moves, refunds, test transfers, or other activity. A flow summary is accounting evidence, but it is not by itself proof of realized earnings.

## Run it against the included sample

From this directory, run:

```bash
python wallet_history_report.py --file sample_history.json
```

The checked-in sample contains three records: two confirmed incoming transfers and one pending outgoing transfer. The script produces the exact output saved in `RUN_OUTPUT.txt`:

```text
transactions: 3
status: confirmed=2, pending=1
direction: received=2, sent=1
received_rtc: 3.750000
sent_rtc: 0.750000
net_flow_rtc: 3.000000
```

The arithmetic is deliberately simple so it is easy to audit. Two incoming transfers of 2.50 RTC and 1.25 RTC total 3.75 RTC. The outgoing 0.75 RTC transfer is still pending, but it is still shown in the directional flow because the history record exists. If your accounting policy only recognizes confirmed transactions, the next enhancement would be to filter rows by `status == "confirmed"` before calculating settled flow.

## Run it against the public API

Because `/wallet/history` is documented as public and wallet-scoped, the script also supports:

```bash
python wallet_history_report.py --miner-id YOUR_MINER_ID --limit 50
```

It builds the query using Python's standard library and reads the JSON response directly. No API key is required for this documented read-only endpoint. The code does not sign transactions, move RTC, call admin routes, or inspect private credentials.

## Why status-aware reporting matters

RustChain's API reference separately documents signed transfers as entering a pending phase before confirmation. It also documents wallet-history fields such as `confirmed_at`, `confirms_at`, `status`, and `raw_status`. That means a robust payout tracker should preserve the lifecycle: submitted, accepted, payment queued, pending transfer, confirmed transfer, and only then whatever internal definition you use for settled funds.

Treating every visible amount as settled would create false positives. A pending transfer might still fail, be voided elsewhere in a workflow, or simply not have reached its confirmation time. Conversely, a confirmed incoming transfer is much stronger evidence because the public history exposes the state transition directly.

For production use I would add three things: a `--confirmed-only` switch, CSV export for reconciliation, and a checkpoint file so repeated runs can identify newly confirmed transactions without double-counting old ones. Those are reporting improvements; they do not require privileged access.

The core lesson is simple: use the public API as evidence, but keep state semantics intact. RustChain already exposes enough structure to build a transparent wallet audit trail with a few dozen lines of standard-library Python, and that is a better foundation than treating a single balance or screenshot as proof of settlement.
