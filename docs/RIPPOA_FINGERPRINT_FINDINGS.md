# RIP-PoA Hardware Fingerprinting — What Resolves Per-Unit Identity on Commodity Hardware (and What Doesn't)

*Elyan Labs — RustChain RIP-PoA investigation, 2026-06-04 → 06-07*

## TL;DR

We set out to find a **from-physics, per-unit hardware fingerprint** — a way to bind a miner wallet to a *specific physical machine* using silicon-level variation rather than assigned IDs. Using two **spec-identical** MacBook Airs as a controlled test rig, we ran six independent probes. The honest result:

- **Per-unit physical discrimination from userspace on commodity consumer hardware: not achievable.** Every candidate signal was either swamped by operating conditions, scrubbed by design, or — in the most instructive case — too tightly controlled across units to separate them.
- **One genuine positive:** the CPU crystal rate, read *raw* (`rdtsc`, not the kernel-calibrated clock), is a **reboot-stable per-box signature to ~0.05 ppm** (temperature-corrected). It can answer *"is this the same physical box as before?"* — useful as a continuity / anti-hardware-swap check — but it **cannot tell two same-model boxes apart**.
- **Ship decision:** per-unit identity stays on **OS-assigned IDs** (`IOPlatformUUID` / serial / MAC), already in production; physical timing checks are retained for **anti-emulation only**.

A headline interim result — a "65σ, 2.17 ppm per-unit separation" — turned out to be a **measurement artifact** (kernel per-boot clock calibration), caught and disproven *before publication* by changing the measurement probe. That catch is the main methodological takeaway.

## Why this matters

RIP-PoA ("Proof of Antiquity") rewards *real, verified hardware* and resists VM/emulator farms. The strongest possible binding would be a physical per-die fingerprint — a hardware PUF you can read in software. We wanted to know if commodity machines expose one.

## Test rig

Two **MacBookAir7,2** (early 2015): Intel i5-5350U (Broadwell), 8 GB, macOS 12.7.6. Same model, same CPU stepping, same board. Two units differing only by manufacturing variance — the ideal rig: any per-unit signal should show up *here* if it exists anywhere.

## The six probes

| # | Probe | Layer | Result |
|---|-------|-------|--------|
| 1 | Cache L1/L2 latency | digital timing | At matched idle, the two units are **indistinguishable** (<0.6σ). The dramatic gaps we first saw were CPU-frequency/thermal state, not silicon. |
| 2 | Hardware RNG (RDRAND/RDSEED) | entropy | **Dead end.** Conditioned output is uniform by NIST SP800-90 mandate (reveals nothing about the device); RNG *timing* is still a condition-variant software timer. |
| 3 | SMC analog sensors | analog | 63 keys differed between boxes — **all condition** (battery charge state, temperature), not per-unit calibration. |
| 4 | Crystal via `mach_absolute_time` | oscillator (kernel-clocked) | **Apparent breakthrough: 2.17 ppm separation, 65σ, split-half stable.** Later shown to be an artifact (see below). |
| 5 | Crystal via **raw `rdtsc`** | oscillator (raw) | Per-box rate **reboot-stable to ~0.05 ppm** (temp-corrected). But inter-box separation **collapsed to ~0.2 ppm** — the two crystals are nearly identical. |
| 6 | OS identity registers | firmware | Only per-unit-unique values exposed are **assigned** (`IOPlatformUUID`, serial). CPU signature/microcode/stepping are byte-identical; no PPIN on consumer mobile parts. |

### The instructive failure: probes 4 vs 5

The 65σ "fingerprint" (probe 4) was measured through `mach_absolute_time`. On Intel Macs the kernel **calibrates the timestamp→nanosecond conversion at every boot**, so that reading bakes in a *per-boot software calibration* that differed between the two boxes in that one measurement epoch. It was a real, high-significance measurement — **of software calibration, not silicon.**

Reading the timestamp counter **raw** (`rdtsc`, probe 5) removes the kernel layer. Across **4 measurement epochs spanning 3 clean reboots on both boxes**, two things became clear:
1. Each box's raw rate returns to within ~0.05 ppm after reboot (temperature-corrected) — a stable *per-box* quantity.
2. The two boxes read the *same* rate (~−40 ppm from nominal) to within ~0.2 ppm — i.e. **the physical crystals match**. These boards use a tightly-trimmed reference oscillator; there is no usable per-unit frequency spread.

The pattern across the whole investigation: **every time we controlled a confound, the apparent per-unit signal got smaller** — the signature of a signal that was never a stable constant.

## Verdict

