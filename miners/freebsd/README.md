# RustChain Miner — FreeBSD Port

## Verify Before Trust

Before installing or mining, verify what this software does:

```bash
# Preview installer actions without installing
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner-freebsd.sh | bash -s -- --dry-run

# Show hardware payload that would be attested (locally, no network)
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner-freebsd.sh | bash -s -- test-wallet --test-only
```

## Quick Start

```bash
# Install and start mining
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner-freebsd.sh | bash -s -- your-wallet-name
```

## Platform Support

**Tested on:**
- FreeBSD 14.x (amd64)
- FreeBSD 13.x (amd64)

**Detected device family:** `x86-64 (Modern)` — Multiplier 0.8x

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `RUSTCHAIN_NODE` | `https://rustchain.org` | Attestation node URL |
| `WALLET_NAME` | (required) | Your RTC wallet name |

## Service Management

```bash
# Enable and start
sysrc rustchain_miner_enable="YES"
service rustchain_miner start

# Check status
service rustchain_miner status

# View logs
tail -f /var/log/rustchain/miner.log

# Stop
service rustchain_miner stop
```

## Build from Source

```bash
# Install dependencies
pkg install python3 py311-pip
pip3 install requests

# Run miner directly
python3 rustchain_miner.py --node https://rustchain.org --wallet your-wallet-name
```

## Attestation Evidence

This miner attests honestly — no hardware fingerprint fabrication. The detected hardware family is determined by the FreeBSD `sysctl` interface:

```
sysctl hw.model        → CPU model
sysctl hw.machine      → Architecture
sysctl hw.ncpu         → Core count
```

## Security

- Miner runs as dedicated `rustchain` user (no root)
- No hardware spoofing or fingerprint fabrication
- All attestations signed with Ed25519
- TLS certificate pinning enabled

## Uninstall

```bash
service rustchain_miner stop
sysrc -x rustchain_miner_enable
rm -rf /opt/rustchain
rm -f /usr/local/etc/rc.d/rustchain_miner
pw userdel rustchain
pw groupdel rustchain
```
