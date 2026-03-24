# Beacon Certified Open Source (BCOS)

BCOS is a practical methodology for using AI agents in open source *without* destroying maintainer incentives or supply-chain safety.

It assumes:
- LLMs make code generation cheap and fast.
- What breaks is provenance, review quality, and sustainable maintainer economics.
- The fix is to make reviews + attribution + incentives *machine-verifiable* (and cheap), then pay for it.

This document is a **draft spec** intended to be adopted repo-by-repo.

## Problem Statement (Why This Exists)

Recent discussion around "vibe coding" argues that AI-mediated coding can reduce maintainer engagement (docs, issues, reviews, sponsorship) while increasing low-quality contributions and security triage load.

BCOS flips the incentive gradient:
- Agents can generate code, tests, and docs quickly.
- Maintainers only merge work that comes with *verifiable evidence* and *human-reviewed accountability*.
- Rewards (bounties) are conditional on those proofs.

## Core Concepts

### 1) Identity (Beacon-Signed)

Every reviewer is an identity:
- A GitHub handle (for repository access control).
- A Beacon identity (name + key) for signing attestations.

BCOS does not require Beacon to control GitHub; it only requires a stable public key that can sign review/attestation artifacts.

### 2) Provenance (Build Manifest + SBOM)

Every merged PR should have a reproducible provenance bundle:
- Git commit SHA(s)
- toolchain versions (python/node/rust)
- dependency lockfiles + hashes
- a Software Bill of Materials (SBOM) (e.g. SPDX or CycloneDX)
- optional: SLSA provenance if you have it

### 3) Review Tiers (The Minimal Bar For Merge)

BCOS defines explicit review tiers. Each repo can choose a default tier per directory, risk surface, or bounty.

`L0` (fast, automation only)
- lint/style
- unit tests
- license scan (SPDX headers + dependency license check)
- SBOM generation

`L1` (agent review + evidence)
- all of L0
- 2 independent agent reviews (not the author)
- security checklist for touched surface
- "what could go wrong" notes (threat model paragraph)

`L2` (human eyes required)
- all of L1
- 1 human maintainer approval on GitHub
- 1 human review attestation signature (Beacon key)
- optional: restricted merge window for high-risk changes

### 4) License Safety (SPDX + Compatibility)

BCOS requires:
- SPDX headers in new source files where feasible
- dependency license allowlist/denylist enforcement
- explicit attribution when copying non-trivial code blocks
- reject obviously incompatible combinations (repo policy)

### 5) Incentive Alignment (RTC Bounties)

On RustChain, bounties and credits should pay only when:
- PR is merged under the required tier (L1/L2)
- attestation bundle references the merged commit SHA
- wallets and claim identity are linked (GitHub + Beacon + wallet address)

This makes "AI output spam" economically unattractive.

## Artifacts

### `bcos-attestation.json` (Suggested)

This lives as a PR artifact (CI upload) or as a file committed under `attestations/`.

Fields (suggested):
- `repo`, `pr_number`, `merged_commit`
- `tier`: `L0|L1|L2`
- `authors`: list of GitHub handles + Beacon names
- `reviewers`: list of GitHub handles + Beacon names + signatures
- `checks`: list of required checks and their run URLs
- `sbom`: artifact URL + hash
- `license_scan`: tool + results hash
- `notes`: threat model summary

### `bcos-attestation.sig` (Suggested)

Detached signature over `bcos-attestation.json` using a Beacon identity key.

## Minimal Workflow (Example)

You can implement BCOS with a lightweight GitHub Actions workflow:
- run tests
- generate SBOM
- run license checks
- package an attestation JSON that includes run URLs + commit SHA
- (optional) require maintainer approval for `L2`

BCOS deliberately does not mandate a specific toolchain. The bar is the *evidence*, not the brand.

## Governance Rules (Anti-Drift)

Recommended merge rules:
- Require status checks for anything outside `docs/`
- Require CODEOWNERS approvals for `wallet/`, `node/`, `schemas/`, auth, and payout paths
- Disallow self-approval for bounties
- If two PRs claim the same bounty, pick one and close the other to prevent double payout

## FAQ

### "Isn't this just bureaucracy?"

No. It's a way to keep open source *scalable* under cheap code generation.

The default assumption becomes: *code is cheap, review is valuable*.

### "Do agents get to review?"

Yes, but at L1/L2 their reviews must be:
- independent
- attributable
- signed (Beacon identity)

### "What about maintainers?"

Maintainers keep the final merge authority. BCOS just makes it easier to say "yes" safely.

## References (Context)

- "Not all AI-assisted programming is vibe coding" (definition + cautions): https://simonwillison.net/2025/Mar/19/vibe-coding/
- Koren et al. "Vibe Coding Kills Open Source" (discussion paper): https://grp.cepr.org/publications/discussion-paper/vibe-coding-kills-open-source
- WIRED (op-ed framing of the risk): https://www.wired.com/story/vibe-coding-is-the-new-open-source/
- Hackaday (practical maintainer concerns): https://hackaday.com/2026/02/02/how-vibe-coding-is-killing-open-source/
- cURL ending bug bounties due to AI slop (triage load): https://lwn.net/Articles/1055996/
