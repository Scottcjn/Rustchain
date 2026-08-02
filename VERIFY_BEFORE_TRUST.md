# Verify Before Trust — RustChain Windows Miner Port (#12788)

The Windows portable build (`install-miner-windows.ps1`) follows a strict
**verify-before-trust** contract. A miner runs on your hardware and earns RTC,
so it must never execute a downloaded artifact blindly.

## The contract

1. **Download, do not pipe-to-shell.** The script writes the artifact to
   `$HOME/.rustchain/miner.py` first; it never does `curl | powershell`.
2. **Hash it.** Computes `SHA256` of the artifact locally.
3. **Compare to upstream.** Fetches `miners/checksums.sha256` from the pinned
   `RUSTCHAIN_REF` (default `main`) and checks the hash is listed.
   - ✅ Match → safe to run.
   - ⚠️ No match / unreachable → warns and refuses to auto-trust.
4. **Dry-run by default for inspection.** `install-miner-windows.ps1 -DryRun`
   downloads + hashes + prints versions but executes nothing.
5. **Signatures (recommended).** If upstream publishes a GPG/cosign signature
   next to the artifact, verify it before running:
   ```powershell
   # example with cosign (adjust to upstream's published key)
   cosign verify-blob --key rustchain.pub --signature miner.py.sig miner.py
   ```
6. **Least privilege.** Runs under the current user, not SYSTEM. CPU
   overhead <0.1%, GPU impact 0%, RAM <50MB (per upstream docs).

## Manual verification checklist (do this before trusting any build)

- [ ] I downloaded the script from the official `Scottcjn/Rustchain` repo, not a fork mirror.
- [ ] I read `install-miner-windows.ps1` and understand every step.
- [ ] I ran `-DryRun` and confirmed no unexpected network calls.
- [ ] I verified the artifact's SHA256 against upstream `checksums.sha256`.
- [ ] If a signature is published, I verified it with the official key.
- [ ] I understand the miner uses my hardware fingerprint for Proof of Antiquity.

## Why this matters

RustChain's value comes from trust in the hardware identity layer. A portable
build that executes unverified binaries would defeat that. This port makes
Windows first-class while keeping the trust boundary explicit and auditable.
