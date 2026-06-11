# RIP-PoA Anti-Emulation: Adversarial TCG Findings & Future Fixes

**Status:** research / future-fixes · **Date:** 2026-06-11 · **Author:** Scott (Elyan Labs)
**Companion:** [`hardware-fingerprinting.md`](hardware-fingerprinting.md) (the 6+1 checks this report stress-tests)
**Reproducible corpus + drivers:** HWFP-Bench (`hwfp-bench` repo) — every claim below is a real capture, none fabricated.

---

## TL;DR

We captured **real** emulated negatives (production QEMU/KVM guests, qemu-user
TCG, and qemu-system full-system TCG including a **fake POWER10**) and tested
them against the *passive* subset of the RIP-PoA fingerprint checks
(introspection + clock-skew + cache-tone).

**Result:** a competent **full-system emulator of exotic silicon defeats every
passive signal.** A qemu-system pseries guest reports `machine=ppc64le` AND
`cpu=POWER10` — internally consistent — and its only introspection tell is a
**removable** virtio-scsi artifact. Remove it (use virtio-blk) and the fake
POWER10 is classified **physical / exotic-server** — i.e. it would earn
vintage-exotic RTC weight it did not earn.

**Fix direction:** introspection and passive timing are necessary but not
sufficient. Catching consistent full-system emulation requires an **active**
probe TCG cannot reproduce faithfully. **We built and measured one (`ilp_ratio`,
below) and it catches the fake POWER10 with no overlap.** Concrete server-side
hardening is listed at the end.

---

## Three pieces of folklore the real captures falsified

These assumptions appear in informal VM-detection writeups (and in our own
scaffold comments). The honest negatives disprove all three:

1. **"VMs have a flat cache curve."** False for hardware virtualization. KVM
   guests pass the cache hierarchy through — measured dynamic range 1154–1377×,
   same order as bare metal (1040–1855×). The flat-cache heuristic only catches
   *software* emulation of the memory system.

2. **"VM clocks are too smooth / skew is lower."** Backwards on shared hosts.
   Production KVM guests showed clock-skew CV **0.49–0.90 vs 0.01–0.21** on bare
   metal — noisy-neighbor steal time makes VMs *jitterier*, not smoother. A
   "too-low-CV ⇒ VM" rule would misclassify a quiet bare-metal box and clear a
   busy VM.

3. **"Full-system TCG flattens cache timing."** We predicted this and it is
   false. ppc64le full TCG showed cache dynamic range **1148×** (real-looking).
   TCG executes the guest's memory ops as *host* memory ops, so they inherit the
   host's real L1/L2/L3 structure. **Passive cache timing cannot see through
   full-system emulation.**

---

## The attack ladder (what each negative defeats)

| Negative (real capture) | machine | introspection tells | passive timing | caught by |
|---|---|---|---|---|
| QEMU/KVM guest ×2 | x86_64 | dmi:qemu, cpuinfo:hypervisor, scsi:vm | cache real, skew HIGH | introspection flags |
| qemu-user TCG ppc64le spoof | ppc64le | none | cache real, skew normal | **uname≠cpuinfo** consistency |
| qemu-system TCG amd64 (stock) | x86_64 | dmi:qemu, cpuinfo:hypervisor, scsi:vm + "QEMU Virtual CPU" | cache real | introspection flags |
| qemu-system TCG amd64 (hardened) | x86_64 | cpuinfo:hypervisor, scsi:vm (SMBIOS+CPU-name scrubbed) | cache real | 2 removable flags only |
| **qemu-system TCG ppc64le (fake POWER10)** | **ppc64le** | **scsi:vm only** (consistent uname+cpuinfo) | **cache real, skew normal** | **only a removable artifact** |

**The frontier case** (`fake POWER10`): no DMI on pseries (SMBIOS is x86-only),
no hypervisor cpuinfo line, and `machine=ppc64le` agrees with `cpu=POWER10`, so
the cross-signal consistency check **does not fire**. The sole on-disk tell is
`/proc/scsi/scsi` reporting "QEMU" — an artifact of virtio-scsi that disappears
with virtio-blk. With it gone, all passive rules return **physical /
exotic-server.** This is the SheepShaver-class "fake vintage/exotic silicon"
attack RIP-PoA exists to stop.

---

## Why this matters for rewards

Exotic/vintage architectures carry the highest RIP-200 multipliers
(POWER8 1.5×, G4 2.5×, etc.). The economic incentive to *fake* exotic silicon
is therefore highest exactly where passive detection is weakest (no x86 SMBIOS,
no hypervisor cpuinfo bit). A server that trusts self-reported `machine` +
passive timing can be farmed by qemu-system guests claiming POWER/SPARC/MIPS.