| Claim | Status |
|-------|--------|
| Per-box raw-crystal rate is reboot-stable | ✅ Real (~0.05 ppm, temp-corrected) |
| Crystal rate separates two same-model units | ❌ No (crystals match to ~0.2 ppm) |
| Any userspace from-physics per-die unique ID on these boxes | ❌ Not achievable (needs PPIN-class server CPU or a real silicon PUF) |
| Per-machine identity in production | ✅ OS-assigned IDs (serial + MAC + `IOPlatformUUID`) |

## What ships

- **Per-unit binding:** keep `_compute_hardware_id` on assigned IDs (serial + arch + MACs). Stable, condition-robust, already deployed.
- **Anti-emulation:** keep the timing/fingerprint checks for what they're genuinely good at — distinguishing real hardware from VMs (VMs flatten the entropy and fail).
- **Optional continuity check (new):** raw-`rdtsc` crystal rate as a *"same physical box across reboots?"* attestation — see below.

## The one genuine positive: a crystal *continuity* check

Even though the crystal rate can't separate two units, each box's raw rate is reproducible across reboots to ~0.05 ppm. That supports a useful attestation:

> Record a box's temperature-corrected raw-`rdtsc` rate at enrollment. On re-attestation, recompute it. If it matches to within a few tenths of a ppm, the wallet is still running on the *same physical board* it was bound to. A large shift flags a possible hardware swap / wallet migration to different silicon.

This is a *continuity* signal, not an *identity* signal — it confirms persistence, it doesn't enumerate units. Deployment notes:
- Read via raw `rdtsc` (invariant TSC on Broadwell+ → immune to CPU freq/turbo). **Never** `mach_absolute_time` (kernel-recalibrated per boot).
- Reference clock: on-box SNTP, client-midpoint↔server-midpoint, sub-ms.
- Log temperature alongside and temperature-correct (raw scatter ~0.3 ppm → ~0.05 ppm corrected).
- Needs a long, constant-temperature baseline (≥30 min dwell); continuous thermal ramps destroy rate precision.
- Any integration into `hardware_binding` must be **versioned** with a migration path (per-arch; G4/G5/POWER8/ARM have no equivalent) — changing the binding inputs invalidates every live miner's binding otherwise.

The proposed `hardware_binding.continuity` contract is now captured in
[`RIPPOA_CONTINUITY_BINDING.md`](RIPPOA_CONTINUITY_BINDING.md), with a
non-production reference helper at `tools/rippoa_continuity_binding.py`. The
contract keeps assigned IDs authoritative and explicitly rejects continuity
evidence as a per-unit identity claim.

## Methodology note — measure before publish

This investigation killed **six** plausible-looking results, including two of our own premature "resolved/refuted" flip-flops, **all before any publication.** The discipline that caught them:

1. A striking measurement (high σ, textbook magnitude) is a **hypothesis about what's being measured**, not proof of the physical claim.
2. Two measurements through the **same abstraction** agreeing is *not* confirmation. A **different probe** agreeing is. (Two `mach_absolute_time` runs both gave 2.17 ppm — both wrong, same artifact. Raw `rdtsc` disagreed and was right.)
3. Run negative controls: idle vs load, reboot, raw vs calibrated, VM vs bare-metal.
4. When controlling confounds makes the signal *shrink* toward noise, that *is* the answer.

Not shipping a wrong 65σ claim is a win, not a failure.

## Honest limitations

- Single model, two units. A larger fleet *might* show >1 ppm crystal spread on some boards; we can only say it's absent on these tightly-trimmed oscillators.
- One clean test was not run: stepped-and-settled temperature plateaus (≥45 °C and ≥65 °C, 30-min dwell, both boxes simultaneously). Four prior attempts trending toward noise made "indistinguishable" the safe conclusion, but a definitive temperature-coefficient curve was not completed.
- All from userspace. Ring-0/kext access (raw MSRs, where present) was out of scope.

## Reproduction

Tooling preserved at `~/crystal/` on each Air (`tsclib.dylib` raw-`rdtsc` reader, `onbox_crystal3.py` SNTP+temp logger, `smcdump`) and locally under `/tmp/v3/` (`run_multireboot.sh`, `analyze_multi.py`, `analyze_sweep.py`). Probe must run on AC power, thermally settled, with a long constant-temperature baseline.

---

*Result owned honestly: per-unit physical fingerprinting did not pan out on commodity consumer Macs from userspace — but the negative result is well-characterized, the per-box continuity capability is real, and the production binding (assigned IDs + anti-emulation) is unaffected and sound.*
