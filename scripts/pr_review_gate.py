#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
PR-Review Bounty Gate — on-arrival adjudication of Bounty #73 code-review claims.

Runs per newly-opened/edited issue. For a code-review claim it verifies, against
the (public) Rustchain repo, that the claimant was the FIRST substantive reviewer
of the referenced PR, within the per-contributor cap. Conservative:
  - clear NOT-FIRST / rubber-stamp / over-cap  -> close (not planned) + comment
  - eligible                                   -> label 'bounty-eligible' + comment
  - ambiguous / no PR ref / non-native wallet  -> label 'needs-human' (no close)
Idempotent: skips issues already labeled/closed by the gate.

Hardened against silent-success failures (#16471, #16710):
  1. `api()` distinguishes genuine HTTP 404/410 (`None`) from transient/rate-limit
     HTTP 403/429/5xx, network errors, and malformed JSON (`GateTransientError`),
     so a transient failure on `/pulls/{pr}/comments` never masquerades as 0 inline
     comments (auto-closing a valid claim) and a transient failure on `/search/issues`
     never masquerades as `total_count: 0` (bypassing the 15-review contributor cap).
  2. `gate-processed` is applied ONLY after adjudication succeeds, never before
     read-only API calls complete (#16710).
  3. `/pulls/{pr}/reviews` and `/pulls/{pr}/comments` are paginated (`per_page=100`)
     so PRs with >30 reviews or >100 inline comments never silently drop reviews.
  4. Unhandled `GateTransientError` / `Exception` exits non-zero (`sys.exit(1)`)
     so failed gate runs surface visibly in GitHub Actions and can be retried.
"""
import os, re, json, sys, urllib.request, urllib.error

TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO = os.environ.get("GH_REPO", "Scottcjn/rustchain-bounties")
TARGET = os.environ.get("TARGET_REPO", "Scottcjn/Rustchain")
NUM = os.environ.get("ISSUE_NUMBER", "")
CAP = int(os.environ.get("CAP", "15"))
RATE = os.environ.get("RATE_RTC", "3")
API = "https://api.github.com"


class GateTransientError(RuntimeError):
    """Raised when a GitHub API request fails transiently or returns unparseable JSON."""


def api(path, method="GET", data=None):
    req = urllib.request.Request(
        f"{API}{path}",
        method=method,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "pr-review-gate",
        },
    )
    if data is not None:
        req.data = json.dumps(data).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            try:
                return json.loads(raw or b"null")
            except json.JSONDecodeError as e:
                raise GateTransientError(f"Malformed JSON from {method} {path}: {e}") from e
    except urllib.error.HTTPError as e:
        if method == "GET" and e.code in (404, 410):
            return None
        raise GateTransientError(f"HTTP {e.code} on {method} {path}") from e
    except urllib.error.URLError as e:
        raise GateTransientError(f"Network error on {method} {path}: {e}") from e


def api_paginated_list(base_path, max_pages=10):
    """Paginate a GitHub REST list endpoint (`per_page=100`).

    Returns `None` if the resource returns HTTP 404/410 on page 1, or the complete
    list across pages. Raises `GateTransientError` on any transient/non-list response.
    """
    sep = "&" if "?" in base_path else "?"
    items = []
    for page in range(1, max_pages + 1):
        url = f"{base_path}{sep}per_page=100&page={page}"
        res = api(url, method="GET")
        if res is None:
            return None if page == 1 else items
        if not isinstance(res, list):
            raise GateTransientError(f"Expected list from {url}, got {type(res).__name__}")
        items.extend(res)
        if len(res) < 100:
            break
    return items


def is_review_claim(title):
    t = title.lower()
    return ("review" in t) and ("pr " in t or "code review" in t or "#73" in t or "pr#" in t or "pr #" in t)


def pr_ref(title, body):
    """Resolve the claimed PR as (repo_fullname_or_None, number_str_or_None)."""
    for s in (title, body or ""):
        m = re.search(r"github\.com/([\w.-]+/[\w.-]+)/pull/(\d{1,6})", s)
        if m:
            return m.group(1), m.group(2)
    for s in (title, body or ""):
        m = re.search(r"(?:\bPR\s*#?\s*|pull/)(\d{1,6})", s, re.IGNORECASE)
        if m:
            return None, m.group(1)
    for s in (title, body or ""):
        stripped = re.sub(r"(?i)bounty\s*#\s*\d{1,6}", "", s)
        m = re.search(r"#(\d{3,6})", stripped)
        if m:
            return None, m.group(1)
    return None, None


def native_wallet(body):
    b = body or ""
    if re.search(r"\bRTC[0-9a-fA-F]{40}\b", b) or re.search(r"(?i)miner[_\-]?id", b):
        return True
    if re.search(r"\b[1-9A-HJ-NP-Za-km-z]{32,44}\b", b) and "rtc" not in b.lower():
        return False
    return None


_SUBSTANTIVE_MARKER_RE = re.compile(
    r"(?:"
    r"\b(?:ref|refs|reference|finding|findings|bug|issue|risk|guard|"
    r"security|vuln|vulnerability|regression|edge case|missing|broken|"
    r"leak|panic|null|deref|injection|xss|csrf|race|deadlock|overflow)\b"
    r"|"
    r"`[^`]*\.[a-zA-Z0-9]{1,5}`"
    r"|"
    r"\b[a-zA-Z0-9_./-]+\.(?:py|js|ts|go|rs|java|kt|swift|c|cpp|h|hpp|"
    r"md|yaml|yml|json|toml|sh|bash)\b"
    r"|"
    r"\bL:?\s*\d{1,4}\b"
    r"|"
    r"\bline\s*\d{1,4}\b"
    r"|"
    r"```"
    r")",
    re.IGNORECASE,
)

_RUBBER_STAMP_PHRASES = (
    "lgtm", "lgtm!", "great work", "great contribution", "great work on this",
    "nice work", "nice!", "nice job", "awesome", "awesome!",
    "looks good", "looks great", "ship it", "shipit", "approved!",
    "excellent", "excellent contribution", "appreciate", "appreciated",
    "appreciate the work", "thanks", "thanks!", "thanks for", "thank you",
    "thx", "thnx", "great pr", "great review", "great catch", "great find",
    "good work", "good job", "well done", "wonderful", "fantastic", "amazing",
)

_RUBBER_STAMP_RE = re.compile(
    r"^\s*(?:" + "|".join(re.escape(p) for p in _RUBBER_STAMP_PHRASES) + r")"
    r"[\s\W"
    r"\U0001F300-\U0001FAFF"
    r"\U0001F600-\U0001F64F"
    r"\U0001F680-\U0001F6FF"
    r"\U0001F1E0-\U0001F1FF"
    r"\u2600-\u27BF"
    r"]*$",
    re.IGNORECASE | re.UNICODE,
)

_EMOJI_ONLY_RE = re.compile(
    r"^[\s\W"
    r"\U0001F300-\U0001FAFF"
    r"\U0001F600-\U0001F64F"
    r"\U0001F680-\U0001F6FF"
    r"\U0001F1E0-\U0001F1FF"
    r"\u2600-\u27BF"
    r"]+$",
    re.UNICODE,
)


def is_substantive_review(review, inline_count=0):
    if inline_count and inline_count > 0:
        return True
    body = (review.get("body") or "").strip()
    if not body:
        return False
    if _SUBSTANTIVE_MARKER_RE.search(body):
        return True
    if _EMOJI_ONLY_RE.match(body):
        return False
    if _RUBBER_STAMP_RE.match(body):
        return False
    if len(body) >= 80:
        return True
    return False


def comment(n, body):
    api(f"/repos/{REPO}/issues/{n}/comments", "POST", {"body": body})


def add_label(n, lab):
    api(f"/repos/{REPO}/issues/{n}/labels", "POST", {"labels": [lab]})


def close(n, reason_comment):
    comment(n, reason_comment)
    api(f"/repos/{REPO}/issues/{n}", "PATCH", {"state": "closed", "state_reason": "not_planned"})


def main():
    iss = api(f"/repos/{REPO}/issues/{NUM}")
    if not iss or iss.get("state") != "open":
        return 0
    labels = {l["name"] for l in iss.get("labels", [])}
    if {"bounty-eligible", "needs-human", "gate-processed"} & labels:
        return 0
    title = iss.get("title", "")
    body = iss.get("body") or ""
    author = iss["user"]["login"]
    if not is_review_claim(title):
        return 0

    claim_repo, pr = pr_ref(title, body)
    if not pr:
        add_label(NUM, "needs-human")
        add_label(NUM, "gate-processed")
        comment(
            NUM,
            "🤖 Gate: couldn't find a single PR reference. Per **Bounty #73**, file one claim per PR with `PR #<number>` (a full PR URL is best). Flagged for human review.",
        )
        return 0

    target = TARGET
    if claim_repo:
        if claim_repo.lower().startswith(TARGET.split("/")[0].lower() + "/"):
            target = claim_repo
        else:
            add_label(NUM, "needs-human")
            add_label(NUM, "gate-processed")
            comment(
                NUM,
                f"🤖 Gate: claim references a PR outside the maintainer's repos ({claim_repo}#{pr}). Flagged for human review.",
            )
            return 0

    if native_wallet(body) is False:
        close(
            NUM,
            "🤖 Gate: payout must be a **native RTC wallet** (`RTC…`) — RTC has no off-ramp, no Solana/ETH bridge. Reopen with a native wallet.",
        )
        add_label(NUM, "gate-processed")
        return 0

    reviews = api_paginated_list(f"/repos/{target}/pulls/{pr}/reviews")
    if reviews is None:
        add_label(NUM, "needs-human")
        add_label(NUM, "gate-processed")
        comment(
            NUM,
            f"🤖 Gate: couldn't read reviews for {target}#{pr} (private/deleted?). Flagged for human review.",
        )
        return 0

    rv = [r for r in reviews if r.get("submitted_at")]
    rv.sort(key=lambda r: r["submitted_at"])

    inl = api_paginated_list(f"/repos/{target}/pulls/{pr}/comments")
    if inl is None:
        raise GateTransientError(f"Pull request {target}#{pr} reviews readable but comments returned 404")

    author_inline = {}
    for c in inl:
        login = (c.get("user") or {}).get("login")
        if login:
            author_inline[login] = author_inline.get(login, 0) + 1

    substantive = [
        r for r in rv
        if is_substantive_review(r, inline_count=author_inline.get(r["user"]["login"], 0))
    ]
    first = substantive[0]["user"]["login"] if substantive else None
    body_len = max((len(r.get("body") or "") for r in rv if r["user"]["login"] == author), default=0)
    inline = author_inline.get(author, 0)

    if first != author:
        close(
            NUM,
            f"🤖 Gate (Bounty #73 — first substantive review only): {target}#{pr} was first reviewed by **{first or 'someone else'}** (after filtering rubber-stamps), not @{author}. Path back: review PRs where you're the first reviewer.",
        )
        add_label(NUM, "gate-processed")
        return 0

    if inline == 0 and body_len < 120:
        close(
            NUM,
            f"🤖 Gate: your review of {target}#{pr} has no inline comments and no substantive summary — Bounty #73 requires a **substantive line-level review**, not a bare approval.",
        )
        add_label(NUM, "gate-processed")
        return 0

    elig = api(f"/search/issues?q=user:Scottcjn+label:bounty-eligible+author:{author}+type:issue")
    if not isinstance(elig, dict) or "total_count" not in elig:
        raise GateTransientError(f"Invalid search/issues response while checking cap for {author}")

    if elig.get("total_count", 0) >= CAP:
        close(
            NUM,
            f"🤖 Gate: @{author} has reached the **{CAP} eligible reviews/contributor** cap (Bounty #73). Quality over volume — thanks!",
        )
        add_label(NUM, "gate-processed")
        return 0

    add_label(NUM, "bounty-eligible")
    add_label(NUM, "gate-processed")
    comment(
        NUM,
        f"✅ 🤖 Gate: **verified eligible** — @{author} is the first substantive reviewer of {target}#{pr}. **{RATE} RTC** pending payout (native `RTC…` wallet if not on file).",
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"gate error: {e}", file=sys.stderr)
        raise SystemExit(1)
