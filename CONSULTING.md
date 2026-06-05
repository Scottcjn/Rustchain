<div align="center">

# Elyan Labs — Consulting

### We make machines everyone else gave up on run modern AI.

**Legacy enterprise iron. Vintage silicon. Air-gapped edge. Big-endian and exotic ISAs.**
*If it boots, we can probably make it think.*

</div>

---

## Why hire us

Most AI shops have one move: rent more cloud GPUs. We do the opposite — we get
real, measurable inference out of hardware you already own, including hardware
the rest of the industry calls e-waste. That is the entire thesis behind
RustChain, and it is backed by shipped, verifiable work — not slides.

| Proof | What it is | Where to verify |
|---|---|---|
| **8.8× LLM inference on IBM POWER8** | ~147 tok/s prompt eval on a POWER8 S824 vs. ~17 stock, via NUMA-aware weight banking + VSX kernels + cache-resident prefetch | [`ram-coffers`](https://github.com/Scottcjn/ram-coffers) |
| **Modern toolchains on dead platforms** | GCC 10 / Perl 5.34 for PowerPC Mac OS X Tiger & Leopard; Node.js builds on a Power Mac G5 | [`ppc-compilers`](https://github.com/Scottcjn/ppc-compilers) |
| **Hardware-bound provenance at scale** | A live DePIN chain that tells real silicon from VMs using oscillator drift, cache-timing, SIMD bias, thermal and jitter fingerprints | [Explorer](https://rustchain.org/explorer/) · [Whitepaper](docs/WHITEPAPER.md) |
| **Upstream systems credibility** | PowerPC AES-GCM work upstreamed to OpenSSL; PowerPC patches to LLVM | OpenSSL / LLVM PR history |
| **Peer-reviewed research** | GRAIL-V (IEEE) | DOI on request |

We don't theorize about constraints. We deliver to POWER8 servers, vintage
PowerPC Macs, and a production blockchain — on real hardware, under real load.

---

## What we do

**1. Legacy & enterprise hardware AI optimization.**
You have racks of POWER, older Xeon, or repurposed servers and want private,
local LLM inference without buying a GPU farm. We profile NUMA topology, tune
threading and cache residency, write architecture-specific kernels, and get you
the most tokens-per-second your silicon can physically produce.

**2. Porting modern software to vintage / exotic architectures.**
Big-endian breakage, dead compilers, 64-bit assumptions, missing atomics — the
failure modes that stop a normal port cold. We've shipped Node.js, llama.cpp,
and Python toolchains onto PowerPC, POWER8, and 68K-era systems.

**3. Edge & air-gapped inference.**
Intelligent behavior on constrained or fully offline hardware: aggressive
quantization, fixed-point math, zero-dependency builds. For robotics, defense,
industrial, and anywhere a cloud round-trip is not an option.

**4. Hardware attestation & anti-spoof provenance.**
Telling real physical hardware from emulation/VMs without a central authority —
the fingerprinting stack that powers RustChain's Proof-of-Antiquity.

---

## How we engage

> **Open is open. Implementation is paid.**

The *ideas, methods, and architecture* behind everything above are published
freely — in this repo, in `ram-coffers`, in the whitepaper, in our papers. Read
them, cite them, build on them. That is on purpose.

What we sell is **implementation**: the bespoke kernels, the toolchain surgery,
the integration into *your* stack, the tuning against *your* hardware and *your*
SLA. That work is delivered under a signed statement of work with a defined
scope and price.

We are glad to have an architecture conversation up front. We do not write a
free proof-of-concept against your hardware before a scope is signed — that is
the deliverable, not the sales pitch.

| Stage | Cost |
|---|---|
| Architecture / feasibility conversation | Free |
| Published methods & open-source code | Free, Apache-2.0 |
| Scoped implementation, tuning, drivers, integration | Paid SOW |

---

## Start here

**→ [Open an Engineering Optimization Inquiry](https://github.com/Scottcjn/Rustchain/issues/new?template=consulting-inquiry.yml)**

Tell us the hardware, the workload, and the metric you need to hit. We'll reply
with a feasibility read and, if it's a fit, a scoped proposal.

Prefer not to use a public issue? Reach out via the sponsor/contact links on the
[Elyan Labs](https://rustchain.org) site.

---

<div align="center">

*Elyan Labs builds AI that survives without the cloud.*
*RustChain is the proof it works at scale.*

</div>
