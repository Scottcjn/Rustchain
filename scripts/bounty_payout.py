#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Bounty payout — pays verified-eligible code-review claims as wallets confirm.

Completes the pipeline: the PR-review gate labels a claim `bounty-eligible`
(or a maintainer comments "Verified eligible"); when the claimant adds a native
RTC wallet, this run pays 3 RTC from founder_community and closes the claim.

If the claim has no native `RTC[0-9a-fA-F]{40}` address, the script falls
back to a GitHub handle from the issue body or a recent `Wallet: <handle>`
comment - matching the rtc-reward action's handle-fallback (PR #13394).
Bots are excluded so automation cannot farm rewards.

SAFETY:
  - pays ONLY verified-eligible claims (gate label or "Verified eligible" comment)
  - native RTC wallet preferred; handle fallback is opt-in
  - handle fallback excludes bot accounts (`type == 'Bot'` or `[bot]` suffix)
  - idempotency_key=bounty73-claim-<n> + trusted 'RTC-AutoPay-Confirmed' marker => never double-pays
    (the marker only counts from a paying identity, in the structured form; see payment_markers.py)
  - MAX_PER_RUN aggregate cap (default 40) — hard stop per run, surfaced in log
Env: GITHUB_TOKEN, RTC_ADMIN_KEY, RTC_VPS_HOST, GH_REPO, RATE_RTC(3), MAX_PER_RUN(40),
     RUSTCHAIN_TLS_PIN_SHA256 (SHA-256 of the node's DER certificate; required for the
       self-signed node, e.g. `openssl s_client -connect HOST:443 </dev/null |
       openssl x509 -outform DER | sha256sum`; update it when the cert rotates),
     RUSTCHAIN_CA_BUNDLE (optional CA file when not pinning; default = system CAs),
     RUSTCHAIN_PAYOUT_INSECURE (unset = authenticated HTTPS only; "1" allows unverified
       TLS and the plaintext :8099 fallback -- the admin key is then exposed).
