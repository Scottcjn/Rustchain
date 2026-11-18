# Payout Pipeline Silent-Success Audit (`Scottcjn/rustchain-bounties#16471`)

## Overview

This audit documents **6 concrete silent-success defects** across `scripts/pr_review_gate.py`, `scripts/docstring_gate.py`, and `scripts/bounty_payout.py` where a gate or payout workflow exits `0` (green) while either skipping valid payouts, permanently starving claims, or bypassing per-contributor caps.

---

## Finding 1 — `scripts/pr_review_gate.py`: Premature `gate-processed` Label + Exit-0 Wrapper Causes Permanent Claim Starvation (`#16710`)

- **Location**: `scripts/pr_review_gate.py`, lines 236–239 and 288–291.
- **Silent-Success Mechanism**:
  1. `add_label(NUM, "gate-processed")` was called at line 239 **before** querying `/repos/{target}/pulls/{pr}/reviews`, `/comments`, or `/search/issues`.
  2. When any subsequent API call raised an exception (e.g. HTTP 502/503 or socket timeout), the `if __name__ == "__main__":` block caught `Exception`, printed `gate error: ...` to stderr, and **exited `0` (green)**.
  3. On every subsequent run or issue edit, line 236 (`if {"bounty-eligible", "needs-human", "gate-processed"} & labels: return`) saw `gate-processed` and exited immediately without adjudicating the claim.
- **Fix**: Defer `add_label(NUM, "gate-processed")` until after adjudication completes, and exit non-zero (`SystemExit(1)`) on unhandled exceptions.

---

## Finding 2 — `scripts/pr_review_gate.py`: `api()` Swallows HTTP 403/429/5xx on `GET /search/issues` Into `None`, Silently Bypassing the 15-Review Contributor Cap

- **Location**: `scripts/pr_review_gate.py`, lines 33–34 and 282–284.
- **Silent-Success Mechanism**:
  1. `api(path, method="GET")` caught **all** `urllib.error.HTTPError` exceptions on `GET` and returned `None` (`if method == "GET": return None`).
  2. GitHub's `/search/issues` endpoint has a strict secondary rate limit (30 requests/min). When `/search/issues?q=user:Scottcjn+label:bounty-eligible+author:{author}+type:issue` returned HTTP `403` or `429` (or `503`), `api(...)` returned `None`.
  3. Line 282 evaluated `elig = api(...) or {}`, turning `None` into `{}`, and line 283 evaluated `elig.get("total_count", 0) >= CAP` as `0 >= 15` (`False`).
  4. The gate then labeled an over-cap contributor `bounty-eligible` and exited `0`.
- **Fix**: Only treat HTTP `404`/`410` as `None`; raise `GateTransientError` on HTTP `403`/`429`/`5xx`, `URLError`, or missing `"total_count"` in `/search/issues`.

---

## Finding 3 — `scripts/pr_review_gate.py`: `api()` Swallows Transient Errors on `GET /pulls/{pr}/comments` Into `[]`, Falsely Auto-Closing Valid Claims

- **Location**: `scripts/pr_review_gate.py`, lines 33–34, 258, and 275–278.
- **Silent-Success Mechanism**:
  1. Line 258 executed `inl = api(f"/repos/{target}/pulls/{pr}/comments?per_page=100") or []`.
  2. If `/reviews` succeeded but `/comments` hit a transient HTTP `502`/`503`/`403`, `api()` returned `None` and `inl` became `[]` (`inline = 0`).
  3. Any reviewer whose review relied on inline diff comments (with a top-level summary `< 80` or `< 120` chars) was misclassified as non-substantive and **permanently closed (`state: "closed"`, `state_reason: "not_planned"`)** on a green workflow run.
- **Fix**: Raise `GateTransientError` on non-200 `/comments` responses and paginate both `/reviews` and `/comments` (`api_paginated_list`).

---

## Finding 4 — `scripts/pr_review_gate.py`: `next(...)` Only Inspects the Author's First Review `body_len`, Falsely Rejecting Follow-Up Substantive Reviews

- **Location**: `scripts/pr_review_gate.py`, line 273 (`body_len = next((len(r.get("body") or "") for r in rv if r["user"]["login"] == author), 0)`).
- **Silent-Success Mechanism**:
  1. If a contributor posted a short initial comment review (`< 80` chars) and then immediately posted the first substantive review (`>= 120` chars, no inline comments), `substantive[0]` correctly identified `first == author`.
  2. However, `next(...)` took the length of the contributor's **first** review record in `rv` (which was `< 120` chars), causing line 277 (`if inline == 0 and body_len < 120: close(...)`) to auto-close the valid claim!
- **Fix**: Use `max((len(r.get("body") or "") for r in rv if r["user"]["login"] == author), default=0)`.

---

## Finding 5 — `scripts/docstring_gate.py`: Missing `weekly-cap-reached` Idempotency Guard & Partial Label Failure (`#16711`, `#16662`)

- **Location**: `scripts/docstring_gate.py`, lines 400, 479–496, and 517–526.
- **Silent-Success Mechanism**:
  1. Claims over `MAX_RTC_PER_WEEK` received `weekly-cap-reached` and a multi-paragraph comment on every scheduled sweep while still over cap (`#16711`).
  2. When `add_labels("bounty-eligible", "docstring-verified")` succeeded on `bounty-eligible` and failed on `docstring-verified` (`#16662`), `bounty-eligible` remained on the issue, causing the next sweep's top-level skip check (`{"bounty-eligible", ...} & labels`) to skip the issue permanently while `bounty_payout.py` ignored it for lacking `docstring-verified`.

---

## Finding 6 — `scripts/bounty_payout.py`: `_list()` Swallows `json.JSONDecodeError` Into `[]` (`#16660`)

- **Location**: `scripts/bounty_payout.py`, lines 474–479.
- **Silent-Success Mechanism**:
  1. `_list()` caught `json.JSONDecodeError` and returned `[]`, so truncated/malformed `gh` output caused the payout runner to log `0 candidate issues` and exit `0`.
