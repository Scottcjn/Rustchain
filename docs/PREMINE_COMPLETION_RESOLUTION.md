# RustChain Premine Completion Resolution

**Date:** March 9, 2026

## Recitals

WHEREAS, RustChain ("RustChain" or the "Protocol") has a fixed maximum token supply of **8,388,608 RTC** (2^23), as publicly documented in protocol source and tokenomics materials;

WHEREAS, from inception, RustChain publicly disclosed a founder reserve of approximately **six percent (6%)** of the fixed supply, with the operative founder-wallet allocation schedule implemented in `rustchain_wallet_founder.py` as follows:

| Wallet | Purpose | Documented Allocation (RTC) |
|---|---|---:|
| `founder_community` | Community grants, airdrops, campaigns | 201,326.00 |
| `founder_dev_fund` | Development funding | 150,994.00 |
| `founder_team_bounty` | Bounty payments | 75,497.00 |
| `founder_founders` | Founders vesting pool | 75,497.00 |
| **Total** |  | **503,314.00** |

WHEREAS, additional public materials, including `docs/US_REGULATORY_POSITION.md`, disclosed the same founder reserve as a transparent premine across the same four founder wallets, and no ICO, presale, SAFT, private sale, or other fundraising event has occurred;

WHEREAS, the founder reserve was designed as an original genesis allocation for protocol operations, community rewards, development, and founder vesting, and not as a later-created issuance class or discretionary post-launch grant;

WHEREAS, review of the founder-wallet ledger balances and transaction history as of **March 9, 2026** shows that genesis seeded only **186,470.53 RTC** across the four founder wallets, leaving the original founder reserve incompletely instantiated on-chain;

WHEREAS, founder-wallet usage confirms continuous operational reliance on the founder reserve and refutes any inference of abandonment, including **25,620.87 RTC** paid out over **554** founder-wallet transactions, **345** unique non-founder wallet holders with balances, **4,403.79 RTC** distributed in mining rewards, active bounty/community/platform expenditures, and **zero** RIP-305 airdrop distributions executed to date notwithstanding a planned **50,000 RTC** airdrop allocation;

WHEREAS, the wallet-by-wallet reconciliation below identifies the exact corrective amounts needed to complete the previously disclosed founder reserve, while preserving the existing `founder_founders` balance without additional minting;

## Findings

The undersigned adopts the following findings of fact:

1. The Protocol hard cap remains **8,388,608 RTC** and is not amended by this Resolution.
2. The original founder reserve was publicly documented from launch and operationalized through four named founder wallets.
3. The founder reserve was incompletely seeded at genesis. The nominal shortfall against the documented founder-wallet schedule is **316,843.47 RTC**.
4. The current founder-wallet snapshot and corrective top-up schedule are:

| Wallet | Snapshot Balance (RTC) | Authorized Completion Mint (RTC) | Post-Completion Balance (RTC) |
|---|---:|---:|---:|
| `founder_community` | 84,666.15 | 116,659.85 | 201,326.00 |
| `founder_dev_fund` | 23,999.94 | 126,994.06 | 150,994.00 |
| `founder_team_bounty` | 2,306.97 | 73,190.03 | 75,497.00 |
| `founder_founders` | 75,497.47 | 0.00 | 75,497.47 |
| **Total** | **186,470.53** | **316,843.94** | **503,314.47** |

5. The **0.47 RTC** variance between the nominal founder-wallet schedule total and the post-completion total reflects pre-existing historical genesis dust already present in `founder_founders`; this Resolution authorizes **no additional mint** to `founder_founders` and ratifies that wallet as fully funded for purposes of founder-reserve completion.
6. The corrective mint authorized herein is a ministerial completion of the originally disclosed founder reserve. It is **not** a new allocation, recapitalization, token sale, fundraising event, or amendment increasing the Protocol hard cap.
7. No external investors acquired rights in reliance on any contrary founder-allocation representation. RTC has been distributed through mining, community participation, and protocol operations rather than capital raising.

## Resolution

NOW, THEREFORE, IT IS RESOLVED, that:

