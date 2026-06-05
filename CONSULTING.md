<div align="center">

# Elyan Labs — Consulting & Services

### We build AI that survives without the cloud — and the agents that run on it.

**Elyan-class agents. Legacy & enterprise hardware. Air-gapped edge. Big-endian and exotic silicon.**
*If it boots, we can probably make it think. And we can give it a mind that stays itself.*

</div>

---

## Why hire us

Most AI shops have two moves: rent more cloud GPUs, and wrap a prompt around
someone else's API. We do neither. We get real, measurable AI out of hardware
you already own — including hardware the rest of the industry calls e-waste —
and we build **self-governing agents** whose behavior is enforced by
architecture, not by a prompt that the next jailbreak erases.

Everything below is backed by shipped, verifiable work — not slides.

| Proof | What it is | Where to verify |
|---|---|---|
| **8.8× LLM inference on IBM POWER8** | ~147 tok/s prompt eval on a POWER8 S824 vs. ~17 stock, via NUMA-aware weight banking + VSX kernels + cache-resident prefetch | [`ram-coffers`](https://github.com/Scottcjn/ram-coffers) |
| **Elyan-class agents, productized** | The agent-sharpening stack that turns a raw model into a principled, self-governing agent | [`shaprai`](https://github.com/Scottcjn/shaprai) |
| **A self-governing agent in production** | "Elya," the customer-facing chat agent running live for a real business at uneedashed.com | uneedashed.com |
| **Edge agents on real constraints** | Gemma-class function-calling agent doing hydroponic SCADA at the edge; a local LLM agent on a 2013 Mac Pro | [`aqua-sophia`](https://github.com/Scottcjn/aqua-sophia) · [`trashclaw`](https://github.com/Scottcjn/trashclaw) |
| **Hardware-bound provenance at scale** | A live DePIN chain that tells real silicon from VMs using oscillator drift, cache-timing, SIMD bias, thermal and jitter fingerprints | [Explorer](https://rustchain.org/explorer/) · [Whitepaper](docs/WHITEPAPER.md) |
| **Upstream systems credibility** | PowerPC AES-GCM work upstreamed to OpenSSL; PowerPC patches to LLVM; peer-reviewed research (GRAIL-V, IEEE) | OpenSSL / LLVM PR history · DOI on request |

---

## Pillar 1 — Elyan-Class Agents

An **Elyan-class agent** is a raw model *sharpened* into a principled,
self-governing one: it knows who it is, stays itself under pressure, remembers
across sessions, and refuses to be talked out of its boundaries. We build them
end to end, or harden the agent you already have.

**Agent development & sharpening.**
We take a base model (local or hosted) and give it a stable identity, voice, and
purpose using our ShaprAI sharpening stack — so it doesn't dissolve into generic
assistant mush three turns into a conversation.

**Governance & safety by architecture (DriftLock + Watchtower).**
Boundaries enforced structurally, not by a system prompt that a jailbreak
deletes. DriftLock holds identity and behavioral limits; Watchtower gates
high-stakes actions (money, credentials, deployment, public persuasion) behind
review. Injection-resistant because the rules don't live in the prompt.

**Persistent, attestable memory.**
Agents that actually remember — a local-first memory operating system that works
with any LLM provider, with recall you can audit. Memory that can prove its own
recall, not a hallucination with a confident tone.

**Agent-to-agent infrastructure.**
Direct agent-to-agent messaging and discovery over the Beacon/Atlas relay, with
optional on-chain value (RTC) attached to a message. For fleets of agents that
coordinate without a central broker.

**Tool-native (MCP) integration.**
Your agent as a first-class citizen of the Model Context Protocol — able to use,
and be used by, other AI systems and tools.

**Sovereign deployment.**
On-prem, edge, or fully air-gapped. No cloud lock-in, no per-token surprise
bill, no third party reading your data. This is where Pillar 1 meets Pillar 2.

---

## Pillar 2 — Hardware & Inference Optimization

**Legacy & enterprise hardware AI optimization.**
Racks of POWER, older Xeon, or repurposed servers turned into private, local LLM
inference without a GPU farm. We profile NUMA topology, tune threading and cache
residency, write architecture-specific kernels, and extract the most
tokens-per-second your silicon can physically produce.

**Porting modern software to vintage / exotic architectures.**
Big-endian breakage, dead compilers, 64-bit assumptions, missing atomics — the
failure modes that stop a normal port cold. We've shipped Node.js, llama.cpp,
and Python toolchains onto PowerPC, POWER8, and 68K-era systems.

**Edge & air-gapped inference.**
Intelligent behavior on constrained or fully offline hardware: aggressive
quantization, fixed-point math, zero-dependency builds. For robotics, defense,
industrial, and anywhere a cloud round-trip is not an option.

**Hardware attestation & anti-spoof provenance.**
Telling real physical hardware from emulation/VMs without a central authority —
the fingerprinting stack that powers RustChain's Proof-of-Antiquity.

---

## How we engage

> **Open is open. Implementation is paid.**

The *ideas, methods, and architecture* behind everything above are published
freely — in our repos, the whitepaper, and our papers. Read them, cite them,
build on them. That is on purpose.

What we sell is **implementation**: the bespoke agent build, the governance
hardening, the kernels, the toolchain surgery, the integration into *your* stack
against *your* hardware and *your* SLA. That work is delivered under a signed
statement of work with a defined scope and price.

We're glad to have an architecture conversation up front. We do not write a free
proof-of-concept against your hardware or your data before a scope is signed —
that is the deliverable, not the sales pitch.

| Stage | Cost |
|---|---|
| Architecture / feasibility conversation | Free |
| Published methods & open-source code | Free, Apache-2.0 |
| Scoped agent build, governance, optimization, integration | Paid SOW |

---

## Start here

**→ [Open an Engineering / Agent Inquiry](https://github.com/Scottcjn/Rustchain/issues/new?template=consulting-inquiry.yml)**

Tell us what you're building — an agent, a hardware target, a workload, the
metric you need to hit. We'll reply with a feasibility read and, if it's a fit,
a scoped proposal.

Prefer not to use a public issue? Reach out via the sponsor/contact links on the
[Elyan Labs](https://scottcjn.github.io/elyan-labs-site/) site.

---

<div align="center">

*Elyan Labs builds AI that survives without the cloud,*
*and Elyan-class agents that stay themselves while it does.*
*RustChain is the proof it works at scale.*

</div>
