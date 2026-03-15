# Homebrew Tap for RustChain Miner

## Install

```bash
brew tap Scottcjn/rustchain https://github.com/Scottcjn/Rustchain.git
brew install clawrtc
```

Or use the one-liner:

```bash
curl -fsSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/Formula/install.sh | bash
```

## Usage

```bash
# Show help
clawrtc --help

# Start mining
clawrtc mine --wallet YOUR_WALLET_ADDRESS
```

## Upgrade

```bash
brew upgrade clawrtc
```

## Uninstall

```bash
brew uninstall clawrtc
brew untap Scottcjn/rustchain
```

## What gets installed

- `clawrtc` CLI binary (via Python virtualenv)
- Dependencies: `requests`, `cryptography`
- Python 3.12 (if not already installed)

## Requirements

- macOS or Linux
- Homebrew package manager

## Links

- [RustChain](https://rustchain.org)
- [GitHub](https://github.com/Scottcjn/Rustchain)
- [clawrtc on PyPI](https://pypi.org/project/clawrtc/)
