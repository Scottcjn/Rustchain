#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Adjudicate docstring bounty claims.

WHY THIS EXISTS
---------------
The #73 gate only recognises CODE-REVIEW claims -- `is_review_claim()` requires
"review" in the title. Every other bounty type falls straight through it, so
docstring, blog, star and bug claims had no automated adjudication at all and
simply accumulated unpaid. On 2026-08-10 that was 19 open docstring claims,
batches 31 to 49, none of them gate-processed.

Docstring claims are unusually verifiable, so they are worth gating properly
rather than paying on assertion. A claim states a PR, a file, a function count
and a rate, and the diff should be `+N/-0` where N is that count.

WHAT IT VERIFIES (all of it, before paying anything)
  1. The cited PR lives in an Elyan Labs repository (DOCSTRING_ALLOWED_OWNERS)
     and was **authored by the claimant**. Without this, citing anyone's
     merged docstring PR anywhere on GitHub was paid to the claimant.
  2. The cited PR is **MERGED**. An open PR is not delivered work.
  3. The added lines are **actually docstrings** -- lines opening with a quote
     triple. This is the check that matters: without it "I added 40 docstrings"
     pays out for 40 lines of anything.
  4. The claimed count is compared with what was really added (reported, and
     the verified count is what gets paid). The file named in the claim is NOT
     checked; every added docstring in the PR counts.

PAYMENT IS COMPUTED FROM THE VERIFIED COUNT, NEVER THE CLAIMED ONE. A claim
that overstates is paid the true amount rather than rejected outright -- the
usual cause is miscounting, not fraud, and rejecting honest arithmetic errors
teaches people to stop claiming.

Sets `bounty-eligible` + `docstring-verified` and posts the arithmetic, so the
existing payout runner pays it on its next pass. Never moves RTC itself.

Env: GITHUB_TOKEN, GH_REPO, ISSUE_NUMBER, RATE_PER_FUNC (0.01), MAX_RTC (25).
"""
from __future__ import annotations

import datetime
import json
import os
import re
import subprocess
import sys

REPO = os.environ.get("GH_REPO", "Scottcjn/rustchain-bounties")
NUM = os.environ.get("ISSUE_NUMBER", "")
RATE = float(os.environ.get("RATE_PER_FUNC", "0.01"))
# A single claim asking for more than this is not auto-payable. Docstring work
# is small by nature; a very large claim is either a mistake or something that
# deserves a human read.
MAX_RTC = float(os.environ.get("MAX_RTC", "25"))
# Per-contributor rolling weekly ceiling on DOCSTRING earnings specifically.
#
# A per-claim ceiling bounds nothing here: each batch is ~5 RTC, so batch 50,
# 51 and 52 all sail under it. The unbounded axis is volume, not size -- there
# is always another file to document, which is the same faucet shape as the
# ONBOARD comparison bounty that had to be closed at 98% farm share.
#
# At 0.01 RTC/function the weekly cap is a soft backstop, not the constraint:
# a docstring is a one-line comment (often on a test stub), so the per-unit price
# sits at the top of what the strongest contributors earn across ALL bounty
# types in a week (measured 2026-08-10: typical top earners 20-50 RTC/week).
# It caps a faucet without punishing anyone doing real work.
#
# This applies ONLY to docstring claims. Large one-off bounties are untouched.
MAX_RTC_PER_WEEK = float(os.environ.get("MAX_RTC_PER_WEEK", "40"))

PR_RE = re.compile(r'github\.com/([\w.-]+/[\w.-]+)/pull/(\d+)')
COUNT_RE = re.compile(
    r'(?:functions?\s+documented|documented|added\s+docstrings?\s+to)\D{0,20}?(\d{1,3})',
    re.I)
FILE_RE = re.compile(r'(?:^|\s)((?:[\w.-]+/)*[\w.-]+\.py)\b')
DOCSTRING_OPEN = re.compile(r'^\s*[rRbBuU]{0,2}("""|\'\'\')')
PAYOUT_MARKER_RE = re.compile(r'<!--\s*rtc-payout-amount:\s*([\d.]+)\s*-->')

