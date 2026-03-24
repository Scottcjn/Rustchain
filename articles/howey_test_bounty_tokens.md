---
title: "Is Your Crypto Bounty Token a Security? A Developer's Guide to the Howey Test"
published: false
description: "Not every token is created equal. Learn how the 1946 Howey Test applies to developer bounty tokens, and why the distinction between earned and purchased tokens matters more than ever."
tags: crypto, blockchain, opensource, security
cover_image: https://rustchain.org/images/howey-test-dev-guide-og.png
canonical_url: https://rustchain.org/blog/howey-test-bounty-tokens
---

If you run an open-source project that pays contributors in tokens, you need to understand the Howey Test. Not because you are a securities lawyer. Because the SEC does not care whether you think your token is a utility -- they care whether it walks like a security, swims like a security, and quacks like a security.

This article is a developer's field guide. We will walk through the legal framework, then apply it to real patterns you see in bounty token projects.

---

## What Is the Howey Test?

In 1946, the U.S. Supreme Court decided *SEC v. W.J. Howey Co.*, a case about Florida orange groves. The Howey company sold tracts of citrus land along with a service contract to cultivate and harvest the fruit. The buyers did no farming. They just collected checks.

The Court ruled this was an "investment contract" -- a security -- because it met four conditions. These four prongs are now the standard test for whether any asset is a security under U.S. law:

1. **An investment of money** -- Someone pays value to acquire the asset.
2. **In a common enterprise** -- The investors' fortunes are pooled or tied to the same venture.
3. **With an expectation of profits** -- The buyer anticipates returns.
4. **Derived primarily from the efforts of others** -- Those returns depend on work done by a promoter or third party, not the buyer.

All four prongs must be met. If any one fails, the asset is not a security under Howey.

This sounds simple. It is not. Let us look at how it plays out for bounty tokens.

---

## When Bounty Tokens Are Likely Securities

Consider a hypothetical project: **CoinBounty**. The founder mints a token on a smart-contract platform, sets up a bonding curve for public purchase, and announces: "Earn tokens by contributing to our repos! Also, buy them on our bonding curve -- early buyers get the best price."

Let us apply Howey.

### Prong 1: Investment of Money

The bonding curve is a purchase mechanism. Users send SOL, ETH, or stablecoins and receive CoinBounty tokens in return. That is an investment of money, full stop. It does not matter that *some* tokens are also earned through work. If there is a purchase path, Prong 1 is met for every token acquired through it.

### Prong 2: Common Enterprise

All token holders share a common pool. When the founder markets the token, everyone's holdings rise. When interest fades, everyone's holdings fall. The fortunes of buyers and contributors are tied to the same venture. Prong 2 is almost always met for fungible tokens.

### Prong 3: Expectation of Profits

If the project's Discord says "get in early," "token will moon," or "we're listing on [exchange] next month" -- that is an explicit expectation of profits. Even without those statements, a bonding curve *by construction* implies that early buyers profit from later buyers. The mechanism itself creates the expectation. Prong 3 is met.

### Prong 4: Efforts of Others

This is the killer prong for most bounty tokens. Ask: where does the token's value come from?

If the answer is "the founder's marketing, the founder's exchange listings, the founder's partnership announcements" -- that is the efforts of others. The buyer sitting on a bonding curve position is not doing anything. They are waiting for the founder to make their tokens worth more.

**All four prongs met. CoinBounty tokens purchased on the bonding curve are likely securities.**

Even the *earned* tokens become legally complicated when there is a parallel purchase market, because the existence of a liquid speculative market changes the "expectation of profits" analysis for everyone.

---

## When Bounty Tokens Are Likely NOT Securities

Now consider a different model. A project has been running for over a year. There is no token sale. No bonding curve. No exchange listing. The only way to acquire the token is to do real, verifiable work.

### Prong 1: Investment of Money

No one purchases the token. Contributors earn it by writing code, mining on real hardware, running infrastructure, or completing audits. There is no investment of money because there is no purchase mechanism.

Some legal scholars argue that contributing labor constitutes an "investment." Courts have generally rejected this when the labor produces standalone value (code that works, infrastructure that runs) rather than being purely speculative (buying a lottery ticket).

### Prong 2: Common Enterprise

This prong often still applies -- contributors and the network share a common interest. But without Prong 1, the analysis is already weakened.

### Prong 3: Expectation of Profits

If the token has real utility -- paying for network fees, purchasing compute jobs, settling agent-to-agent transactions -- then holders use the token, they do not just hold it hoping for appreciation. The token is more like arcade tokens at a bowling alley than shares in a company.

Consider a concrete example: a token earned by attesting real hardware (PowerPC G4s, SPARC workstations, IBM POWER8 servers) to a blockchain through six layers of physical fingerprinting. The token pays for transaction fees on that network. Miners earn it by running actual machines that consume actual electricity. The network uses it to settle cross-chain anchoring fees. This is utility, not speculation.

### Prong 4: Efforts of Others

When miners earn tokens through their own hardware, their own electricity, and their own uptime -- the profits derive from the efforts of the token holder, not a third party. A miner running a Power Mac G5 that earns tokens through attestation is more like a farmer growing oranges than an investor buying orange grove shares.

