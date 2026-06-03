# RustChain Contributor Tier System

**RIP-306: Contributor Reputation and Tier Framework**
**Status**: PROPOSAL
**Author**: Elyan Labs
**Date**: 2026-03-24

---

## Summary

A four-tier reputation system for RustChain bounty contributors, calculated from
on-chain bounty ledger data. Tiers unlock payout multipliers, bounty access
levels, and governance participation. All thresholds are denominated in RTC
earned through verified bounty payments.

## Tier Definitions

| Tier | Threshold | Multiplier | Badge Color |
|------|-----------|------------|-------------|
| **Platinum** | 1,000+ RTC | 1.5x | `#E5E4E2` |
| **Gold** | 500+ RTC | 1.2x | `#FFD700` |
| **Silver** | 200+ RTC | 1.1x | `#C0C0C0` |
| **Bronze** | 50+ RTC | 1.0x | `#CD7F32` |
| Untiered | < 50 RTC | 1.0x | none |

Multipliers apply to future bounty payouts only. They do not retroactively
adjust past payments.

## Benefits by Tier

### Bronze (50+ RTC earned)

- Listed on the public contributors page at `rustchain.org/contributors`
- Priority claim window on new bounties (24h head start over untiered)
- SVG badge for GitHub profile README
- Access to `#contributors` Discord channel

### Silver (200+ RTC earned)

- Everything in Bronze
- **1.1x payout multiplier** on all bounties
- Access to medium-difficulty bounties (100+ RTC pool)
- Vote on proposed bounties (one vote per Silver+ contributor)
- Referral code eligibility (see REFERRAL_PROGRAM.md)

### Gold (500+ RTC earned)

- Everything in Silver
- **1.2x payout multiplier** on all bounties
- Access to red-team security bounties (900 RTC pool)
- Nominate new bounties for community vote
- "Trusted Reviewer" status: approvals count toward merge threshold
- Quarterly AMA slot with core team

### Platinum (1,000+ RTC earned)

- Everything in Gold
- **1.5x payout multiplier** on all bounties
- Direct communication channel with core team (Discord/Slack)
- Access to all bounty categories including infrastructure
- Governance weight: 2 votes on bounty proposals
- Name on the RustChain genesis contributors list (permanent, on-chain)
- Early access to RIP drafts before public posting

## Tier Calculation

Tiers are computed from the `bounty_ledger` table. Only confirmed payments
(status = `confirmed`) count toward the threshold.

```sql
SELECT
    wallet_id,
    SUM(amount_rtc) AS total_earned,
    CASE
        WHEN SUM(amount_rtc) >= 1000 THEN 'platinum'
        WHEN SUM(amount_rtc) >= 500  THEN 'gold'
        WHEN SUM(amount_rtc) >= 200  THEN 'silver'
        WHEN SUM(amount_rtc) >= 50   THEN 'bronze'
        ELSE 'untiered'
    END AS tier
FROM bounty_ledger
WHERE status = 'confirmed'
GROUP BY wallet_id
ORDER BY total_earned DESC;
```

### What Counts

- Bounty payments (engineering, creative, security, stars)
- Red-team payouts
- Ambassador compensation
- Referral bonuses (capped separately; see REFERRAL_PROGRAM.md)

### What Does Not Count

- Mining rewards (RTC earned through PoA attestation)
- Airdrop tokens
- OTC purchases
- Transfers between wallets

## Database Schema Additions

```sql
-- Contributor profile (derived, cached)
CREATE TABLE contributor_profiles (
    wallet_id       TEXT PRIMARY KEY,
    github_username TEXT,
    display_name    TEXT,
    tier            TEXT NOT NULL DEFAULT 'untiered',
    total_earned    REAL NOT NULL DEFAULT 0.0,
    bounties_merged INTEGER NOT NULL DEFAULT 0,
    first_payout    INTEGER,          -- unix timestamp
    last_payout     INTEGER,          -- unix timestamp
    referral_code   TEXT UNIQUE,      -- assigned at Silver
    referred_by     TEXT,             -- referral_code of referrer
    badge_svg_url   TEXT,
    updated_at      INTEGER NOT NULL
);

-- Tier change audit log
CREATE TABLE tier_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_id   TEXT NOT NULL,
    old_tier    TEXT NOT NULL,
    new_tier    TEXT NOT NULL,
    total_at_change REAL NOT NULL,
    changed_at  INTEGER NOT NULL
);

-- Index for fast lookup
CREATE INDEX idx_profiles_tier ON contributor_profiles(tier);
CREATE INDEX idx_profiles_github ON contributor_profiles(github_username);
```