# Identities whose `rtc-payout-amount` marker is an authoritative figure.
#
# This gate posts its marker with the workflow's GITHUB_TOKEN, i.e. as
# `github-actions[bot]` (REST) / `github-actions` (GraphQL). Maintainers can
# adjudicate by hand. The set deliberately MIRRORS `TRUSTED_AUTHORS` in
# scripts/bounty_payout.py (a test pins the two together): the weekly cap must
# count exactly the markers the payout runner will pay. Counting fewer would
# undercount earnings and fail the cap open; counting more lets strangers
# steer it. Every other commenter is untrusted -- anyone with a GitHub account
# can write a marker on a public issue (#16471, @fsalmon1991).
TRUSTED_MARKER_AUTHORS = frozenset({
    "scottcjn", "sophiaeagent-beep", "github-actions[bot]", "github-actions"})


PAYOUT_AMOUNT_RE = re.compile(r'\d+(?:\.\d+)?')

# Owners whose repositories docstring work is paid for. `PR_RE` accepts a PR
# URL in ANY repository on GitHub, and nothing downstream checked where it
# pointed, so a claim citing any merged documentation PR anywhere (CPython,
# requests, ...) was verified and paid. Mirrors pr_review_gate.py, which only
# follows cited PRs into the maintainer's own repositories.
ALLOWED_PR_OWNERS = frozenset(
    o.strip().lower()
    for o in os.environ.get("DOCSTRING_ALLOWED_OWNERS", "Scottcjn").split(",")
    if o.strip())


def _comment_login(c):
    """Author login of a comment in GraphQL (`author`) or REST (`user`) shape.

    Same precedence as `_comment_author_login` in scripts/bounty_payout.py:
    `author` first, and if it is a dict its login is final (no fall-through to
    `user`). The two must resolve the same author for the same comment.
    """
    if not isinstance(c, dict):
        return None
    for key in ("author", "user"):
        who = c.get(key)
        if isinstance(who, dict):
            return who.get("login")
    return None


def trusted_payout_amount(comments):
    """The payout amount a claim's comment thread authoritatively carries.

    Only markers written by TRUSTED_MARKER_AUTHORS count; a marker from anyone
    else is ignored no matter where it sits in the thread. Like the payout
    runner, the LAST valid trusted marker wins. Returns None if there is none.

    A trusted marker whose amount is not a plain number (`...`, `1.2.3`) is
    logged and ignored rather than crashing the gate run. This matches
    `_trusted_marker_amount` in bounty_payout.py, which skips the same marker
    and so never pays it -- the cap keeps counting exactly what gets paid.
    """
    amount = None
    for c in comments or []:
        login = _comment_login(c)
        if not login or login.lower() not in TRUSTED_MARKER_AUTHORS:
            continue
        m = PAYOUT_MARKER_RE.search(c.get("body") or "")
        if not m:
            continue
        if not PAYOUT_AMOUNT_RE.fullmatch(m.group(1)):
            print(f"::warning::ignoring unparseable trusted payout marker {m.group(1)!r}")
            continue
        amount = float(m.group(1))
    return amount


class GhError(RuntimeError):
    """A `gh` invocation failed. Must never be mistaken for an empty result."""


def gh(args, default=None, strict=False):
    """Run `gh` and parse JSON.

    `strict=True` raises on failure instead of returning `default`. That matters
    wherever the result feeds a MONEY decision: the earnings lookup behind the
    weekly cap returned `{}` on any CLI/auth/rate-limit failure, which
    `docstring_rtc_this_week()` then reported as 0.0 RTC already earned. A
    contributor already over the 40 RTC/week ceiling was therefore treated as
    having earned nothing, and the cap failed OPEN. A failed lookup is not an
    authoritative zero.
    """
    try:
        p = subprocess.run(["gh"] + args, capture_output=True, text=True, timeout=120)
    except Exception as e:
        if strict:
            raise GhError(f"gh {' '.join(args[:3])} failed: {e}") from e
        return default
    if p.returncode != 0:
        if strict:
            raise GhError(f"gh {' '.join(args[:3])} exited {p.returncode}: "
                          f"{(p.stderr or '').strip()[:200]}")
        return default
    try:
        return json.loads(p.stdout) if p.stdout.strip() else default
    except json.JSONDecodeError as e:
        if strict:
            raise GhError(f"gh {' '.join(args[:3])} returned unparseable JSON: {e}") from e
        return default


