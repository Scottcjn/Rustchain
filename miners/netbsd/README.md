# RustChain Miner — NetBSD Port

## Verify Before Trust

Before installing or mining, verify what this software does:

```sh
# Preview installer actions without installing
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner-netbsd.sh | sh -s -- --dry-run

# Show the hardware payload that would be attested (locally, no network)
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner-netbsd.sh | sh -s -- --test-only
```

After installing, the miner client keeps the same contract:

```sh
cd /opt/rustchain
/usr/pkg/bin/python3.11 rustchain_netbsd_miner.py --dry-run        # preflight, read-only health probe
/usr/pkg/bin/python3.11 rustchain_netbsd_miner.py --test-only      # local sysctl detection, no network, no attestation
/usr/pkg/bin/python3.11 rustchain_netbsd_miner.py --dry-run --show-payload   # also print node responses
```

`--dry-run` performs no mining and changes no state (it only issues a
read-only `GET /health` against the node). `--test-only` touches no network
at all.

## What This Port Is

`miners/netbsd/rustchain_netbsd_miner.py` reuses the Linux miner's
enrollment, Ed25519 attestation signing, and mining core, and replaces only
the hardware probes with NetBSD-native lookups so every attested value is
**measured, not guessed**:

| Probe | NetBSD source |
|---|---|
| OS | `sysctl -n kern.ostype` (must be `NetBSD`) |
| CPU model | `sysctl -n machdep.cpu_model` (fallback `machdep.cpu_brand_string`) |
| Architecture | `sysctl -n hw.machine_arch`, falling back to `hw.machine` only when unavailable |
| Cores | `sysctl -n hw.ncpuonline` (fallback `hw.ncpu`) |
| Memory | `sysctl -n hw.physmem64` (fallback `hw.physmem`, then `sysconf`) |
| MAC addresses | `ifconfig <iface>` (`address:` lines) |

Unmeasurable values are reported as unknown instead of defaulted — a
fabricated default (for example a made-up memory size) is fingerprint
fabrication and grounds for bounty rejection.

The client **refuses to run on non-NetBSD systems**. Hardware numbers
measured on another OS must not be attested as a NetBSD device.

## Quick Start

```sh
# Install and start mining
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner-netbsd.sh | sh -s -- your-wallet-name
```

## Platform Support

**Targeted:** NetBSD 9.x / 10.x on `amd64`; the sysctl probes used are
present on all NetBSD ports (`evbarm`, `sparc64`, `macppc`, ...).

**Detected device family:** derived from the measured NetBSD machine
architecture (for example, `amd64` reports `family=x86`, `arch=amd64`). The
port does not infer a machine age or multiplier from its architecture. An
unrecognized architecture is reported as `unknown`; unavailable core, memory,
and MAC readings remain unknown or empty rather than receiving placeholders.

## Configuration

| Environment variable | Default | Description |
|---|---|---|
| `RUSTCHAIN_NODE` | `https://rustchain.org` | Attestation node URL |
| `WALLET_NAME` | (required, installer argument) | Your RTC wallet name |

## Service Management

The installer installs a standard NetBSD rc.d unit at
`/etc/rc.d/rustchain_miner` (using `/etc/rc.subr` and `daemon(8)`), enabled
via `rustchain_miner=YES` in `/etc/rc.conf`:

```sh
service rustchain_miner start    # Start miner
service rustchain_miner stop     # Stop miner
service rustchain_miner status   # Check status
tail -f /var/log/rustchain/miner.log   # View logs
```

## Build from Source (pkgsrc)

```sh
pkgin -y install python311 py311-requests py311-pynacl
cd /path/to/Rustchain
/usr/pkg/bin/python3.11 -m py_compile miners/netbsd/rustchain_netbsd_miner.py
/usr/pkg/bin/python3.11 miners/netbsd/rustchain_netbsd_miner.py --test-only
/usr/pkg/bin/python3.11 miners/netbsd/rustchain_netbsd_miner.py --wallet your-wallet-name
```

From a repository checkout, the client finds the Linux miner core at
`../linux/rustchain_linux_miner.py` automatically; in the installer layout
everything is placed together in `/opt/rustchain/`.

## Attestation Evidence

This miner attests honestly — no hardware fingerprint fabrication. All
attestations are signed with Ed25519 (via `miner_crypto.py` / PyNaCl) and
every attested hardware field comes from the NetBSD `sysctl` interface
listed above. Run `--test-only` on the target machine to capture the exact
hardware payload before attesting, and check the node's balance endpoint to
confirm acceptance.

## Security

- Miner runs as the dedicated `rustchain` user (no root mining)
- No hardware spoofing or fingerprint fabrication; non-NetBSD hosts are refused
- All attestations signed with Ed25519
- Installer downloads are SHA-256 verified against `miners/checksums.sha256`

## Uninstall

```sh
service rustchain_miner stop
grep -v '^rustchain_miner=' /etc/rc.conf > /etc/rc.conf.new && mv /etc/rc.conf.new /etc/rc.conf
rm -f /etc/rc.d/rustchain_miner
rm -rf /opt/rustchain /var/log/rustchain
userdel rustchain
groupdel rustchain
```
