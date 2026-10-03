# rustchain-address

A small, dependency-free Rust crate for parsing, validating, and normalizing RustChain RTC wallet addresses.

## Why

Applications should not pass unchecked wallet strings between API, CLI, and storage layers. `RtcAddress` validates the `RTC` prefix, exact payload length, and hexadecimal encoding once, then stores the address as a compact 20-byte value.

## Usage

```rust
use rustchain_address::RtcAddress;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let address: RtcAddress =
        "RTC2fe3c33c77666ff76a1cd0999fd4466ee81250ff".parse()?;

    println!("canonical: {address}");
    println!("payload: {}", address.payload());
    println!("bytes: {:?}", address.as_bytes());
    Ok(())
}
```

Validation without keeping the parsed value:

```rust
use rustchain_address::RtcAddress;

assert!(RtcAddress::is_valid(
    "RTC2fe3c33c77666ff76a1cd0999fd4466ee81250ff"
));
assert!(!RtcAddress::is_valid("RTCbad"));
```

Uppercase hexadecimal payloads are accepted and normalized to lowercase when displayed. The `RTC` prefix itself is intentionally strict and case-sensitive.

## Design

- No runtime dependencies.
- Stable Rust.
- 20-byte internal representation.
- Strict `RTC` prefix and 40 hexadecimal character payload.
- `FromStr`, `Display`, byte conversion, validation helper, and typed errors.
- Unit tests and rustdoc examples.
- MIT licensed.

## Verification

```text
cargo fmt -- --check
cargo test
cargo clippy --all-targets --all-features -- -D warnings
cargo doc --no-deps
cargo package
```

## License

MIT
