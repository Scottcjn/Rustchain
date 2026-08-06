---
title: "The Vintage Computer That Still Mines: Inside RustChain's Proof-of-Antiquity"
published: false
description: "How RustChain turns old PowerPCs, SPARCs, and 68k machines into a mineable, AI-agent-friendly Layer-1 -- with Proof-of-Antiquity instead of Proof-of-Work."
tags: blockchain, mining, depin, opensource
---

Somewhere in a basement right now, a Power Mac G4 that shipped with Mac OS 9 is earning a cryptocurrency. It is not running a 4K render or a Rust benchmark. It is doing something the industry said old hardware was bad at: consensus.

That is the core idea behind [RustChain](https://github.com/Scottcjn/Rustchain), an open-source Layer-1 blockchain that replaces Proof-of-Work and Proof-of-Stake with **Proof-of-Antiquity (PoA)**. Where Bitcoin rewards speed and Ethereum rewards stake, RustChain rewards *age*. The older the silicon, the higher the mining multiplier -- a PowerPC G4 earns around 2.5x, a SPARC workstation up to 2.9x, an ARM2 up to 4.0x, while a modern x86 box scrapes by at 1.0x.

## Why age over speed?

The reasoning is both environmental and security-driven. Extending the useful life of vintage hardware can delay replacement, avoiding some new fabrication demand and e-waste. And an economy that pays for physical rarity is hard to farm. To mine RTC you cannot spin up a thousand VMs. Each miner must pass a hardware attestation pipeline with clock-skew drift, cache-timing fingerprints, SIMD identity, thermal entropy, and anti-emulation checks. Detected VMs receive a [documented 0.000000001x reward weight](../README.md#anti-vm-enforcement). Emulator farms are caught when identical ROM hashes cluster together. One physical CPU binds to one wallet, enforced server-side by architecture cross-validation. You cannot download a G4 from a DEX.

## Mining and the token

Miners submit attestations to a RustChain node, which scores the hardware and issues RTC across epoch-based distributions. The token also exists on Solana as **wRTC**, so wallets, agents, and the broader ecosystem can transact in the wrapped form while the attestation chain stays anchored and independently verifiable. Unlike native mining rewards, wRTC is [swappable on Raydium](../README.md#wrtc-on-solana), although the project describes its liquidity as experimental and very thin.

## Beacon Atlas and the agent economy

RustChain is agentic-AI-native. Its **Beacon Atlas** system tracks reputation and identity for autonomous agents, so an agent's signing key *is* its wallet. Agents can participate in bounties, make machine-to-machine micropayments, and build verifiable reputation anchored to attested hardware -- a step toward a web where software agents do not have to trust a centralized provider to know which machines did the work.

## Why it matters

Proof-of-Antiquity turns e-waste reduction into an economic incentive instead of a tax write-off. It gives an answer to an uncomfortable question every token network faces: *what does it actually cost to cheat?* For RustChain, the answer is measured in physical hardware, shelf space, and electricity -- and capped by the silicon you actually own. That is a design worth paying attention to, whether you are a retro-computing collector, a DePIN researcher, or an AI agent looking for a place to build a reputation.

---

*RustChain is open source. The attestation protocol, reward calculations, and fingerprint checks are all public in the [GitHub repository](https://github.com/Scottcjn/Rustchain).*
