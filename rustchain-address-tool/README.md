# RustChain Address Tool

A Rust implementation of RustChain address generation and validation.

## Features

- Generate new RustChain addresses from random entropy
- Import from BIP39 mnemonic phrases
- Import from private key hex
- Validate address format
- Derive address from public key

## Installation

```bash
# Build from source
cargo build --release

# Or install globally
cargo install --path .
```

## Usage

### Generate New Address

```bash
rtc-address generate
```

Output:
```
Generated RustChain Address
===========================
Address:     RTCa1b2c3d4e5f6...
Private Key: [64 character hex]
Public Key:  [64 character hex]
```

### Import from Mnemonic

```bash
rtc-address import-mnemonic "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
```

### Import from Private Key

```bash
rtc-address import-key 0000000000000000000000000000000000000000000000000000000000000000
```

### Validate Address

```bash
rtc-validate address RTCa1b2c3d4e5f6...
```

### Get Address from Public Key

```bash
rtc-validate pubkey a1b2c3d4e5f6...
```

## Library Usage

```rust
use rustchain_address::{generate_address, validate_address, address_from_pubkey_hex};

// Generate new address
let (address, keypair) = generate_address();

// Validate address
let is_valid = validate_address("RTC0000000000000000000000000000000000000000");

// Get address from public key hex
let address = address_from_pubkey_hex("a1b2c3d4e5f6...").unwrap();
```

## Address Format

RustChain addresses start with `RTC` followed by 40 hexadecimal characters (total 43 characters). The address is derived from the SHA256 hash of the Ed25519 public key.

## Bounty

This tool is submitted for [Bounty #674](https://github.com/Scottcjn/rustchain-bounties/issues/674): Build RustChain Tools & Features in Rust (Tier 1: Address Generator + Validator).

## License

MIT