"""
import os, re, json, time, subprocess, ssl, hashlib, hmac, http.client, urllib.parse, urllib.request, urllib.error, importlib.util

def _load_second_act():
    """Load the payout second-act hook. Optional: absence must not break payouts."""
    try:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "second_act.py")
        spec = importlib.util.spec_from_file_location("second_act", p)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m
    except Exception as e:
        print(f"::warning::second_act hook unavailable ({e}); payouts continue without it")
        class _Null:
            @staticmethod
            def build(*a, **k): return ""
        return _Null()

_second_act = _load_second_act()

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import payment_markers  # noqa: E402  (shared "already paid" rules; must not be optional)
import docstring_gate  # noqa: E402  (provenance rule for docstring claims; must not be optional)
TOKEN=os.environ["GITHUB_TOKEN"]; ADMIN=os.environ["RTC_ADMIN_KEY"]
HOST=os.environ.get("RTC_VPS_HOST","50.28.86.131"); REPO=os.environ.get("GH_REPO","Scottcjn/rustchain-bounties")
RATE=float(os.environ.get("RATE_RTC","3"))
# Hard ceiling re-enforced at payout time, independent of any gate.
MAX_CLAIM_RTC=float(os.environ.get("MAX_CLAIM_RTC","25")); MAXRUN=int(os.environ.get("MAX_PER_RUN","40"))
FROM="founder_community"; PORT="8099"
WALLET_RE=re.compile(r'\bRTC[0-9a-fA-F]{40}\b')
# Matches `Wallet: <handle-or-address>` (case-insensitive, Markdown-tolerant).
# Tolerates:
#   - leading Markdown headers (`## Wallet: handle`)
#   - bullet list markers (`- **Wallet:** handle`)
#   - bold markers (`**Wallet:** handle` / `**Wallet**: handle`)
#   - inline code (`` `handle` ``)
#   - trailing parentheses / notes (`(GitHub handle)`)
#   - trailing annotation (`- please send RTC here`)
# The implementation strips `**` markers per-line and matches against
# the simplified pattern; this is much more reliable than trying to
# support every bold/colon interleaving in a single regex.
HANDLE_RE=re.compile(
    r'(?im)^\s*[-*]?\s*(?:#+\s+)?'
    r'(?:wallet|wallet\s+address|wallet\s+id|recipient)'
    r'\s*[:=]\s*'
    r'`?([A-Za-z0-9][A-Za-z0-9_-]{0,38})`?'
    r'(?:\s*\([^)]*\))?'
    r'(?:\s*[-—]\s*\S.*)?'
    r'\s*$'
)
GH_LOGIN_RE=re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,38}$')
BOT_SUFFIX_RE=re.compile(r'\[bot\]$', re.IGNORECASE)
# Known non-human logins that should be excluded even without an explicit
# type/suffix marker. Keep the set small and verifiable from public GitHub
# conventions (CI bots, automation accounts, etc.).
KNOWN_BOT_LOGINS=frozenset({
    "github-actions", "github-actions[bot]",
    "dependabot", "dependabot[bot]",
    "renovate", "renovate[bot]",
    "codecov", "codecov[bot]",
    "deepsource-io[bot]", "imgbot[bot]", "netlify[bot]",
})



# Identities whose word can authorize money movement. Everything reachable from
# a public issue comment is UNTRUSTED: anyone with a GitHub account can write a
# comment on a public repo, so a comment can never be an authorization by itself.
TRUSTED_AUTHORS = frozenset({"scottcjn", "sophiaeagent-beep", "github-actions[bot]", "github-actions"})


def _is_trusted(login):
    return bool(login) and login.lower() in TRUSTED_AUTHORS


def _find_handle_in_text(text):
    """Return the first handle found on any line of `text`, or None.

    Strips Markdown bold (`**`) markers per-line before matching so
    `**Wallet:** handle` and `**Wallet**: handle` both work, and
    accepts bullet/header prefixes. The first matching line wins.
    """
    if not text:
        return None
    for raw_line in text.splitlines():
        line = raw_line.replace("**", "").strip()
        m = HANDLE_RE.match(line)
        if m:
            return m.group(1)
    return None
class CanonicalRegistryError(RuntimeError):
    """docs/CLAIMANTS.md exists but could not be read/parsed.

    Never degrade this into an empty map: a registered contributor would then
    fall through to an older wallet or bare handle and be paid to the WRONG
    destination, silently, on a green run.
    """


def _load_canonical_wallets():
    """Parse docs/CLAIMANTS.md into {handle_lower: native_RTC_wallet}.

    Canonical registry: a handle listed here is ALWAYS paid to its registered
    native wallet, regardless of what an individual claim body says. Only native
    `RTC[0-9a-fA-F]{40}` rows are honored.

    Fail-closed contract (reported by @Nish916 under #16471):
      - File genuinely ABSENT -> empty map is fine; no registry is configured,
        so resolution falls back to per-claim parsing.
      - File PRESENT but unreadable/unparseable (encoding, OS, partial read) ->
        raise CanonicalRegistryError. Returning a partial/empty map here would
        violate the "canonical registry ALWAYS wins" invariant and misroute a
        registered contributor's payout while the run still reports success.
    """
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "CLAIMANTS.md")
    out = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if "|" not in line:
                    continue
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if len(cells) < 2:
                    continue
                handle, wallet = cells[0], cells[1]
                m = WALLET_RE.search(wallet)
                if handle and m and not handle.lower().startswith(("github handle", "---")):
                    out[handle.lower()] = m.group(0)
    except FileNotFoundError:
        # No registry configured for this repo -> per-claim resolution only.
        return {}
    except Exception as e:
        # The file exists but could not be read/parsed. Fail closed: abort
        # before any transfer rather than pay a registered contributor to a
        # stale wallet or bare handle.
        raise CanonicalRegistryError(
            f"docs/CLAIMANTS.md exists but could not be parsed: "
            f"{e.__class__.__name__}: {e}"
        ) from e
    return out


CANONICAL_WALLETS = _load_canonical_wallets()


class GhError(RuntimeError):
    """A `gh` invocation failed. Never swallow this into an empty result."""


def gh(args, _check=True):
    """Run `gh`, raising on failure rather than returning empty stdout.

    The previous version returned `.stdout` and ignored the return code, so an
    auth, rate-limit or transport failure produced an empty string, `_list()`
    turned that into `[]`, and the payout run completed GREEN having enumerated
    zero candidates and paid nobody. A workflow that goes green while paying
    nothing is indistinguishable from a quiet day.
    """
    p = subprocess.run(["gh"]+args,capture_output=True,text=True,timeout=60,
        env={**os.environ,"GH_TOKEN":TOKEN})
    if _check and p.returncode != 0:
        raise GhError(f"gh {' '.join(args[:3])} exited {p.returncode}: {(p.stderr or '').strip()[:200]}")
    return p.stdout
class TlsPinMismatch(RuntimeError):
    """The node presented a certificate other than the pinned one. Never retried."""


def _tls_pin():
    """RUSTCHAIN_TLS_PIN_SHA256 normalised to lowercase hex, or "" if unset.

    Accepts `sha256sum` output, `openssl x509 -fingerprint -sha256` output
    (`SHA256 Fingerprint=AB:CD:...`) or bare hex.
    """
    raw=os.environ.get("RUSTCHAIN_TLS_PIN_SHA256","").strip()
    if "=" in raw: raw=raw.split("=",1)[1]
    raw=raw.split()[0] if raw.split() else ""
    pin=raw.replace(":","").lower()
    if pin and not re.fullmatch(r"[0-9a-f]{64}",pin):
        raise ValueError("RUSTCHAIN_TLS_PIN_SHA256 must be the SHA-256 of the node's DER certificate (64 hex chars)")
    return pin


def _tls_context(pin, insecure):
    """How the HTTPS leg authenticates the node before X-Admin-Key is sent.

    The node serves a self-signed certificate, so CA verification cannot work
    and the old code simply turned verification OFF (CERT_NONE). Anyone
    on-path could then terminate TLS with any certificate and read the admin
    key -- the plaintext-fallback fix alone only stopped passive sniffing.
      - pin set    : chain/hostname checks off (self-signed), but the leaf
                     certificate must hash to the pin (checked in _post
                     after the handshake, BEFORE any byte of the request).
      - INSECURE=1 : legacy unauthenticated TLS, with a loud warning.
      - neither    : normal CA + hostname verification (RUSTCHAIN_CA_BUNDLE
                     may name a CA file). Against a self-signed node this
                     fails closed: nothing is sent.
    """
    if pin or insecure:
        ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
        return ctx
    return ssl.create_default_context(cafile=os.environ.get("RUSTCHAIN_CA_BUNDLE") or None)


def _post(url, body):
    headers={"Content-Type":"application/json","X-Admin-Key":ADMIN}
    u=urllib.parse.urlsplit(url)
    if u.scheme=="http":
        # Only reachable through the RUSTCHAIN_PAYOUT_INSECURE=1 fallback.
        req=urllib.request.Request(url,data=body,method="POST",headers=headers)
        with urllib.request.urlopen(req,timeout=30) as r: return json.loads(r.read())
    if u.scheme!="https":
        raise ValueError(f"refusing non-http(s) payout URL scheme {u.scheme!r}")
    pin=_tls_pin(); insecure=os.environ.get("RUSTCHAIN_PAYOUT_INSECURE")=="1"
    if not pin and insecure:
        print("::warning::RUSTCHAIN_PAYOUT_INSECURE=1 and no RUSTCHAIN_TLS_PIN_SHA256 — "
              "node certificate NOT verified; admin key is exposed to an active on-path attacker")
    conn=http.client.HTTPSConnection(u.hostname,u.port or 443,timeout=30,context=_tls_context(pin,insecure))
    try:
        conn.connect()
        if pin:
            der=conn.sock.getpeercert(binary_form=True) or b""
            got=hashlib.sha256(der).hexdigest()
            if not hmac.compare_digest(got,pin):
                raise TlsPinMismatch(f"node certificate sha256 {got[:16]}... does not match RUSTCHAIN_TLS_PIN_SHA256; admin key NOT sent")
        path=(u.path or "/")+(f"?{u.query}" if u.query else "")
        conn.request("POST",path,body=body,headers=headers)
        r=conn.getresponse(); data=r.read()
        if r.status>=400:
            raise urllib.error.HTTPError(url,r.status,f"HTTP {r.status}: {data[:160]!r}",r.headers,None)
        return json.loads(data)
    finally:
        conn.close()
def _docstring_claim_problem(body, title, claimant):
    """Why a docstring-verified claim must NOT be paid now, or None if it may.

    The docstring gate only started checking provenance (PR in an allowed
    repository, PR authored by the claimant) on 2026-09-26, and it skips any
    claim that is already labelled. Claims it verified before then -- possibly
    for someone else's PR, or a PR in any repository on GitHub -- still carry
    `docstring-verified` + a trusted amount marker. Re-checking here, at the
    moment money moves, covers those claims without relying on a manual audit.
    Uses the gate's own PR_RE (same first match) and pr_provenance_problem.
    Fails closed: an unreadable or unmerged PR is not payable.
    """
    m = docstring_gate.PR_RE.search(body or "") or docstring_gate.PR_RE.search(title or "")
    if not m:
        return "no pull request URL in the claim"
    pr_repo, pr_num = m.group(1), m.group(2)
    try:
        pr = json.loads(gh(["pr","view",pr_num,"-R",pr_repo,"--json","author,state"]) or "{}")
    except (GhError, ValueError) as e:
        return f"could not read {pr_repo}#{pr_num}: {str(e)[:120]}"
    if not isinstance(pr, dict):
        return f"could not read {pr_repo}#{pr_num}"
    if pr.get("state") != "MERGED":
        return f"{pr_repo}#{pr_num} is not merged"
    return docstring_gate.pr_provenance_problem(claimant, pr_repo, pr)


# Validate the pin once, up front: a malformed pin must stop the run, not
# surface later as a per-transfer error that could fall through to plaintext.
_tls_pin()


def transfer(to,memo,idem,amount=None):
    """Return (ok, response_or_error).

    FIX (#16390): the previous version returned True whenever `_post` did not
    raise. A transport-level success carrying an application-level refusal
    (HTTP 200 with `{"ok": false, ...}`, e.g. insufficient balance or a
    rejected wallet) was therefore recorded as PAID — the claim got closed and
    publicly confirmed with no RTC sent. Success now requires `ok` to be true
    in the response body.

    A server that answers and declines is NOT retried against the fallback
    endpoint: it already processed the request, so re-posting risks a second
    debit under a different URL.
    """
    body=json.dumps({"from_miner":FROM,"to_miner":to,"amount_rtc":(RATE if amount is None else amount),"memo":memo,"idempotency_key":idem}).encode()
    # node gunicorn is bound to 127.0.0.1:8099 (nginx-only) — reach it via the
    # nginx HTTPS endpoint (the working path).
    #
    # SECURITY: the plaintext http://HOST:8099 fallback used to be tried on ANY
    # HTTPS exception, re-sending X-Admin-Key in the clear. Anyone able to make
    # port 443 fail (drop/reset it on-path) could therefore downgrade the
    # request and read the admin key off the wire. It is now opt-in via
    # RUSTCHAIN_PAYOUT_INSECURE=1, the same switch scripts/auto-pay.py uses.
    # The HTTPS leg itself authenticates the node (certificate pin or CA
    # verification, see _tls_context); it no longer accepts any certificate.
    urls=[f"https://{HOST}/wallet/transfer"]
    if os.environ.get("RUSTCHAIN_PAYOUT_INSECURE")=="1":
        print("::warning::RUSTCHAIN_PAYOUT_INSECURE=1 — plaintext fallback enabled; admin key may be sent over HTTP")
        urls.append(f"http://{HOST}:{PORT}/wallet/transfer")
    last="no_endpoint_attempted"
    for url in urls:
        try:
            resp=_post(url,body)
        except TlsPinMismatch as e:
            # Someone other than the node answered on 443. Falling back to
            # plaintext would hand them the key anyway: stop here.
            return False,f"tls_pin_mismatch:{str(e)[:160]}"
        except Exception as e:
            last=str(e)[:160]
            continue
        if not isinstance(resp,dict) or not resp.get("ok"):
            # Server answered and refused. Do not try the other endpoint.
            return False,f"server_declined:{str(resp)[:180]}"
        return True,resp
    return False,last
def _is_bot_login(login, user_obj):
    """Return True if the comment/author appears to be a bot.

    Accepts both REST (`user`) and GraphQL (`author`) comment shapes from
    `gh issue view --json comments`. Falls back to login-string heuristics
    (suffix `[bot]`, known CI-bot logins) when the type is not declared.
    """
    # `user` field is the REST shape; `author` field is the GraphQL shape
    # returned by `gh issue view --json comments`. Either may be present.
    for obj in (user_obj,):
        if obj and isinstance(obj, dict):
            t = obj.get("type")
            if t == "Bot":
                return True
            if t and t != "User":
                # Unknown type (e.g. "Bot" with a capital "B" or
                # "Organization"). Be conservative.
                if t.lower() == "bot":
                    return True
            # GraphQL GraphType `__typename` and the `is_bot` field
            # are sometimes exposed. Trust them when seen.
            if obj.get("is_bot") is True:
                return True
            if obj.get("__typename") == "Bot":
                return True
    if login:
        if BOT_SUFFIX_RE.search(login):
            return True
        if login.lower() in KNOWN_BOT_LOGINS:
            return True
    return False


def _comment_author_login(c):
    """Return (login, user_obj) for a comment in either REST or GraphQL shape.

    `gh issue view --json comments` returns `author` (GraphQL); some other
    call paths return `user` (REST). The previous version only checked
    `user`, so it silently treated every GraphQL comment as a non-bot.
    """
    if not isinstance(c, dict):
        return None, None
    # GraphQL shape (from `gh issue view --json comments`).
    a = c.get("author")
    if isinstance(a, dict):
        return a.get("login"), a
    # REST shape (fallback; e.g. from custom REST endpoints).
    u = c.get("user")
    if isinstance(u, dict):
        return u.get("login"), u
    return None, None


PAYOUT_MARKER_RE = re.compile(r'<!--\s*rtc-payout-amount:\s*([\d.]+)\s*-->')
PAYOUT_AMOUNT_RE = re.compile(r'\d+(?:\.\d+)?')


def _trusted_marker_amount(comments, where=""):
    """The amount a docstring claim's thread authoritatively carries, or None.

    Only markers written by a trusted author count, and the LAST valid one wins.
    A trusted marker whose amount is not a plain number (`...`, `1.2.3`) is
    logged and ignored: it used to reach `float()` and raise, killing the whole
    payout run for every claim behind it. Ignoring it is fail-closed here -- a
    claim with no valid trusted marker is skipped, never paid.

    scripts/docstring_gate.py has a copy of this (`trusted_payout_amount`) for
    its weekly cap; the two must agree, and a test runs the same threads
    through both.
    """
    amount = None
    for c in comments or []:
        if not _is_trusted(_comment_author_login(c)[0]):
            continue
        m = PAYOUT_MARKER_RE.search(c.get("body") or "")
        if not m:
            continue
        if not PAYOUT_AMOUNT_RE.fullmatch(m.group(1)):
            print(f"::warning::{where} ignoring unparseable trusted payout marker {m.group(1)!r}")
            continue
        amount = float(m.group(1))
    return amount


def _looks_like_handle(token):
    if not token:
        return False
    if WALLET_RE.fullmatch(token):
        return False
    if not GH_LOGIN_RE.match(token):
        return False
    bad = {"address", "wallet", "id", "tbd", "tba", "n/a", "none", "null",
           "the", "my", "your", "this", "pending", "see", "comment", "issue"}
    return token.lower() not in bad
def resolve_wallet(issue_body, comments, claimant_login=None):
    """Return (wallet, source) where source is 'canonical' | 'native' | 'handle' | None.
    Resolution order:
      0. Canonical registry (docs/CLAIMANTS.md) for claimant_login — ALWAYS wins
         so a registered contributor's payouts can't fragment across handle/wallet.
      1. Native `RTC[0-9a-fA-F]{40}` in the issue body (preferred).
      2. `Wallet: <handle>` line in the issue body, when it parses as a
         plausible GitHub login.
      3. Most recent non-bot `Wallet: <handle>` comment.
      4. `claimant_login` (the PR author) if it is a plausible login and not
         a bot. Caller is responsible for bot-excluding.
    """
    # 0. Canonical registry — registered handle always maps to its native wallet.
    if claimant_login and claimant_login.lower() in CANONICAL_WALLETS:
        return CANONICAL_WALLETS[claimant_login.lower()], "canonical"
    body = issue_body or ""
    wm = WALLET_RE.search(body)
    if wm:
        return wm.group(0), "native"
    hm = _find_handle_in_text(body)
    if hm and _looks_like_handle(hm):
        return hm, "handle"
    if comments:
        for c in reversed(comments):
            author, user_obj = _comment_author_login(c)
            if _is_bot_login(author, user_obj):
                continue
            # Only the CLAIMANT may name their own payout destination, or a
            # trusted maintainer may set it for them. Previously any non-bot
            # commenter could post "Wallet: attacker-handle" on someone else's
            # claim and silently redirect the payout to themselves.
            if not (claimant_login and author
                    and author.lower() == claimant_login.lower()) and not _is_trusted(author):
                continue
            cb = c.get("body") or ""
            m = _find_handle_in_text(cb)
            if m and _looks_like_handle(m):
                return m, "handle"
    if claimant_login and _looks_like_handle(claimant_login) and not _is_bot_login(claimant_login, None):
        return claimant_login, "handle"
    return None, None
def _list(extra):
    try:
        return json.loads(gh(["issue","list","-R",REPO,"--state","open",
                              "--json","number,title,labels"]+extra) or "[]")
    except json.JSONDecodeError:
        return []

# Candidate set = every gate-labelled claim UNION a recent-window sweep.
#
# The recent sweep alone (the previous behaviour, --limit 400) silently
# excluded any claim outside the 400 newest open issues. With a backlog in
# the thousands that meant a gate-verified claim could age past the window
# and become unpayable forever, with no error anywhere — the claim just
# stopped being considered. The label pass makes eligibility, not recency,
# decide what gets paid; the recent pass still catches claims made eligible
# by a maintainer "Verified eligible" comment rather than the label.
issues=_list(["--label","bounty-eligible","--limit","1000"])
_seen={i["number"] for i in issues}
issues += [i for i in _list(["--limit","400"]) if i["number"] not in _seen]
print(f"bounty-payout: {len(issues)} candidate issues "
      f"({len(_seen)} label-eligible, {len(issues)-len(_seen)} from recent window)")
paid=0; total=0.0
for i in issues:
    if paid>=MAXRUN: print(f"::notice::MAX_PER_RUN={MAXRUN} reached — stopping; remaining eligible will pay next run."); break
    t=i["title"].lower()
    labels_pre={l["name"] for l in i.get("labels",[])}
    # Review claims are title-matched; docstring claims are label-matched.
    #
    # This filter used to be review-only, so docstring claims adjudicated by
    # the docstring gate were labelled `bounty-eligible` and then silently
    # skipped here -- eligible, verified, and never paid. Any future gate that
    # marks a claim payable must be represented here too, or it recreates the
    # same dead end one layer down.
    is_review = ("review" in t) and ("pr" in t or "code" in t or "#73" in t)
    is_docstring = "docstring-verified" in labels_pre
    if not (is_review or is_docstring): continue
    num=str(i["number"]); labels={l["name"] for l in i.get("labels",[])}
    d=json.loads(gh(["issue","view",num,"-R",REPO,"--json","body,comments,author"]))
    coms=d.get("comments",[])
    # FIX (#17054): `gh issue view --json comments` only returns the first 100 comments;
    # if 100+ comments exist, fetch the full thread via `gh api --paginate --slurp` so
    # a trusted `rtc-payout-amount` or `RTC-AutoPay-Confirmed` marker at 101+ is never missed.
    if len(coms) >= 100:
        raw_pages = json.loads(gh(["api", "--paginate", "--slurp", f"/repos/{REPO}/issues/{num}/comments?per_page=100"]) or "[]")
        coms = [c for page in raw_pages for c in (page if isinstance(page, list) else [page]) if isinstance(c, dict)]
    # `claimant_login` is the issue author's GitHub login. It is the last-resort
    # handle fallback for claims whose body says "Wallet: TBD" and whose
    # comment thread has no parseable handle. The previous version fetched
    # only `body,comments`, so the fallback was unreachable in production.
    a=d.get("author") or {}
    claimant=a.get("login") if isinstance(a, dict) else None
    # A label can only be applied by someone with triage/write access, so it is
    # an authorization. A COMMENT is not: anyone with a GitHub account can write
    # "Verified eligible" on a public issue and, before this check, be paid for
    # it. Comment-based eligibility now requires a trusted author.
    eligible = ("bounty-eligible" in labels) or any(
        "Verified eligible" in (c.get("body") or "")
        and _is_trusted(_comment_author_login(c)[0])
        for c in coms)
    if not eligible: continue
    # Already paid? Only a TRUSTED, structured confirmation counts. This used
    # to skip on any comment by anyone containing the marker string, so any
    # GitHub user could cancel an eligible claim's payout on a green run by
    # commenting it (rules shared with auto-pay; see payment_markers.py). The
    # idempotency key below still makes a repeat transfer a no-op at the node.
    if any(payment_markers.comment_records_payment(c, REPO.split("/")[0]) for c in coms): continue
    wallet, source = resolve_wallet(d.get("body"), coms, claimant_login=claimant)
    if not wallet: continue
    # Review claims are a flat RATE. Docstring claims are worth whatever the
    # gate verified (0.5 RTC per docstring), so paying the flat rate would pay
    # 3 RTC for work verified at 4.5, 7.5 or 9. Read the gate's own figure.
    amount, memo, idem = RATE, f"Bounty #73 code-review — claim #{num} (source: {source})", f"bounty73-claim-{num}"
    if is_docstring:
        # The amount marker decides how much money moves, so it may only come
        # from the gate that verified the work. Previously every comment was
        # scanned and the LAST match won with no author check, so anyone could
        # append a larger marker and be paid it -- and because the gate's
        # per-claim ceiling is enforced before that comment exists, the marker
        # also bypassed the ceiling. Trusted authors only, and re-check the cap.
        amount=_trusted_marker_amount(coms, where=f"#{num}")
        if amount is None:
            print(f"::warning::#{num} is docstring-verified but carries no trusted amount marker; skipping")
            continue
        if amount > MAX_CLAIM_RTC:
            print(f"::warning::#{num} amount {amount} exceeds MAX_CLAIM_RTC={MAX_CLAIM_RTC}; skipping")
            continue
        problem=_docstring_claim_problem(d.get("body"), i.get("title"), claimant)
        if problem:
            print(f"::warning::#{num} is docstring-verified but not payable: {problem}; skipping (needs a human)")
            continue
        memo=f"Docstring bounty — claim #{num}, gate-verified (source: {source})"
        idem=f"docstring-claim-{num}"
    ok,resp=transfer(wallet,memo,idem,amount)
    if ok:
        paid+=1; total+=amount
        # Transfers are two-phase: the node returns phase="pending" with a 24h
        # confirmation window, and the balance does not move until the pending
        # confirmer runs. Say "queued", not "sent" — reporting an unconfirmed
        # hold as a completed payment is the other half of #16390.
        phase=resp.get("phase","") if isinstance(resp,dict) else ""
        txh=resp.get("tx_hash","") if isinstance(resp,dict) else ""
        tx=f" tx `{txh}`." if txh else ""
        if phase=="pending":
            hrs=resp.get("confirms_in_hours",24)
            state=(f"**queued** — {amount:g} RTC to `{wallet}`.{tx} Pending the standard "
                   f"{hrs:g}h confirmation window; the balance moves when it clears.")
        else:
            state=f"**settled** — {amount:g} RTC to `{wallet}`.{tx}"
        # Second-act hook: the payout notification is the one moment of
        # guaranteed attention. Ending on "thanks" wastes it; ending on a named
        # next task is the cheapest retention step available. Fail-open by
        # construction -- build() returns "" rather than raising, so a broken
        # hook can never block a payment.
        try:
            hook=_second_act.build(claimant or wallet, REPO, i["title"])
        except Exception:
            hook=""
        gh(["issue","comment",num,"-R",REPO,"--body",
            f"💸 **RTC-AutoPay-Confirmed** — payout {state} "
            f"(source: {source}, verified #73 review, from `founder_community`). "
            f"Thanks for the review!{hook}\n\n"
            f"<!-- {payment_markers.MARKER} kind=claim claim={num} -->"])
        gh(["issue","close",num,"-R",REPO,"--reason","completed"])
    else: print(f"::warning::pay failed #{num}: {resp}")
    time.sleep(1.5)
print(f"bounty-payout: paid {paid} claims = {total:g} RTC this run")
