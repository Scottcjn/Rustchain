# Fingerprint Preflight (Contributor Test Harness)

This is a standalone runner for the RustChain hardware fingerprint checks, intended for:
- contributors porting the miner to new platforms (ARM64, SPARC, PPC, 68K)
- operators validating that a machine will likely pass attestation before deploying

## Run

From `node/`:

```bash
python3 test_fingerprints.py
```

Write a JSON report (attach to bug reports / PRs):

```bash
python3 test_fingerprints.py --json-out fingerprint_report.json
```

If you plan to share the report publicly, you can redact host identifiers:

```bash
python3 test_fingerprints.py --json-out fingerprint_report.json --redact
```

Skip ROM check (most modern systems do not need it):

```bash
python3 test_fingerprints.py --no-rom
```

## Reference Profile Compare (optional)

List built-in reference profiles:

```bash
python3 test_fingerprints.py --list-profiles
```

Compare your results to a profile (basic sanity checks):

```bash
python3 test_fingerprints.py --compare modern_x86
```

Profiles live in `node/fingerprint_reference_profiles/` and currently encode lightweight expectations
(SIMD traits + minimum clock drift CV). They are meant to catch obvious mis-detection, not to be a strict
"hardware authenticity" oracle.

## Security Notes

- `--json-out` writes to the provided path. Treat CLI args as trusted (do not run untrusted commands as admin/root).
- The runner imports `fingerprint_checks.py` from the local `node/` directory to avoid module shadowing via `PYTHONPATH`.

## What Each Check Is Doing (high level)

- Clock drift: tries to detect synthetic / perfectly stable timing sources.
- Cache timing: checks that L1/L2/L3 access times are meaningfully different (real cache hierarchy).
- SIMD identity: confirms the CPU exposes expected SIMD features for the architecture.
- Thermal drift: expects timing variance between cold and warm runs.
- Instruction jitter: expects non-zero timing variance across integer/float/branch loops.
- Anti-emulation: scans for common VM/container indicators (should be empty on bare metal).

## Exit Codes

- `0`: all checks passed
- `2`: at least one check failed

