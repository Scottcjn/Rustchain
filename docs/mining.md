# RustChain Mining

This lowercase guide exists for the `docs/mining.md` link used from the main
README. For the full reference, see [MINING_GUIDE.md](MINING_GUIDE.md).

## Quick Start

Install the miner with the repository installer:

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

Preview the installer without installing or mining:

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --dry-run
```

Use a specific miner wallet name:

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet YOUR_WALLET_NAME
```

The installer is the recommended setup path. The miner is not published as a
`rustchain-miner` PyPI package.

## Check Your Miner

After the miner has attested and an epoch has settled, check the balance for the
same wallet name used during setup:

```bash
curl -fsS "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

Inspect recent wallet activity:

```bash
curl -fsS "https://rustchain.org/wallet/history?miner_id=YOUR_WALLET_NAME&limit=20"
```

Check the public node health:

```bash
curl -fsS https://rustchain.org/health
```

## Platform Notes

- Linux users can also run the miner directly from [miners/linux/](../miners/linux/).
- macOS users can run the macOS miner from [miners/macos/](../miners/macos/).
- Windows users should start with [miners/windows/README.md](../miners/windows/README.md).
- PowerPC, i386, Apple II, floppy, and console bridge miners have their own
  platform-specific README files under [miners/](../miners/).

For hands-on setup by platform, see
[docs/sprint/miner-setup-guide.md](sprint/miner-setup-guide.md). For the
complete mining overview, hardware multipliers, and troubleshooting, see
[MINING_GUIDE.md](MINING_GUIDE.md).
