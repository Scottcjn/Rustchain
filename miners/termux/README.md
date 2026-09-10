# RustChain Miner — Android / Termux (aarch64)

## Verify before trust

Do not start a persistent miner first. The three commands below have deliberately different safety levels.

```bash
# 1) Preview the installer. No package/file/service changes, no attestation.
curl -fsSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners/termux/install.sh \
  | bash -s -- --dry-run

# 2) After installing, print the exact local hardware/fingerprint fields that
# would be included in an attestation. This mode performs NO network requests.
rustchain-termux --wallet YOUR_WALLET --show-payload

# 3) Attest exactly once to an explicit NON-PRODUCTION test node and exit.
# It never enrolls or mines, and it refuses https://rustchain.org.
rustchain-termux --wallet termux-test --test-only \
  --node-url http://127.0.0.1:58333
```

`--dry-run` on the miner itself is also safe for production connectivity: it runs the hardware fingerprint and a read-only `GET /health`, but does not attest, enroll, or mine.

```bash
rustchain-termux --wallet YOUR_WALLET --dry-run
```

## Tested platform

This port was exercised on physical Android hardware from Termux, not in an emulator:

- Android 16 / Linux kernel 6.1
- Termux 0.118.3
- `platform.system()`: `Android`
- `platform.machine()`: `aarch64`
- CPU reported by the existing RustChain probe: `Cortex-A520`
- 8 logical cores
- Python 3.14.6
- libsodium 1.0.22
- PyNaCl 1.6.2 built successfully against Termux's system libsodium

The client reports `family=ARM`, `arch=aarch64`; the current node independently stores the same `ARM/aarch64` classification. This port does **not** hardcode a device class or multiplier. Modern ARM receives whatever policy the node derives for that hardware.

Fingerprint timings naturally vary. In repeated physical-device runs the cache-timing check was observed both passing and failing. The port reports the measured result as-is; it never forces `all_passed` or edits fingerprint data.

## Install

The installer is user-space only: no root and no `sudo`. It installs Termux packages needed to build PyNaCl against system libsodium, downloads the existing canonical Linux miner implementation plus its fingerprint/crypto helpers, verifies those three files against `miners/checksums.sha256`, and adds a thin Termux launcher.

```bash
curl -fsSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners/termux/install.sh \
  | bash -s -- --wallet YOUR_WALLET
```

The installer intentionally creates the persistence service **disabled**. It does not begin mining just because installation completed.

### Build/install recipe from a source checkout

```bash
pkg install python python-pip libsodium clang make pkg-config termux-services curl
SODIUM_INSTALL=system python -m pip install 'requests>=2.28' 'PyNaCl>=1.6.2'

python miners/termux/rustchain_termux_miner.py \
  --wallet YOUR_WALLET --dry-run
```

Python 3.14 currently builds PyNaCl from source on Termux. `SODIUM_INSTALL=system` reuses Termux's maintained `libsodium` instead of building a second bundled copy.

## Reproduce the localhost attestation test

`miners/termux/test_node.py` is a local harness around the repository's **real current Flask node and real `/attest/challenge` + `/attest/submit` handlers**. It binds only to `127.0.0.1`, uses a disposable SQLite database, generates a throwaway admin key in-process, and disables P2P auto-start.

From a full RustChain checkout, terminal 1:

```bash
python miners/termux/test_node.py --port 58333
```

Terminal 2:

```bash
python miners/termux/rustchain_termux_miner.py \
  --wallet termux-testonly-12788 \
  --test-only --node-url http://127.0.0.1:58333
```

Physical-device verification on 2026-09-10 returned:

```text
[PASS] Attestation accepted!
CPU: Cortex-A520
Arch: aarch64/aarch64
Fingerprint: PASSED
[TEST-ONLY] detected=ARM/aarch64 machine=aarch64 cpu=Cortex-A520
[TEST-ONLY] attestation_accepted=True
```

The isolated node database independently recorded:

```text
miner=termux-testonly-12788
source_ip=127.0.0.1
device_family=ARM
device_arch=aarch64
fingerprint_passed=1
```

This is test-node state only; the evidence run did not submit an attestation, enrollment, or mining request to the production RustChain node.

## Persistent service (runit / termux-services)

Android does not run systemd inside Termux. The platform equivalent supplied by this port is a runit service under:

```text
$PREFIX/var/service/rustchain-miner/run
```

After reviewing `--show-payload` and, preferably, testing an attestation against a test node:

```bash
SVDIR="$PREFIX/var/service" sv-enable rustchain-miner
SVDIR="$PREFIX/var/service" sv status rustchain-miner
```

Stop/disable:

```bash
SVDIR="$PREFIX/var/service" sv-disable rustchain-miner
```

Logs are written by `svlogd` under:

```text
~/.local/state/rustchain-termux/log/
```

The service takes a Termux wake lock before launching the miner so Android is less likely to suspend a deliberately enabled persistent session. Battery-optimization policy is still controlled by Android and the user.

## Normal foreground mining

Only after verification:

```bash
rustchain-termux --wallet YOUR_WALLET --node-url https://rustchain.org
```

Normal mode persists the miner Ed25519 key using the existing miner code. Verification modes use an ephemeral key and do not persist it.

## Troubleshooting

If `PyNaCl` reports a build failure, verify that `libsodium`, `clang`, `make`, and `pkg-config` are installed and retry with `SODIUM_INSTALL=system`. If `rustchain-termux` reports that it is not running in Termux, check `$PREFIX` and `TERMUX_VERSION`; this launcher intentionally refuses generic desktop Linux because this package is specifically the Android port. If `--test-only` rejects the node URL, supply a local/test node: production `rustchain.org` is intentionally blocked for that mode.
