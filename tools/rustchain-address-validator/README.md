# RustChain Address Validator & Generator

A Rust CLI tool for generating and validating RTC addresses on the RustChain network.

## Features

- Generate new RTC addresses with private keys
- Validate existing RTC addresses
- Derive address from private key

## Installation

```bash
cargo install --path .
```

Or build and run directly:

```bash
cargo build --release
./target/release/rtc-address --help
```

## Usage

### Generate a new address

```bash
rtc-address generate
```

Output:
```
=== Generated RTC Address ===

Address:     RTCxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Private Key: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

IMPORTANT: Save your private securely!
    Anyone with your private key can access your funds.
```

### Validate an address

```bash
rtc-address validate RTCxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### Derive address from private key

```bash
rtc-address from-key <private-key-hex>
```

## Development

### Build

```bash
cargo build
```

### Test

```bash
cargo test
```

### Run

```bash
cargo run -- generate
```

## Bounty

This tool is submitted for [Bounty #674: Build RustChain Tools & Features in Rust](https://github.com/Scottcjn/rustchain-bounties/issues/674)

- **Tier**: 1 (Utilities)
- **Target**: RTC address generator + validator

## License

MIT