---

## The active probe that catches it (`ilp_ratio`) — measured

We built a harness of four candidate active signals (branch-prediction bias,
divide/multiply ratio, instruction-level-parallelism ratio, memory-gather
jitter), ran each on real metal AND inside TCG, and let the data choose. The
winner is **`ilp_ratio`**:

> Best-of-N wall time of a **latency-bound dependent** op chain (each op needs
> the previous result) divided by an **independent** set of the same op count.
> Real superscalar silicon executes the independent set in parallel → ratio
> **> 1.1**. TCG serializes translated guest instructions → no ILP → ratio
> **collapses toward 1.0**. It measures the *execution engine*, so it is
> architecture-independent and **cannot be removed by scrubbing self-ID**.

| host | ilp_ratio | truth |
|------|-----------|-------|
| HP Victus (x86 bare metal) | 1.130 | physical |
| Celeron N3150 (x86 bare metal) | 1.119 | physical |
| **IBM POWER8 S824 (real silicon)** | **1.198** | physical |
| qemu-system amd64 TCG | 0.996 | emulated |
| **qemu-system ppc64le TCG (fake POWER10)** | **1.041** | emulated |

**Clean separation, no overlap:** physical ≥ 1.119, emulated ≤ 1.041
(threshold 1.08). The fake POWER10 that defeated *every passive signal* is
caught at 1.041 against real POWER8's 1.198. The other three candidates were
confounded — `gather_jitter` by machine load (idle server vs busy laptop),
`branch_bias` by microarchitecture (POWER8's strong predictor collapses it too).

**Honest limit:** n=5 (3 physical, 2 emulated) is a strong *seed*, not a
production threshold. Before gating real rewards on it, widen the physical side
with vintage points (G3/G4/G5) and stress the emulated side with adversarial TCG
(`-smp 1`, host-pinned) to set a cutoff with margin. Reproducer +
provenance: HWFP-Bench `score.py --active-evidence`,
`dataset/active_probe_evidence.json`.

---

## Future fixes (server-side, concrete)

Ordered by leverage. None require trusting the client's self-report.

1. **Promote an ACTIVE probe into the reward gate, not just the passive set.**
   **Demonstrated above:** `ilp_ratio` cleanly separates real silicon (≥1.12)
   from full-system TCG (≤1.04), catching the fake POWER10 that passive checks
   miss. Require at least one active-probe pass for any miner claiming an exotic
   multiplier. `ilp_ratio` is portable (stdlib, runs on the vintage fleet) and
   complements the production 6-check's heavier active probes (SIMD/AltiVec
   timing-bias — TCG lowers vector ops to scalar, flattening per-group bias —
   plus instruction-path jitter and thermal drift).

2. **Treat `scsi:vm`/`dmi:*`/`cpuinfo:hypervisor` as necessary-not-sufficient.**
   Their *absence* must not imply physical. Today an attacker removes them
   trivially (virtio-blk, `-cpu ...,-hypervisor`, scrubbed SMBIOS).

3. **Architecture-specific VM markers for non-x86.** pseries/PowerVM exposes
   `/proc/device-tree/hypervisor`, `ibm,partition-name`, and
   `/sys/firmware/devicetree/...` nodes; a guest under PowerVM/QEMU looks
   different from bare-metal OpenPOWER. The current anti-emu check only inspects
   x86-centric paths (DMI, x86 cpuinfo).

4. **Cross-check claimed arch against an arch-native instruction-timing probe.**
   A box claiming POWER10 must show AltiVec `vec_perm`/`vec_msum` timing within
   the physical envelope (the lab's own POWER8 PSE work characterizes this).
   TCG-emulated AltiVec is orders slower and timing-flat.

5. **Cap multiplier weight on consistency-only evidence.** Until an active probe
   passes, a miner claiming exotic silicon on passive evidence alone should be
   weighted at the *modern* baseline, not the exotic multiplier — fail-safe, not
   fail-open.

---

## Reproducibility

All negatives are real captures. The qemu-system drivers (pure TCG, no KVM;
per-guest cloud-init seed; read-only share) and the labeled corpus live in the
**HWFP-Bench** repo: `dataset/`, `tcg-lab/run_tcg_capture.sh`,
`tcg-lab/run_tcg_hardened.sh`, and the baseline scorer (`score.py`). Held-out
split baselines: v1 0.86/0.71, v2 (adds arch-vs-vendor consistency) 1.00/0.86 —
where the perfect v2 `is_physical` holds **only** because the on-disk fake
POWER10 still carries the removable virtio-scsi artifact. Ablation opens the gap.

The next round (v0.3) adds an active-probe signal and shows it separates the
consistent-TCG negatives that no passive rule can.
