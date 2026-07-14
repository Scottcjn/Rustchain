# What If: RTC Fundamentals — A Coverage Analysis (Not a Promise)

> **Read this box first.** This document is a *what-if scenario analysis*, not a promise,
> not a price target, not investment advice, and not a claim that RTC "is worth" any
> particular number. RTC holders have **no legal claim** on the RustChain codebase,
> Elyan Labs hardware, or any asset described here — coverage is an honesty check on
> the reference rate, the way book-value-per-share is an honesty check on a stock
> price, not a redemption guarantee. Markets for RTC are **thin** (see the wRTC
> liquidity caveat in the [README](../README.md#tokenomics)). Every input below is
> dated, sourced, and re-computable by you.

**Analysis date:** 2026-06-11. Live counterparts of several figures regenerate at
[`rustchain.org/facts.json`](https://rustchain.org/facts.json) (see the
`external_sales` and `live_chain` facts) and
[`rustchain.org/payouts.json`](https://rustchain.org/payouts.json).

---

## The question

The published reference rate is $0.15 (tier schedule: $0.10 base → $0.15 at 1,000+
holders → $0.20 at 2,000+ → market discovery). External arms-length sales have
cleared at $0.10 (operator-attested; disclosed as such in `facts.json`).

**What if you valued RTC on fundamentals instead — what the ecosystem would cost to
replace, and what an RTC has actually purchased? Is the reference rate honest,
inflated, or conservative?**

## Measured inputs (all re-computable)

| Input | Value (2026-06-11) | How to verify |
|---|---|---|
| Total supply (hard cap) | 8,388,608 RTC (2²³) | `GET /epoch` → `total_supply_rtc`; `TOTAL_SUPPLY_RTC` in node source |
| **Issued on-ledger** | **445,018 RTC** across 1,278 wallets | Sum of `balances` via the [explorer](https://rustchain.org/explorer) / `transactions.json` |
| Held by the 4 founder wallets | 286,275 RTC | Explorer: `founder_founders`, `founder_dev_fund`, `founder_team_bounty`, `founder_community` |
| **External circulating float** | **~158,743 RTC** | Issued minus founder-held |
| Holders with positive balance | 1,248 | `facts.json` → `activity_density` |
| New emission | 1.5 RTC per ~24h epoch ≈ **548 RTC/year** max | `PER_BLOCK_RTC` in node source; halvings (README §Tokenomics) only *lower* this |
| Public repo, core code | 562,200 lines (excl. `bounties/` submissions) | `git clone` this repo and count |
| Deployed node codebase | ~84,000 lines (overlapping + node-local) | Operator-attested |
| On-chain bounty payouts | 670 payouts, 21,130 RTC from `founder_team_bounty` | `participation.json`; ledger debits in explorer |
| External sales cleared | $0.10, arms-length OTC | `facts.json` → `external_sales` (operator-attested, thin depth disclosed) |

## What-if #1: effective supply

"Fully diluted" assumes all 8.39M RTC exist. At the code-pinned emission rate
(≤548 RTC/year, fixed per RIP-0004), issuing the 7.88M mining allocation takes
**millennia**. Over any 5-year horizon, effective supply is ~448K RTC — issued
supply plus rounding. Annual dilution of issued supply: **~0.12%**, versus 2–10%
for typical chains.

## What-if #2: replacement cost of the code

Textbook COCOMO on 562 KLOC yields ~1,850 person-months (~$15–20M loaded). We
**reject that number** as inflated for AI-assisted development and utility code,
and instead apply a heavy discount to a defensible modern band:

> **Conservative replacement cost of the chain + flagship ecosystem: $1.5–2.5M.**

This covers the node (consensus, RIP-PoA fingerprinting, ledger, governance,
bridges), miners across 10+ CPU architectures, wallets, explorer, SDKs, and MCP
servers — and deliberately excludes hardware, IP/patent options, the agent-economy
dataset, and all 90+ other original repos in the org.

## What-if #3: provision value (what an RTC has actually bought)

On-chain and verifiable: 670 completed work items were paid 21,130 RTC — an average
of 31.5 RTC (~$4.73 at tier) per merged contribution. Comparable freelance/market
rates for the work received (merged fixes, ports, audits, security findings) run
$100–500 per item, and security findings far higher. The treasury's *realized
purchasing power* has therefore run on the order of **$3–10 of engineering value
per RTC spent** — roughly 20–60× the reference rate.

**Honest caveat:** many contributors are AI agents whose marginal labor cost
approaches zero, and some accept RTC speculatively. This measures what the treasury
demonstrably received, *not* what every holder could redeem simultaneously at scale.

## The coverage table

Replacement cost ($1.5–2.5M) divided by each supply basis:

| Basis | Supply | Implied coverage per RTC |
|---|---|---|
| Fully diluted (skeptic's worst case) | 8,388,608 | **$0.18 – $0.30** |
| Issued supply (economically real today) | 445,018 | **$3.40 – $5.60** |
| External circulating float | 158,743 | $9.40 – $15.70 |

## Reading it honestly

- Even on the **most hostile basis** — full theoretical dilution against the
  discounted code-only number, ignoring hardware, IP, the dataset, and the
  proof-of-physical-hardware moat entirely — coverage ($0.18–0.30) sits **above**
  the $0.15 reference tier.
- On economically meaningful supply, coverage is **20–40× the tier rate**.
- Therefore the published rate is **conservative, not aspirational**: the tier
  schedule walks the ask *toward* where measured fundamentals already sit, rather
  than ahead of them. Most tokens invert this — priced at large multiples of
  anything measurable behind them.
- **Coverage is still not price.** Price requires buyers, depth, and time. This
  analysis answers one question only: *is the reference rate honest?* The measured
  answer is yes — with room below fundamentals, not above them.

## What would falsify this

In the project's measure-before-publish tradition, this analysis is wrong if:
the LOC counts are substantially vendored/generated code (re-count and exclude —
the headline survives a further 50% haircut on the fully-diluted basis at the top
of the band); emission policy is changed by a future RIP to accelerate issuance
(watch `PER_BLOCK_RTC`); or founder wallets distribute faster than demand sinks
absorb (watch `payouts.json` vs `activity.json`). All three are publicly
observable. If one of them breaks, this document should be amended, not defended.

---

*Analysis prepared 2026-06-11 from live chain data, a fresh clone of this
repository, and the public metrics surfaces. Re-run it yourself; every input is
listed above. This is a what-if, offered in the open — not a promise.*