## API Endpoints

### Public

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/contributors` | Paginated list, sorted by total_earned |
| GET | `/api/contributors/{wallet_id}` | Single profile with tier, stats, badge URL |
| GET | `/api/contributors/{wallet_id}/badge.svg` | Dynamic SVG badge |
| GET | `/api/tiers/summary` | Count of contributors per tier |

### Authenticated (admin key)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/contributors/recalculate` | Force tier recalculation from ledger |
| POST | `/api/contributors/{wallet_id}/link-github` | Associate GitHub username |

### Example Response

```json
GET /api/contributors/createkr

{
    "wallet_id": "createkr",
    "github_username": "createkr",
    "tier": "platinum",
    "total_earned": 3122.0,
    "bounties_merged": 45,
    "multiplier": 1.5,
    "first_payout": 1704067200,
    "last_payout": 1711238400,
    "badge_url": "/api/contributors/createkr/badge.svg",
    "referral_code": "CK-7A3F"
}
```

## SVG Badge System

Badges are generated server-side from contributor data. Format follows
shields.io conventions for compatibility with GitHub profile READMEs.

```
![RustChain Platinum](https://rustchain.org/api/contributors/createkr/badge.svg)
```

Rendered example (text representation):

```
+--------------------------------------------+
| RustChain | Platinum - 3,122 RTC           |
+--------------------------------------------+
  (left: dark bg)  (right: tier-colored bg)
```

Badge fields:
- Left: "RustChain" (static)
- Right: "{Tier} - {total_earned} RTC" (dynamic, tier-colored background)

### Badge SVG Template

```xml
<svg xmlns="http://www.w3.org/2000/svg" width="220" height="20">
  <linearGradient id="b" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <mask id="a">
    <rect width="220" height="20" rx="3" fill="#fff"/>
  </mask>
  <g mask="url(#a)">
    <rect width="80" height="20" fill="#555"/>
    <rect x="80" width="140" height="20" fill="{TIER_COLOR}"/>
    <rect width="220" height="20" fill="url(#b)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,sans-serif" font-size="11">
    <text x="40" y="15" fill="#010101" fill-opacity=".3">RustChain</text>
    <text x="40" y="14">RustChain</text>
    <text x="150" y="15" fill="#010101" fill-opacity=".3">{TIER} - {TOTAL} RTC</text>
    <text x="150" y="14">{TIER} - {TOTAL} RTC</text>
  </g>
</svg>
```

## Contributor Profile Page

The public profile at `rustchain.org/contributors` shows:

1. **Leaderboard** -- Top contributors sorted by total earned
2. **Tier distribution** -- Pie chart of contributor counts per tier
3. **Recent payouts** -- Last 20 confirmed bounty payments
4. **Individual pages** -- Per-contributor history, merged PRs, tier progression

## Recalculation Schedule

Tiers are recalculated:
- After every confirmed bounty payment (event-driven)
- On a daily cron as a consistency check
- On demand via the admin `/recalculate` endpoint

When a contributor crosses a tier boundary:
1. New tier is written to `contributor_profiles`
2. A row is inserted into `tier_history`
3. A Discord webhook fires to `#announcements` with a congratulations message
4. Badge SVG cache is invalidated

## Multiplier Application

When processing a bounty payment:

```python
base_amount = bounty.reward_rtc
profile = get_contributor_profile(recipient_wallet)
multiplier = TIER_MULTIPLIERS.get(profile.tier, 1.0)
final_amount = base_amount * multiplier

# Multiplier funded from founder_team_bounty, not from the bounty pool
# This means the bounty poster pays the base; Elyan Labs funds the bonus
bonus = final_amount - base_amount
transfer(source="founder_team_bounty", to=recipient_wallet, amount=bonus, memo=f"tier_bonus_{profile.tier}")
transfer(source=bounty.funding_wallet, to=recipient_wallet, amount=base_amount, memo=f"bounty_{bounty.id}")
```

The bonus comes from `founder_team_bounty`, not from the bounty's own pool.
This prevents tier multipliers from draining bounty budgets.

## Implementation Plan

### Phase 1: Data and Calculation (Week 1)

- [ ] Add `contributor_profiles` and `tier_history` tables to `rustchain_v2.db`
- [ ] Write `recalculate_tiers.py` script that reads `bounty_ledger` and populates profiles
- [ ] Run initial calculation against existing 31,710 RTC / 487 wallets
- [ ] Deploy as cron job on Node 1 (https://rustchain.org)

### Phase 2: API and Badges (Week 2)

- [ ] Add `/api/contributors/*` endpoints to the RustChain node
- [ ] Implement SVG badge generation
- [ ] Add contributor page to `rustchain.org` (static site generation from API)

### Phase 3: Multiplier Integration (Week 3)

- [ ] Update bounty payment flow to apply tier multipliers
- [ ] Wire Discord webhook for tier-up notifications
- [ ] Update `confirm_pending.sh` to include multiplier in payment confirmation

### Phase 4: Governance (Week 4+)

- [ ] Implement bounty voting system (Silver+)
- [ ] Implement bounty nomination (Gold+)
- [ ] Add referral code generation (Silver+)

## Anti-Gaming Provisions

1. **Ledger-only calculation**: Tiers derive from confirmed on-chain payments,
   not self-reported data.
2. **No retroactive multipliers**: Crossing a tier threshold does not adjust
   past payments.
3. **Spam resistance**: The existing bounty triage process (Sophia's House)
   filters low-quality submissions before they reach payment.
4. **Wallet binding**: One GitHub account per wallet. The `hardware_bindings`
   table and existing identity checks prevent sybil wallets.
5. **Cooldown**: Tier downgrades are not implemented. Once earned, a tier is
   permanent unless the contributor is flagged for fraud.
6. **Audit trail**: Every tier change is logged in `tier_history` with the
   RTC total at the time of change.

## Compatibility with Existing Systems

- **ShAprAI Sanctuary**: Contributors who graduate agents through Sophia's House
  earn RTC through the agent economy (RIP-302). Those payments count toward
  tier progression.
- **Star King bounties**: Star-farming payments count, but the per-contributor
  cap (existing policy) limits gaming.
- **Mining rewards**: Excluded from tier calculation. Mining and contributing
  are separate activities.

## Open Questions

1. Should tiers decay if a contributor is inactive for 6+ months?
2. Should there be a "Diamond" tier above Platinum for 5,000+ RTC?
3. Should multipliers apply to star bounties or only engineering/security work?

---

## Appendix: Current Tier Distribution (2026-03-24 Snapshot)

See `analyze_tiers.py` for the full breakdown. Summary:

| Tier | Count | Notable Contributors |
|------|-------|---------------------|
| Platinum | 3 | createkr (3,122), simplereally (1,075), mtarcure (974) |
| Gold | 4 | zhanglinqian (755), davidtang-codex (921), liu971227-sys (550), noxxxxybot/dayi1000 (550) |
| Silver | 7 | BuilderFred (543), LaphoqueRC (429), ArokyaMatthew (340), godong (330), ansomeck (327), erdogan98 (315), John Reed (250) |
| Bronze | 15+ | ALLSTARETC111 (200), krishna2918 (175), CelebrityPunks (129), lopieloo (125), believening (125), energypantry (110), nicepopo86 (109.5), Joshualover (99), WeberG (85), 952800710 (74), jiangyj545 (126), JohnnieLZ (65.5), Tianlin0725 (60), sososonia-cyber (52.5), ApextheBoss (50) |
| Untiered | ~220 | Contributors below 50 RTC |
