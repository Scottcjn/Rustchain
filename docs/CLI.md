# RustChain CLI Wallet Walkthrough

This walkthrough uses the native Rust wallet in `rustchain-wallet/`. It shows
wallet creation, local devnet connectivity, and a simulated transaction.

## Build the wallet

```bash
cargo build --manifest-path rustchain-wallet/Cargo.toml --bin rtc-wallet
```

You can also run commands through Cargo while developing:

```bash
cargo run --manifest-path rustchain-wallet/Cargo.toml -- --help
```

## Create a development wallet

Use a local wallet directory so test wallets stay out of your default wallet
storage.

```bash
cargo run --manifest-path rustchain-wallet/Cargo.toml -- \
  --network devnet \
  --wallet-dir .dev/wallets \
  create --name alice
```

The command prompts for a password and stores the encrypted key in the wallet
directory. Save the printed RTC address if you want to use it in examples.

## Show the receive address

```bash
cargo run --manifest-path rustchain-wallet/Cargo.toml -- \
  --network devnet \
  --wallet-dir .dev/wallets \
  receive --name alice
```

## Check balance on a local node

Start the local node from [`DEVNET.md`](DEVNET.md), then run:

```bash
cargo run --manifest-path rustchain-wallet/Cargo.toml -- \
  --network devnet \
  --wallet-dir .dev/wallets \
  balance --wallet alice \
  --rpc http://127.0.0.1:8099
```

You can also check a raw RTC address:

```bash
cargo run --manifest-path rustchain-wallet/Cargo.toml -- \
  --network devnet \
  --wallet-dir .dev/wallets \
  balance --wallet RTC_EXAMPLE_ADDRESS \
  --rpc http://127.0.0.1:8099
```

## Simulate a transaction

Use `--simulate` first. It signs and prints the transaction without broadcasting
it to the node.

```bash
cargo run --manifest-path rustchain-wallet/Cargo.toml -- \
  --network devnet \
  --wallet-dir .dev/wallets \
  send \
  --from alice \
  --to RTC_RECIPIENT_ADDRESS \
  --amount 1000 \
  --fee 1000 \
  --memo "local devnet test" \
  --rpc http://127.0.0.1:8099 \
  --simulate
```

Remove `--simulate` only after the local node is running, the recipient address
is correct, and you intentionally want to submit the transfer.

## Useful wallet commands

```bash
# List local wallets
cargo run --manifest-path rustchain-wallet/Cargo.toml -- \
  --wallet-dir .dev/wallets list

# Show public wallet details
cargo run --manifest-path rustchain-wallet/Cargo.toml -- \
  --wallet-dir .dev/wallets show --name alice

# Query local network information
cargo run --manifest-path rustchain-wallet/Cargo.toml -- \
  --network devnet network --rpc http://127.0.0.1:8099
```

Never commit files from `.dev/wallets`, exported private keys, seed phrases, or
terminal logs containing secrets.