**Prong 1 fails. Prong 3 is weakened. Prong 4 fails. The token is likely not a security.**

---

## The March 2026 SEC-CFTC Guidance

In March 2026, the SEC and CFTC issued joint guidance clarifying the regulatory landscape for digital assets. Key points:

- **Bitcoin, Ethereum, and Solana** were classified as **commodities**, not securities. This was significant for SOL holders and the broader Solana ecosystem.

- However -- and this is the part many developers miss -- **tokens launched *on* Solana (or any chain) with bonding curves still face Howey scrutiny on their own merits.** The underlying chain being a commodity does not make every token on it a commodity. SOL is a commodity. A token launched via a bonding curve on Solana three days ago with an anonymous founder is a completely different analysis.

- The guidance emphasized **"functional utility at time of distribution"** as a key differentiator. A token that *does something* from day one is treated differently than a token sold with promises of future utility.

- The **"efforts of others"** prong was specifically highlighted as the deciding factor in most borderline cases.

The message to developers is clear: how your token is distributed matters as much as what it does.

---

## Red Flags: Your Bounty Token Might Be a Security

Watch for these patterns. Any one is concerning. Multiple together are a serious problem.

**No infrastructure behind the token.** The token launched in days. The smart contract is the entire project. There is no node software, no hardware requirement, no sustained operation -- just a token and a pitch deck.

**Bonding curve as primary distribution.** If most tokens are acquired through purchase rather than work, the "bounty" framing is cosmetic. Calling something a "bounty token" while selling 90% of supply on a bonding curve does not change the legal analysis.

**Empty repositories.** The GitHub org has repos with README files and not much else. The token exists before the software does. This is the opposite of how legitimate work-for-tokens projects operate.

**"Get in early" messaging.** Any communication that emphasizes price appreciation over utility is building an expectation of profits. Screenshots of price charts in Discord. "We're up 400% this week." This is marketing a security.

**Founder holds majority supply.** If one wallet controls 60% of tokens and the bonding curve lets them sell into public demand, the entire token economy depends on the founder's decisions. Classic "efforts of others."

**No work verification.** Bounties are awarded for trivially completable tasks, or awarded by a single person with no review process. The "work" is a fig leaf over a distribution mechanism.

---

## Green Flags: Your Bounty Token Is Probably Not a Security

These patterns point toward a utility token earned through real work.

**Months or years of continuous operation.** The network has been running. Blocks have been produced. Miners have attested. The token did not appear overnight -- it emerged from sustained engineering.

**Public ledger with verifiable transactions.** Anyone can inspect the chain. Block explorers show real transactions. Epoch settlements are auditable. The system does not require trust in a single party.

**Real infrastructure.** Physical nodes running on real hardware. Hardware attestation that cannot be faked with VMs. Cross-chain anchoring that commits data to independent blockchains. This is not a smart contract on someone else's chain -- it is an actual network.

**No purchase mechanism.** You cannot buy the token. You earn it. Through mining, through code contributions, through running infrastructure, through completing security audits. Every token in circulation represents work that someone did.

**Utility from day one.** The token pays for transaction fees. It settles compute jobs. It funds agent-to-agent transactions. People *use* the token, not just hold it.

**Hardware requirements prevent speculation.** When earning tokens requires owning and operating specific physical hardware -- vintage PowerPC machines, SPARC workstations, RISC-V boards -- the barrier to entry is physical, not financial. You cannot spin up a VM farm and print tokens. The silicon is the proof.

---

## A Decision Framework for Your Project

If you are building a bounty token system, ask yourself these questions:

**Can someone acquire your token without doing any work?**
If yes, you have a Howey problem on Prong 1.

**Does your token do anything besides sit in a wallet and (hopefully) appreciate?**
If no, you have a Howey problem on Prong 3.

**If the founder disappeared tomorrow, would the token still have value?**
If no, you have a Howey problem on Prong 4.

**Is your "bounty" label just a rebranding of a token sale?**
Be honest with yourself. The SEC will be.

---

## What This Means for Open-Source Developers

The crypto space has a pattern: someone sees a working model, copies the surface aesthetics, and adds a bonding curve. The original earns tokens through hardware attestation, code contributions, and years of infrastructure work. The copy earns tokens through... buying them.

These are not the same thing. The law does not treat them as the same thing. And increasingly, regulators are getting specific about the distinction.

If you are a developer contributing to bounty programs, look at how the token is distributed before you invest time. If the primary path to tokens is purchasing them, you are contributing to a project that may face regulatory risk regardless of how good the code is.

If you are building a bounty token system, build the infrastructure first. Make the token useful before you make it tradeable. Earn credibility through operation, not promises.

The Howey Test is 80 years old. It was written for orange groves. But its logic is timeless: if people are buying something purely because they expect a promoter to make it valuable, that is a security. If people are earning something through their own work and using it for its intended purpose, it is not.

Build the orange grove. Do not just sell shares in one.

---

*Disclaimer: This article is educational content for software developers evaluating token project architectures. It is not legal advice. Consult a securities attorney for guidance specific to your project.*

*The author maintains [RustChain](https://rustchain.org), an open-source blockchain where RTC tokens are earned exclusively through hardware attestation and code contributions, with no purchase mechanism.*
