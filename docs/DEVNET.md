# Local Single-Node Devnet

This page shows how to start the RustChain node locally for development and
connect examples to it. The local node uses SQLite and listens on port `8099`.

## 1. Prepare the Python environment

From the repository root, follow the Python setup in [`BUILD.md`](BUILD.md):

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-node.txt
```

On Windows PowerShell, activate the environment with:

```powershell
.\.venv\Scripts\Activate.ps1
```

## 2. Start the node

Use a throwaway SQLite database so local experiments do not reuse production or
shared state.

Linux and macOS:

```bash
export RUSTCHAIN_DB_PATH=.dev/rustchain-devnet.db
mkdir -p .dev
python node/wsgi.py
```

Windows PowerShell:

```powershell
$env:RUSTCHAIN_DB_PATH = ".dev\rustchain-devnet.db"
New-Item -ItemType Directory -Force .dev
python node\wsgi.py
```

The development server listens at:

```text
http://127.0.0.1:8099
```

## 3. Smoke test the local node

In a second terminal:

```bash
curl http://127.0.0.1:8099/health
curl http://127.0.0.1:8099/epoch
curl http://127.0.0.1:8099/api/miners
```

If the node cannot start because port `8099` is already in use, stop the other
process first. The current WSGI entry point hard-codes port `8099` for direct
development runs.

## 4. Connect a miner in dry-run mode

After building the Rust miner, point it at the local node:

```bash
cargo run --manifest-path rustchain-miner/Cargo.toml -- \
  --node http://127.0.0.1:8099 \
  --wallet dev-miner \
  --miner-id dev-miner \
  --dry-run
```

Remove `--dry-run` only when you intentionally want the miner to submit to the
local node.

## 5. Connect the native wallet

The native wallet accepts an RPC override on commands that talk to the network:

```bash
cargo run --manifest-path rustchain-wallet/Cargo.toml -- \
  --network devnet \
  --wallet-dir .dev/wallets \
  network \
  --rpc http://127.0.0.1:8099
```

See [`CLI.md`](CLI.md) for wallet creation, balance, and transaction examples.

## 6. Reset local state

Stop the node, then delete the throwaway database:

```bash
rm -f .dev/rustchain-devnet.db
```

Windows PowerShell:

```powershell
Remove-Item .dev\rustchain-devnet.db -ErrorAction SilentlyContinue
```

Do not run destructive cleanup commands against any database path you did not
create for local development.