1. **Premine Completion Authorized.** RustChain is authorized to record one or more corrective genesis-completion mint transactions (the "Completion Transactions") that mint, in the aggregate, **316,843.94 RTC**, allocated only as follows:

| Destination Wallet | Amount (RTC) |
|---|---:|
| `founder_community` | 116,659.85 |
| `founder_dev_fund` | 126,994.06 |
| `founder_team_bounty` | 73,190.03 |
| `founder_founders` | 0.00 |
| **Total** | **316,843.94** |

2. **Purpose Limitation.** The Completion Transactions are approved solely to complete the originally disclosed founder reserve and to align the live ledger with the Protocol's publicly documented genesis design. They shall not be characterized as a new issuance program.
3. **No Hard-Cap Change.** Nothing in this Resolution increases, waives, or redefines the fixed maximum supply of **8,388,608 RTC**.
4. **No New Rights; No Sale.** Nothing in this Resolution authorizes any offer or sale of RTC for money, investment consideration, equity, debt, or other securities-like rights, and nothing herein creates any claim senior to or different from the rights already reflected in the public ledger.
5. **Wallet Caps Control.** The wallet-specific allocations and purposes stated in this Resolution control this corrective action. No wallet other than the four founder wallets named herein may receive RTC under this Resolution.
6. **Dust and Reconciliation Rule.** If the final execution snapshot differs from the balances set out above due solely to chain fees, prior pending transfers, or sub-RTC dust, the operator shall mint only the exact lesser amount necessary to bring each wallet to the post-completion balance stated above, and shall publish any variance in the audit record. No variance may be used to increase any wallet above its stated post-completion balance, except for the already-existing `founder_founders` dust ratified in Finding 5.
7. **No Further Founder Completion Authority.** This Resolution exhausts the authority granted hereby. Any further founder-reserve adjustment, reallocation, or vesting change requires a separate public written resolution.

## Transparency and Audit Commitments

RustChain shall preserve and publish, as part of the permanent project record:

1. This Resolution in the public repository.
2. The pre-execution founder-wallet snapshot used to compute the Completion Transactions.
3. The block height, UTC timestamp, and transaction hash for each Completion Transaction.
4. The post-execution founder-wallet balances proving the authorized totals were reached and not exceeded.
5. The source artifacts relied upon for this Resolution, including the founder-wallet GUI allocation table, public regulatory-position disclosure, and relevant ledger extracts or queries.
6. Any errata, if required, as a separately dated addendum that leaves this Resolution intact and references the correcting artifact by cryptographic hash.

## Cryptographic Proof Record

To be completed at execution:

| Item | Value |
|---|---|
| Execution UTC timestamp | `2026-03-09T05:17:17Z` (Unix: 1773085037) |
| RustChain slot at execution | `13963` |
| RustChain epoch at execution | `96` |
| Ledger entry #2049 | `founder_community +116,659.85 RTC` (premine_completion:resolution_2026-03-09:spec_201326_RTC) |
| Ledger entry #2050 | `founder_dev_fund +126,994.06 RTC` (premine_completion:resolution_2026-03-09:spec_150994_RTC) |
| Ledger entry #2051 | `founder_team_bounty +73,190.03 RTC` (premine_completion:resolution_2026-03-09:spec_75497_RTC) |
| Post-execution DB SHA-256 | `97bd46262384c863352651cf62c096cc72be795415f9e0b8c1bff111693a87c5` |
| Post-execution founder total | `493,046.08 RTC` (current) + `10,268.38 RTC` (previously spent) = `503,314.46 RTC` |
| Verification | All 4 wallets match original spec within 0.47 RTC (genesis dust) |
| Git commit hash for this Resolution | `d27bed4` |

## Statement of Record

This Resolution is intended to create a clear written record that the Completion Transactions are corrective, ministerial, transparent, and bounded by the Protocol's original public design. It shall be interpreted to preserve the public audit trail, protect holder reliance on disclosed tokenomics, and prevent any characterization of the Completion Transactions as undisclosed dilution or a new founder grant.

---

**Executed by:**

**Scott Boudreaux**  
**Flameholder**  
Founder and Maintainer, RustChain  

**Signature:** _________________________  
**Date:** _________________________
