# Sanctuary Alumni Referral Program

**RIP-306 Addendum: Referral Incentive for Contributor Growth**
**Status**: PROPOSAL
**Author**: Elyan Labs
**Date**: 2026-03-24

---

## Summary

Silver-tier and above contributors receive a referral code. When a new
contributor joins through that code and earns bounty payments, the referrer
receives 10% of the referred contributor's earnings as a bonus. The bonus is
paid from `founder_community`, not deducted from the referred contributor's
payout.

## Goals

1. Incentivize established contributors to recruit quality talent
2. Reward mentorship (Sanctuary alumni guiding newcomers through Sophia's House)
3. Grow the contributor base through trusted word-of-mouth
4. Reduce spam: referred contributors arrive pre-vetted by someone with skin in the game

## Eligibility

### Referrer Requirements

- Must be **Silver tier or above** (200+ RTC earned)
- Must have an active wallet in the contributor_profiles table
- Account must not be flagged for fraud

### Referred Contributor Requirements

- Must be a **new contributor** (no prior bounty payments in the ledger)
- Must use the referral code **before their first bounty claim**
- Must earn at least **10 RTC** through their own work before referral bonuses activate
  (prevents gaming via trivial self-referral chains)

## Referral Code Format

Codes are generated when a contributor reaches Silver tier:

```
{INITIALS}-{4 hex chars}
```

Examples: `CK-7A3F`, `BF-E291`, `MT-4B0C`

Codes are:
- Permanent (do not expire)
- Unique per contributor
- Case-insensitive for entry

## Payout Mechanics

### Referral Bonus

| Parameter | Value |
|-----------|-------|
| **Bonus rate** | 10% of referred contributor's confirmed bounty earnings |
| **Source** | `founder_community` wallet |
| **Cap** | 500 RTC per referrer per calendar quarter |
| **Activation threshold** | Referred contributor must earn 10+ RTC first |
| **Payment frequency** | Batched weekly (every Monday 00:00 UTC) |

### Example

1. Alice (Silver, code `AL-9F1E`) refers Bob
2. Bob claims his first bounty: 25 RTC for an engineering PR
3. Bob has now earned 25 RTC (above the 10 RTC activation threshold)
4. Alice receives 2.5 RTC bonus from `founder_community`
5. Bob later earns 100 RTC in a quarter
6. Alice receives 10 RTC total referral bonus for Bob that quarter
7. Bob's payouts are unaffected -- he receives the full amount plus any tier multiplier

### Cap Enforcement

If Alice has referred 5 contributors who collectively earn 6,000 RTC in a
quarter, Alice's referral bonus would be 600 RTC. The cap limits this to
500 RTC. Overflow does not roll over.

The cap resets on January 1, April 1, July 1, and October 1 UTC.

## Anti-Gaming Rules

### 1. No Self-Referral

A contributor cannot use their own referral code. The system checks that the
referrer wallet and referred wallet are different, and that they are not
linked to the same GitHub account.

### 2. No Circular Referrals

If A referred B, then B cannot refer A. The `referred_by` field is immutable
after first assignment.

### 3. Minimum Contribution Threshold

Referral bonuses do not activate until the referred contributor has earned
10 RTC through confirmed bounty work. This prevents:
- Creating throwaway accounts that earn 1 RTC from a star bounty
- Referring bots or spam accounts
- Farming referral bonuses through trivial contributions

### 4. Single Referral Per Contributor

A contributor can only be referred once. The first valid referral code used
is permanent. Attempts to change the referral code after assignment are rejected.

### 5. Fraud Detection

If a referred contributor is later flagged for spam or fraud:
- All pending referral bonuses for that contributor are voided
- Already-paid bonuses are not clawed back (too complex to administer)
- If a referrer has 3+ referred contributors flagged for fraud, the referrer's
  code is suspended pending manual review

### 6. Rate Limit

A single referrer can have at most **20 active referrals** (referred
contributors who have earned 10+ RTC). This prevents industrial-scale
referral farming.

## Database Schema

```sql
-- Referral tracking
CREATE TABLE referrals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    referrer_wallet TEXT NOT NULL,
    referrer_code   TEXT NOT NULL,
    referred_wallet TEXT NOT NULL UNIQUE,  -- one referral per contributor
    referred_github TEXT,
    created_at      INTEGER NOT NULL,      -- unix timestamp
    activated_at    INTEGER,               -- when referred hit 10 RTC threshold
    is_active       INTEGER DEFAULT 0,     -- 1 after activation threshold met
    FOREIGN KEY (referrer_wallet) REFERENCES contributor_profiles(wallet_id)
);

-- Referral bonus payments
CREATE TABLE referral_payouts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    referrer_wallet TEXT NOT NULL,
    referred_wallet TEXT NOT NULL,
    quarter         TEXT NOT NULL,          -- e.g., "2026-Q1"
    base_earnings   REAL NOT NULL,          -- referred contributor's earnings this quarter
    bonus_amount    REAL NOT NULL,          -- 10% of base, capped
    paid_at         INTEGER NOT NULL,
    tx_id           TEXT                    -- ledger transaction ID
);

-- Quarterly cap tracking
CREATE TABLE referral_caps (
    referrer_wallet TEXT NOT NULL,
    quarter         TEXT NOT NULL,
    total_paid      REAL NOT NULL DEFAULT 0.0,
    cap_remaining   REAL NOT NULL DEFAULT 500.0,
    PRIMARY KEY (referrer_wallet, quarter)
);

CREATE INDEX idx_referrals_referrer ON referrals(referrer_wallet);
CREATE INDEX idx_referrals_referred ON referrals(referred_wallet);
CREATE INDEX idx_payouts_quarter ON referral_payouts(quarter);
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/referral/{wallet_id}` | Get referral code and stats for a contributor |
| POST | `/api/referral/use` | Apply a referral code to a new contributor |
| GET | `/api/referral/{wallet_id}/referred` | List contributors referred by this wallet |
| GET | `/api/referral/{wallet_id}/earnings` | Referral bonus earnings summary |

### Apply Referral Code

```json
POST /api/referral/use
{
    "referred_wallet": "new-contributor-wallet",
    "referral_code": "CK-7A3F"
}

Response:
{
    "ok": true,
    "referrer": "createkr",
    "referred": "new-contributor-wallet",
    "activation_threshold": 10.0,
    "message": "Referral registered. Bonus activates after you earn 10 RTC."
}
```

### Error Cases

```json
{"ok": false, "error": "self_referral", "message": "Cannot use your own referral code"}
{"ok": false, "error": "already_referred", "message": "This wallet already has a referral"}
{"ok": false, "error": "invalid_code", "message": "Referral code not found"}
{"ok": false, "error": "not_new", "message": "Only new contributors can use referral codes"}
{"ok": false, "error": "referrer_suspended", "message": "This referral code is suspended"}
{"ok": false, "error": "referrer_cap", "message": "Referrer has reached maximum active referrals"}
```

## Weekly Payout Batch Process

Runs every Monday at 00:00 UTC via cron on Node 1:

```python
def process_referral_payouts():
    quarter = current_quarter()  # e.g., "2026-Q1"

    for referral in get_active_referrals():
        # Sum referred contributor's earnings this quarter
        earnings = get_quarter_earnings(referral.referred_wallet, quarter)
        if earnings <= 0:
            continue

        # Calculate bonus
        bonus = earnings * 0.10

        # Check cap
        cap = get_or_create_cap(referral.referrer_wallet, quarter)
        if cap.total_paid >= 500.0:
            continue
        bonus = min(bonus, cap.cap_remaining)

        # Pay from founder_community
        tx_id = transfer(
            source="founder_community",
            to=referral.referrer_wallet,
            amount=bonus,
            memo=f"referral_bonus_{referral.referred_wallet}_{quarter}"
        )

        # Record payout
        insert_referral_payout(referral, quarter, earnings, bonus, tx_id)
        update_cap(referral.referrer_wallet, quarter, bonus)
```

## Integration with Sophia's House / Sanctuary

The referral program ties directly into the existing Sanctuary onboarding:

1. Referrer shares their code with a potential contributor
2. New contributor uses the code when creating their wallet
3. New contributor goes through Sophia's House (creative bounty onboarding)
4. After earning 10+ RTC, the referral activates
5. Both parties benefit: referrer gets bonus, referred gets a mentor

### Sanctuary Alumni as Mentors

Contributors who have gone through the full bounty pipeline -- creative
onboarding, engineering work, tier progression -- are the best referrers.
They understand the process and can guide newcomers past common pitfalls:

- How to write a clean PR
- How to claim bounties properly
- How to set up a wallet
- What code quality Sophia's House expects

This mentorship loop is the real value of the referral program. The RTC bonus
is the incentive; the knowledge transfer is the outcome.

## Budget Impact

### Worst-Case Quarter

Assume 30 active referrers, each hitting the 500 RTC cap:
- Maximum quarterly cost: 15,000 RTC
- Source: `founder_community` (current balance ~192,805 RTC)
- Sustainable for 12+ quarters at maximum burn

### Realistic Quarter

Based on current contributor growth (~20 new contributors/month):
- Active referrers: ~10 (Silver+ contributors who actively recruit)
- Average referred earnings: ~50 RTC/quarter
- Average bonus per referrer: ~50 RTC/quarter
- Estimated quarterly cost: ~500 RTC
- Negligible impact on `founder_community` balance

## Rollout Plan

### Phase 1: Code Generation (with Tier System Phase 1)

- Generate referral codes for all existing Silver+ contributors
- Add `referral_code` column to `contributor_profiles`
- Notify eligible contributors via Discord

### Phase 2: Registration and Tracking (Week 2)

- Deploy `/api/referral/*` endpoints
- Add referral code input to wallet creation flow
- Begin tracking referred contributors

### Phase 3: Payouts (Week 3)

- Deploy weekly payout batch job
- Wire Discord notifications for referral bonus payments
- Add referral stats to contributor profile page

### Phase 4: Promotion (Ongoing)

- Announce program on Moltbook, 4claw, Discord
- Add referral link to bounty documentation
- Include referral code in contributor badge pages

## Open Questions

1. Should referral bonuses count toward the referrer's tier progression?
   (Current proposal: yes, they are RTC earned through contribution activity.)
2. Should there be a "super-referrer" bonus for contributors who refer 10+
   successful contributors?
3. Should referral codes be shareable via URL (`rustchain.org/join?ref=CK-7A3F`)?
