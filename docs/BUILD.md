# RustChain Build Guide

Use this guide when you want a local development checkout for the Python node
and the Rust command-line components.

## System prerequisites

| Tool | Minimum | Used for |
| --- | --- | --- |
| Python | 3.11+ recommended | Node, tests, wallet GUI, scripts |
| pip | Bundled with Python | Python dependency installation |
| Rust | 1.70+ | Rust miner and native wallet crates |
| Cargo | Bundled with Rust | Rust builds and checks |
| curl | Any recent version | API smoke tests |
| Git | Any recent version | Checkout and contribution workflow |

Protocol Buffers are not required for the checked-in Python node, Rust miner, or
Rust wallet paths documented here. Install `protoc` only if a specific future
subproject or integration README asks for it.

## Clone the repository

```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain
```

## Python development setup

Linux and macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-node.txt
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-node.txt
```

Verify the key entry points parse correctly:

```bash
python -m py_compile node/wsgi.py node/rustchain_v2_integrated_v2.2.1_rip200.py wallet/__main__.py
```

## Rust component builds

RustChain has multiple Rust subprojects, not one top-level Cargo workspace. Build
or check the component you are changing with `--manifest-path`.

Check the miner:

```bash
cargo check --manifest-path rustchain-miner/Cargo.toml
```

Build the miner:

```bash
cargo build --release --manifest-path rustchain-miner/Cargo.toml
```

Check the native wallet:

```bash
cargo check --manifest-path rustchain-wallet/Cargo.toml
```

Build the native wallet:

```bash
cargo build --release --manifest-path rustchain-wallet/Cargo.toml --bin rtc-wallet
```

## Fast validation before opening a PR

For docs-only changes:

```bash
git diff --check
```

For Python node or wallet changes:

```bash
python -m py_compile node/wsgi.py node/rustchain_v2_integrated_v2.2.1_rip200.py wallet/__main__.py
```

For Rust miner or wallet changes:

```bash
cargo check --manifest-path rustchain-miner/Cargo.toml
cargo check --manifest-path rustchain-wallet/Cargo.toml
```

Run narrower tests for the files you touched when possible. The repository is
large, so prefer focused validation plus any maintainer-requested CI checks.