def gh_raw(args):
    result = subprocess.run(["gh"] + args, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise GhError(f"gh {' '.join(args[:3])} failed (exit {result.returncode}): {result.stderr.strip()}")
    return result.stdout



def add_labels(*names):
    """Apply labels via REST.

    `gh issue edit --add-label` goes through GraphQL and currently fails with a
    Projects-classic deprecation error -- and it fails SILENTLY, so the gate
    would post "verified" while never marking the claim eligible, and the payout
    runner would never see it. Verified by observing an adjudicated claim come
    back with `labels: []`.
    """
    ok = True
    for n in names:
        try:
            r = subprocess.run(["gh", "api", "-X", "POST",
                                f"/repos/{REPO}/issues/{NUM}/labels", "-f", f"labels[]={n}"],
                               capture_output=True, text=True, timeout=60)
        except (subprocess.TimeoutExpired, OSError) as e:
            # A hung or missing `gh` is a failed label, reported like any other
            # (callers fail closed on False), not a crash mid-adjudication.
            print(f"::warning::could not apply label {n}: {e.__class__.__name__}: {str(e)[:120]}")
            ok = False
            continue
        if r.returncode != 0:
            print(f"::warning::could not apply label {n}: {r.stderr.strip()[:120]}")
            ok = False
    return ok



def remove_label(name):
    """Best-effort REST label removal. A failure is logged, never fatal.

    Timeouts and a missing `gh` are caught too: this runs on the provenance
    hold path between posting the comment and applying `needs-human`, and a
    crash there left the claim unlabelled, to be re-swept and re-commented.
    Returns True if the label is gone (or never existed).
    """
    try:
        r = subprocess.run(["gh", "api", "-X", "DELETE",
                            f"/repos/{REPO}/issues/{NUM}/labels/{name}"],
                           capture_output=True, text=True, timeout=60)
    except (subprocess.TimeoutExpired, OSError) as e:
        print(f"::warning::could not remove label {name}: {e.__class__.__name__}: {str(e)[:120]}")
        return False
    if r.returncode != 0 and "Label does not exist" not in (r.stderr or ""):
        print(f"::warning::could not remove label {name}: {(r.stderr or '').strip()[:120]}")
        return False
    return True


def pr_provenance_problem(claimant, pr_repo, pr):
    """Why this claim may not be paid for this PR, or None if it may.

    The gate verified that the cited PR was merged and added docstrings, but
    never that the CLAIMANT wrote it or that it is ecosystem work. `main()`
    already fetched the PR `author` and then ignored it, so filing a claim that
    cited somebody else's merged docstring PR -- in any repository on GitHub --
    was paid to the claimant for work they did not do. Both checks fail closed:
    an unreadable author is not a match.

    scripts/bounty_payout.py re-runs this at payout time, which covers claims
    labelled payable before this check existed (main() skips those).
    """
    owner = pr_repo.split("/", 1)[0].lower()
    if owner not in ALLOWED_PR_OWNERS:
        return (f"{pr_repo} is not an Elyan Labs repository. Docstring bounties pay for "
                f"documentation merged into the project's own repositories.")
    pr_author = ((pr.get("author") or {}).get("login") or "").lower()
    if not claimant or not pr_author:
        return "the claim's author or the PR's author could not be determined."
    if pr_author != claimant.lower():
        return (f"{pr_repo} was authored by @{pr_author}, not by the claimant "
                f"@{claimant}. Docstring bounties are paid to the person who wrote the PR.")
    return None


def _flatten_slurped_pages(raw, list_key=None):
    """Normalize `gh api --paginate --slurp` output (or single-page dict/list) into a flat list.

    Raises GhError if the payload shape is not a valid list/dict of pages.
    """
    if raw is None:
        raise GhError("paginated gh api returned None")
    if isinstance(raw, dict):
        if list_key is not None:
            items = raw.get(list_key)
            if not isinstance(items, list):
                raise GhError(f"paginated gh api dict missing list key {list_key!r}")
            return list(items)
        raise GhError("expected list from paginated gh api, got dict")
    if isinstance(raw, list):
        if not raw:
            return []
        # `--paginate --slurp` on REST list endpoints returns `[[page1...], [page2...]]`
        # and on `search/issues` returns `[{"items": [...]}, {"items": [...]}]`.
        if list_key is not None and all(isinstance(page, dict) for page in raw):
            out = []
            for page in raw:
                page_items = page.get(list_key)
                if not isinstance(page_items, list):
                    raise GhError(f"paginated search page missing list key {list_key!r}")
                out.extend(page_items)
            return out
        if all(isinstance(page, list) for page in raw):
            out = []
            for page in raw:
                out.extend(page)
            return out
        if all(isinstance(item, dict) for item in raw):
            return list(raw)
    raise GhError(f"unexpected paginated gh api payload shape: {type(raw).__name__}")


def docstring_rtc_this_week(author, require_trusted_marker=True):
    """RTC this author has already been granted for docstrings in 7 days.

    Fixes #17054:
      1. Paginates BOTH `search/issues` and `/repos/{REPO}/issues/{n}/comments`
         with `--paginate --slurp` so claims beyond the first 100 or trusted
         markers pushed past comment 100 (page 2+) are never missed.
      2. Fails closed (`raise GhError` -> `needs-human` hold) if pagination
         fails or if a `docstring-verified` prior claim carries NO valid
         trusted `rtc-payout-amount` marker (`amt is None`), because a
         verified claim without a readable trusted marker is an unknown
         prior payout, not an authoritative zero.
    """
    since = (datetime.datetime.now(datetime.timezone.utc)
             - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
    q = (f"repo:{REPO} is:issue author:{author} label:docstring-verified "
         f"created:>{since}")
    res = gh(
        ["api", "--paginate", "--slurp", "-X", "GET", "search/issues", "-f", f"q={q}", "-f", "per_page=100"],
        None,
        strict=True,
    )
    items = _flatten_slurped_pages(res, list_key="items")
    total = 0.0
    for it in items:
        if not isinstance(it, dict) or "number" not in it:
            raise GhError("malformed issue entry in paginated search/issues response")
        if str(it.get("number")) == str(NUM):
            continue          # never count the claim being adjudicated
        raw_cs = gh(
            ["api", "--paginate", "--slurp", f"/repos/{REPO}/issues/{it['number']}/comments?per_page=100"],
            None,
            strict=True,
        )
        cs = _flatten_slurped_pages(raw_cs)
        amt = trusted_payout_amount(cs)
        if amt is None:
            if require_trusted_marker:
                raise GhError(
                    f"docstring-verified claim #{it['number']} has no trusted rtc-payout-amount marker; "
                    f"refusing to treat unknown prior payout as 0"
                )
            continue
        total += amt
    return round(total, 2)


def is_docstring_claim(title, body):
    t = (title or "").lower()
    if "docstring" in t or re.search(r'\bdocs?\s+batch\b', t):
        return True
    return "docstring" in (body or "").lower()[:400]


def count_added_docstrings(diff: str):
    """Return (docstring_lines, total_added, files_touched).

    Counts only ADDED lines that open a docstring. Continuation lines of a
    multi-line docstring are not counted, so one docstring is one unit however
    many lines it spans.
    """
    doc = total = 0
    files = []
    in_docstring = False
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            files.append(line[6:].strip())
            in_docstring = False
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        total += 1
        content = line[1:]
        if in_docstring:
            if '"""' in content or "'''" in content:
                in_docstring = False
            continue
        if DOCSTRING_OPEN.match(content):
            doc += 1
            stripped = content.strip()
            # One-liner if the closing quotes appear again on the same line.
            quote = '"""' if '"""' in stripped else "'''"
            if stripped.count(quote) < 2:
                in_docstring = True
    return doc, total, files


def main():
    if not NUM:
        print("ISSUE_NUMBER not set", file=sys.stderr)
        return 1
    iss = gh(["issue", "view", NUM, "-R", REPO,
              "--json", "title,body,labels,author,state"], {})
    if not iss:
        print(f"could not read {REPO}#{NUM}", file=sys.stderr)
        return 1
    labels = {l["name"] for l in iss.get("labels", [])}
    if {"bounty-eligible", "docstring-verified", "gate-processed"} & labels:
        print("already adjudicated; skipping")
        return 0
    title, body = iss.get("title", ""), iss.get("body") or ""
    if not is_docstring_claim(title, body):
        print("not a docstring claim; leaving for another gate")
        return 0

    m = PR_RE.search(body) or PR_RE.search(title)
    if not m:
        gh(["issue", "comment", NUM, "-R", REPO, "--body",
            "🤖 Docstring gate: no pull request URL found in this claim. Add the full "
            "`https://github.com/<owner>/<repo>/pull/<n>` link and it will be re-checked."], None)
        add_labels("needs-human")
        return 0
    pr_repo, pr_num = m.group(1), m.group(2)

    pr = gh(["pr", "view", pr_num, "-R", pr_repo,
             "--json", "state,additions,deletions,files,author,mergedAt"], {})
    if not pr:
        gh(["issue", "comment", NUM, "-R", REPO, "--body",
            f"🤖 Docstring gate: could not read {pr_repo}#{pr_num}. Flagged for a human."], None)
        add_labels("needs-human")
        return 0

    author = (iss.get("author") or {}).get("login", "")
    problem = pr_provenance_problem(author, pr_repo, pr)
    if problem:
        # Checked before the merge state so a claim on someone else's PR is
        # never parked as `awaiting-merge` and re-swept every few hours.
        gh(["issue", "comment", NUM, "-R", REPO, "--body",
            f"🤖 Docstring gate: this claim cannot be auto-paid: {problem}\n\n"
            f"Flagged for a human. If the gate has this wrong, say so here."], None)
        remove_label("awaiting-merge")
        add_labels("needs-human")
        print(f"provenance check failed for {REPO}#{NUM}: {problem}")
        return 0

    if pr.get("state") != "MERGED":
        gh(["issue", "comment", NUM, "-R", REPO, "--body",
            f"🤖 Docstring gate: {pr_repo}#{pr_num} is **{pr.get('state','OPEN').lower()}**, not merged.\n\n"
            f"Docstring bounties pay on merge, because until then the documentation is not in the "
            f"codebase. This claim is not closed — it will be re-checked automatically once the PR "
            f"lands, and you do not need to re-file it."], None)
        add_labels("awaiting-merge")
        print(f"{pr_repo}#{pr_num} not merged ({pr.get('state')}); waiting")
        return 0

    diff = gh_raw(["pr", "diff", pr_num, "-R", pr_repo])
    doc_count, total_added, files = count_added_docstrings(diff)
    claimed = None
    cm = COUNT_RE.search(body) or COUNT_RE.search(title)
    if cm:
        claimed = int(cm.group(1))

    amount = round(doc_count * RATE, 2)
    if doc_count == 0:
        gh(["issue", "comment", NUM, "-R", REPO, "--body",
            f"🤖 Docstring gate: {pr_repo}#{pr_num} is merged, but no added lines in it open a "
            f"docstring ({total_added} lines added in total). If the work is real and the gate has "
            f"misread it, say so here and a human will look."], None)
        add_labels("needs-human")
        return 0

    try:
        already = docstring_rtc_this_week(author) if author else 0.0
    except GhError as e:
        # Cannot establish prior earnings => cannot honour the cap => do not pay.
        # Failing closed is the whole point; the previous behaviour approved the
        # claim as though the contributor had earned nothing this week.
        gh(["issue", "comment", NUM, "-R", REPO, "--body",
            f"🤖 Docstring gate: verified **{doc_count} docstrings** in {pr_repo}#{pr_num}, but the "
            f"weekly-earnings lookup failed, so the {MAX_RTC_PER_WEEK:g} RTC/week cap cannot be "
            f"checked right now.\n\nHolding rather than approving — a failed lookup is not proof "
            f"that you have earned nothing. This retries automatically on the next sweep; you do "
            f"not need to do anything."], None)
        add_labels("needs-human")
        print(f"::error::earnings lookup failed, refusing to approve: {e}")
        return 0
    if already + amount > MAX_RTC_PER_WEEK:
        add_labels("weekly-cap-reached")
        gh(["issue", "comment", NUM, "-R", REPO, "--body",
            f"🤖 Docstring gate: verified **{doc_count} docstrings** in {pr_repo}#{pr_num} "
            f"(**{amount} RTC**), but this would take you to "
            f"**{round(already + amount, 2)} RTC** of docstring earnings in a rolling 7 days, "
            f"over the **{MAX_RTC_PER_WEEK:g} RTC/week** ceiling for this bounty type.\n\n"
            f"**The work is accepted and this claim is not closed.** It becomes payable again as "
            f"soon as the rolling window clears, and it will be picked up automatically. You do "
            f"not need to re-file it or do anything.\n\n"
            f"Why the ceiling exists: documentation bounties are unbounded by nature, since there "
            f"is always another file. The cap keeps one bounty type from consuming the pool, and "
            f"40 RTC/week is roughly the top of what any contributor earns across all bounty types. "
            f"It is not a judgement on the quality of your work, which has been consistently fine.\n\n"
            f"If you want higher-value work, the bounty board has open items at 7 to 35 RTC each "
            f"that are not rate-limited."], None)
        print(f"weekly cap: {author} at {already} + {amount} > {MAX_RTC_PER_WEEK}")
        return 0

    if amount > MAX_RTC:
        gh(["issue", "comment", NUM, "-R", REPO, "--body",
            f"🤖 Docstring gate: verified **{doc_count} docstrings** in {pr_repo}#{pr_num}, which at "
            f"{RATE} RTC each comes to {amount} RTC. That is above the {MAX_RTC} RTC auto-pay ceiling, "
            f"so it needs a human to release it. Nothing is wrong with the claim."], None)
        add_labels("needs-human")
        return 0

    note = ""
    if claimed is not None and claimed != doc_count:
        note = (f"\n\nYou claimed **{claimed}**; the diff contains **{doc_count}**. "
                f"Paying the verified number. If you think the gate has miscounted, say so and a "
                f"human will check — miscounts are usually arithmetic, not bad faith.")

    # Fail closed (#16471, reported by @antoleod 2026-09-04): add_labels() reports
    # REST label failures, but this caller used to discard that and announce
    # "verified" anyway. The payout sweep keys off the labels, so a claim could be
    # publicly verified and never paid. Hold instead, and exit non-zero so the run
    # is red and the next sweep retries.
    if not add_labels("bounty-eligible", "docstring-verified"):
        gh(["issue", "comment", NUM, "-R", REPO, "--body",
            f"⏸️ 🤖 **Docstring gate: checks passed, but the payable labels could not be applied** "
            f"(GitHub label API error), so this is **held**, not verified. PR {pr_repo}#{pr_num} is "
            f"merged with **{doc_count}** docstrings → **{amount} RTC** once a human or the next "
            f"sweep applies `bounty-eligible` + `docstring-verified`. Nothing is wrong with the "
            f"claim; the gate is refusing to say 'verified' about a state it did not create."], None)
        add_labels("needs-human")
        print(f"::error::labels not applied on {REPO}#{NUM}; held, not verified")
        return 1
    gh(["issue", "comment", NUM, "-R", REPO, "--body",
        f"✅ 🤖 **Docstring gate: verified.**\n\n"
        f"- PR {pr_repo}#{pr_num} is **merged**\n"
        f"- Files: `{', '.join(files[:4]) or 'n/a'}`\n"
        f"- Added lines opening a docstring: **{doc_count}** (of {total_added} added lines)\n"
        f"- Rate {RATE} RTC each → **{amount} RTC**{note}\n\n"
        f"<!-- rtc-payout-amount: {amount} -->\n"
        f"Queued for payout. The balance moves after the standard confirmation window, not on this "
        f"comment."], None)
    print(f"verified {doc_count} docstrings -> {amount} RTC on {REPO}#{NUM}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
