# RustChain Mining Troubleshooting

This guide covers the first checks to run when a miner installs but does not
connect, attest, or receive RTC rewards.

## Quick diagnostics

Run these commands before changing configuration:

```bash
# Confirm the public node is reachable.
curl -sk https://rustchain.org/health

# Confirm the epoch endpoint responds.
curl -sk https://rustchain.org/epoch

# Check your wallet balance with the exact wallet name from install.
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET_NAME"

# Check whether active miners are visible.
curl -sk https://rustchain.org/api/miners
```

The RustChain public node currently uses a self-signed certificate, so examples
use `curl -sk`. The miner handles this internally.

## `Wallet not found`

This usually means the balance check or miner command is using a wallet name
that does not match the one created during installation.

1. Check the wallet name printed by the installer or passed with `--wallet`.
2. Use the exact same spelling and capitalization in balance checks.
3. If you installed the miner manually, check the local miner configuration.
4. If the miner just started, wait at least one epoch before assuming the wallet
   has received rewards.

Example balance check:

```bash
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_EXACT_WALLET_NAME"
```

If you need a new wallet name, reinstall with an explicit value:

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet my-miner-wallet
```

For wallet concepts and backup guidance, see
[`docs/WALLET_SETUP.md`](docs/WALLET_SETUP.md).

## `Connection refused` or bootstrap connection errors

Connection failures usually come from network reachability, a custom node URL,
or a local firewall/proxy blocking outbound traffic.

1. Confirm the public node responds:

   ```bash
   curl -sk https://rustchain.org/health
   ```

2. Confirm your internet connection works outside RustChain.
3. If you use a VPN, proxy, or corporate firewall, allow outbound HTTPS to
   `https://rustchain.org`.
4. If you configured a custom node URL, verify the scheme, host, and port.
5. Check miner logs for the exact node URL being used:

   ```bash
   # Linux systemd install
   journalctl --user -u rustchain-miner -n 50

   # macOS launchd install
   tail -n 50 ~/.rustchain/miner.log
   ```

RustChain miners initiate outbound connections. You normally do not need inbound
port forwarding for the basic miner flow.

## `Insufficient balance`

Mining does not require a prepaid account, but wallet transfers, bridge actions,
or other balance-consuming operations can fail until the wallet has RTC.

1. Confirm you are checking the exact wallet name used by the miner:

   ```bash
   curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_EXACT_WALLET_NAME"
   ```

2. Wait for reward settlement. Current quickstart docs describe epochs as about
   10 minutes, and new miners should wait 2-3 epochs before treating missing
   rewards as a failure.
3. Confirm the miner appears in the active miner list:

   ```bash
   curl -sk https://rustchain.org/api/miners
   ```

4. Check that hardware attestation passes in the miner log. Virtual machines and
   containers may receive little or no reward.

## `Architecture not supported`

Architecture errors usually happen when the downloaded miner does not match the
machine architecture or when Apple Silicon is treated as Intel x86_64.

Check the architecture reported by the operating system:

```bash
uname -m
```

Common values:

| Platform | Expected architecture |
| --- | --- |
| Intel/AMD Linux or Intel Mac | `x86_64` |
| Apple Silicon Mac | `arm64` |
| ARM Linux or Raspberry Pi | `aarch64` or `armv7l` |
| POWER8 Linux | `ppc64le` |
| PowerPC Mac | `powerpc` or `ppc` |

Recommended fixes:

1. Re-run the current installer so it auto-detects the platform:

   ```bash
   curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet YOUR_WALLET_NAME
   ```

2. On Apple Silicon, run the native ARM64 path unless you intentionally use an
   Intel shell under Rosetta. Mixing Rosetta/x86_64 Python with ARM64 downloads
   can produce architecture mismatches.
3. If the machine is a vintage or unusual architecture, compare it with the
   supported platforms in [`INSTALL.md`](INSTALL.md) and
   [`docs/MINING_GUIDE.md`](docs/MINING_GUIDE.md).

## Miner starts but no rewards appear

Use this checklist after the miner has been running for at least 20-30 minutes:

- The wallet name in the command matches the wallet you are checking.
- `curl -sk https://rustchain.org/health` returns a healthy response.
- The miner appears in `curl -sk https://rustchain.org/api/miners`.
- The system clock is reasonably accurate.
- The miner is running on real hardware if you expect normal rewards.
- Logs do not show repeated attestation or network errors.

## Related docs

- [`INSTALL.md`](INSTALL.md) - installation, auto-start, and service commands
- [`docs/QUICKSTART.md`](docs/QUICKSTART.md) - beginner mining walkthrough
- [`docs/MINING_GUIDE.md`](docs/MINING_GUIDE.md) - mining and rewards overview
- [`docs/WALLET_SETUP.md`](docs/WALLET_SETUP.md) - wallet setup and safety
- [`docs/FAQ_TROUBLESHOOTING.md`](docs/FAQ_TROUBLESHOOTING.md) - broader FAQ
