# Self-Audit: node/beacon_api.py

## Wallet
RTC4642c5ee8467f61ed91b5775b0eeba984dd776ba

## Module reviewed
- Path: node/beacon_api.py
- Commit: 0fdd393b74b10cdf8d84298b258f5bf57e45b4fd
- Lines reviewed: whole-file (~680 lines)

## Deliverable: 3 specific findings

1. **Unauthenticated Bounty Claim — Any Agent Can Claim Any Bounty**
   - Severity: high
   - Location: beacon_api.py:402-425 (`/api/bounties/<bounty_id>/claim` endpoint)
   - Description: The `claim_bounty` endpoint accepts a POST with only an `agent_id` field and performs no authentication or authorization check. Any caller can claim any bounty for any agent_id, including impersonating other agents. Contrast with the `complete_bounty` endpoint (line ~430) which properly requires `X-Admin-Key` via `hmac.compare_digest`. The claim endpoint lacks equivalent protection, allowing bounty hijacking.
   - Reproduction:
     ```bash
     # Claim bounty #1 as any arbitrary agent — no auth needed
     curl -X POST https://<host>/api/bounties/gh_Rustchain_1/claim \
       -H 'Content-Type: application/json' \
       -d '{"agent_id": "attacker-agent-001"}'
     # Returns 200: {"ok": true, "bounty_id": "gh_Rustchain_1", "claimant": "attacker-agent-001"}
     ```
   - Fix: Require signature verification — the caller should prove ownership of the agent_id's pubkey (e.g., sign a challenge nonce), or at minimum require an admin key like `complete_bounty` does.

2. **SSL Certificate Verification Disabled — MITM Vulnerability in Bounty Sync**
   - Severity: high
   - Location: beacon_api.py:330-334 (`/api/bounties/sync` endpoint)
   - Description: The `sync_bounties` function explicitly disables SSL certificate verification with `ctx.check_hostname = False` and `ctx.verify_mode = ssl.CERT_NONE`. This allows a network-level attacker (e.g., on the same WiFi, compromised ISP, or DNS hijack) to intercept and modify GitHub API responses, injecting fake bounties with attacker-controlled URLs. The comment says "for demo" but this code ships in the module with no environment guard.
   - Reproduction:
     ```python
     # The vulnerable code in sync_bounties():
     ctx = ssl.create_default_context()
     ctx.check_hostname = False      # ← disables hostname verification
     ctx.verify_mode = ssl.CERT_NONE  # ← disables certificate validation
     # Any network MITM can now inject fake bounty data
     ```
   - Fix: Remove the SSL bypass entirely. Use `ssl.create_default_context()` with default settings. If a demo mode is needed, gate it behind an explicit environment variable like `RC_INSECURE_SSL=1` with a warning log.

3. **Exception String Leakage — Internal Implementation Details Exposed to Clients**
   - Severity: medium
   - Location: beacon_api.py — every endpoint's `except` block (lines ~106, ~118, ~160, ~230, ~260, ~285, ~310, ~370, ~425, ~470, ~530, ~560, ~600, ~650)
   - Description: Every endpoint catches `Exception as e` and returns `str(e)` in the JSON error response. This leaks internal details including database schema (SQLite column names, table names), file paths (`DB_PATH`), Python module paths, and potentially sensitive query fragments. An attacker can use this for reconnaissance — e.g., sending invalid contract_id values to discover table structures, or triggering DB errors to enumerate column names.
   - Reproduction:
     ```bash
     # Trigger a DB error to leak internal details
     curl -X PUT https://<host>/api/contracts/../../etc/passwd \
       -H 'Content-Type: application/json' \
       -d '{"state": "active"}'
     # Error response may contain SQLite error with table/column names
     
     # Or send malformed JSON to create_contract
     curl -X POST https://<host>/api/contracts \
       -H 'Content-Type: application/json' \
       -d '{"from": "test", "to": "test", "type": "test", "amount": "NaN", "term": "test"}'
     # Returns: {"error": "could not convert string to float: 'NaN'"} — leaks Python internals
     ```
   - Fix: Return generic error messages to clients (`"Internal server error"`) while logging the full exception server-side. Example:
     ```python
     except Exception as e:
         app.logger.error(f"Error in endpoint: {e}", exc_info=True)
         return jsonify({'error': 'Internal server error'}), 500
     ```

## Known failures of this audit
- Did not check for SQL injection beyond confirming parameterized queries are used (they are — `?` placeholders throughout)
- Did not test the Flask application's deployment configuration (HTTPS enforcement, CORS origins beyond `*` in OPTIONS handlers)
- Did not verify whether `RC_ADMIN_KEY` is set in production or if `complete_bounty` is effectively unprotected via env misconfiguration
- Did not review rate limiting or brute-force protections on any endpoint
- Did not assess the `relay_agents` table for mass registration abuse (no rate limit on `/beacon/join`)
- Low confidence on whether `db.total_changes` check in `update_contract` (line ~290) correctly detects no-op updates — `total_changes` tracks all changes in the connection, not just the last statement

## Confidence
- Overall confidence: 0.85
- Per-finding confidence: [0.90, 0.95, 0.85]

## What I would test next
- Test whether the `beacon_join` endpoint allows mass registration of fake agents (no rate limit, no CAPTCHA, no proof-of-work) to pollute the beacon atlas
- Verify if the `chat` endpoint stores unsanitized user input that could be rendered as HTML/XSS when consumed by a frontend
- Test the `update_contract` endpoint for authorization — currently anyone can change any contract's state without being a party to that contract
