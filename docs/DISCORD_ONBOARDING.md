# Discord → On-Chain Holder Onboarding

*Program date: 2026-05-30 · Funded entirely from founder premine (no new RTC minted)*

## What this is

RustChain's Discord community (**RustChain — POA Coin Powered By Sophia Core**) has run an
off-chain RTC economy inside the Sophia bot since mid-2025. Members earned RTC for
participation, games (UT99, Halo, Factorio), and daily activity. Those balances lived
**only inside the Discord bot** — they were never on the real chain.

This program **bridges those Discord balances onto the live RustChain**, gives every
participant a real on-chain RTC address, and adds a loyalty bonus for members who stayed.

## How it works

1. **Custodial address per member.** Each Discord account is assigned a real Ed25519
   RustChain wallet (`RTC…`), derived deterministically and held custodially by the
   operator until the member claims it.
2. **Balance migration.** Each member's earned off-chain balance is transferred **from a
   founder wallet** (`founder_community`) to their new on-chain address.
   **No RTC is minted** — this is premine flowing out to the people who earned it.
3. **Loyalty bonus.** Members still in the channel receive an additional **1.5 RTC** for
   staying. (Members who left keep what they *earned*, but do not receive the staying bonus.)
4. **Private delivery.** Sophia DMs each reachable member their wallet address. The wallet
   is held **custodially** for them; to take full self-custody they reply and request a
   transfer to a new wallet they create. (No private keys are ever sent over Discord DMs.)

## The numbers (2026-05-30)

| Group | Members | RTC |
|-------|--------:|----:|
| Stayed + earned balance | 175 | balance + 1.5 |
| Recent joiners (no balance yet) | 43 | 1.5 base grant |
| Earned balance but left the server | 81 | earned balance only (claimable on return) |
| **Total onboarded** | **299** | **~2,072.87 RTC** |

- Balances migrated: **1,745.87 RTC** · Loyalty bonuses: **327.00 RTC** (218 × 1.5)
- All funded from `founder_community` premine — **circulating supply unchanged by minting.**

## Why it matters

This onboarding takes RustChain from **766 on-chain holders to ~1,065**, crossing the
**1,000-holder threshold**. Per the published tokenomics, that lifts the internal
**reference rate from $0.10 to $0.15 per RTC**.

> **Note on the reference rate:** $0.15 is RustChain's *internal reference rate*, scaled by
> holder count. RTC has no DEX/CEX listing and no fiat off-ramp at this time — the reference
> rate is an accounting benchmark for bounty/reward sizing, not a market price.

## Claiming & custody

- **Self-custody (move-on-request):** your wallet is held custodially for now. To take full
  ownership, reply to Sophia's DM and request a transfer to a new wallet you create — funds
  move to your self-made address. **No seed or private key is ever sent over a Discord DM**
  (DMs are not end-to-end encrypted); secure key export, if offered later, will use a
  dedicated channel.
- **Left the server?** Your earned balance is held at your custodial address and is
  claimable if you rejoin.

## Anti-sybil

Recipients are keyed by **unique Discord account ID** (snowflake). Each unique human
account maps to exactly one custodial wallet. Bot accounts are excluded.

---

*Operated by Elyan Labs. Questions: open an issue or ask in the Discord.*
