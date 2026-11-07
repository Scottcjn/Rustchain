// SPDX-License-Identifier: MIT
//! Dependency-free parsing, validation, and normalization for RustChain RTC addresses.
//!
//! RustChain wallet addresses seen in the ecosystem use an `RTC` prefix followed by
//! a 40-character hexadecimal payload. This crate gives applications one strict type
//! instead of passing unchecked strings around.
//!
//! # Scope
//!
//! This crate validates **RustChain wallet addresses** only: the `RTC` + 40-hexadecimal
//! form derived from a public key (`RTC` + `sha256(pubkey)[:40]`, as produced by the
//! `rustchain-wallet` crate). RustChain also uses other identifier forms that are *not*
//! RTC hexadecimal addresses and are deliberately out of scope here. For example,
//! human-readable miner IDs such as `n64-scott-unit1`, or lenient `RTC`-prefixed
//! strings accepted by some bridge checks. Use this crate to validate payout and wallet
//! addresses; do not assume that every account or miner identifier on the network is an
//! `RTC` hexadecimal address.
//!
//! # Example
//!
//! ```
//! use rustchain_address::RtcAddress;
//!
//! let address: RtcAddress =
//!     "RTC2fe3c33c77666ff76a1cd0999fd4466ee81250ff".parse()?;
//! assert_eq!(address.payload().len(), 40);
//! assert_eq!(address.to_string(), "RTC2fe3c33c77666ff76a1cd0999fd4466ee81250ff");
//! # Ok::<(), rustchain_address::AddressError>(())
//! ```

use core::fmt;
use core::str::FromStr;

/// Number of hexadecimal characters after the `RTC` prefix.
pub const PAYLOAD_LEN: usize = 40;
/// Total canonical address length.
pub const ADDRESS_LEN: usize = 3 + PAYLOAD_LEN;
/// Canonical RustChain address prefix.
pub const PREFIX: &str = "RTC";

/// A validated RustChain RTC address.
///
/// The payload is stored as 20 bytes, so once an `RtcAddress` exists it cannot
/// contain malformed hexadecimal data or an incorrect length.
#[derive(Clone, Copy, Debug, Eq, Hash, Ord, PartialEq, PartialOrd)]
pub struct RtcAddress {
    bytes: [u8; 20],
}

/// Error returned while parsing a RustChain address.
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum AddressError {
    /// Input length was not exactly 43 ASCII characters.
    InvalidLength { expected: usize, actual: usize },
    /// Input did not begin with the exact uppercase `RTC` prefix.
    InvalidPrefix,
    /// A non-hexadecimal character occurred in the payload.
    InvalidHex { index: usize, byte: u8 },
}

impl RtcAddress {
    /// Constructs an address from its raw 20-byte payload.
    pub const fn from_bytes(bytes: [u8; 20]) -> Self {
        Self { bytes }
    }

    /// Returns the raw 20-byte payload.
    pub const fn as_bytes(&self) -> &[u8; 20] {
        &self.bytes
    }

    /// Consumes the value and returns the raw payload.
    pub const fn into_bytes(self) -> [u8; 20] {
        self.bytes
    }

    /// Returns the canonical lowercase hexadecimal payload without the prefix.
    pub fn payload(&self) -> String {
        let mut out = String::with_capacity(PAYLOAD_LEN);
        for byte in self.bytes {
            push_hex(&mut out, byte >> 4);
            push_hex(&mut out, byte & 0x0f);
        }
        out
    }

    /// Parses an address using the same strict rules as `FromStr`.
    pub fn parse(input: &str) -> Result<Self, AddressError> {
        input.parse()
    }

    /// Returns true when the supplied string is a valid canonical RTC address.
    pub fn is_valid(input: &str) -> bool {
        Self::parse(input).is_ok()
    }
}

impl From<[u8; 20]> for RtcAddress {
    fn from(bytes: [u8; 20]) -> Self {
        Self::from_bytes(bytes)
    }
}

impl From<RtcAddress> for [u8; 20] {
    fn from(address: RtcAddress) -> Self {
        address.into_bytes()
    }
}

impl FromStr for RtcAddress {
    type Err = AddressError;

    fn from_str(input: &str) -> Result<Self, Self::Err> {
        if input.len() != ADDRESS_LEN {
            return Err(AddressError::InvalidLength {
                expected: ADDRESS_LEN,
                actual: input.len(),
            });
        }

        if !input.starts_with(PREFIX) {
            return Err(AddressError::InvalidPrefix);
        }

        let payload = &input.as_bytes()[PREFIX.len()..];
        let mut bytes = [0u8; 20];

        for (output_index, pair) in payload.chunks_exact(2).enumerate() {
            let source_index = PREFIX.len() + output_index * 2;
            let high = decode_hex(pair[0]).ok_or(AddressError::InvalidHex {
                index: source_index,
                byte: pair[0],
            })?;
            let low = decode_hex(pair[1]).ok_or(AddressError::InvalidHex {
                index: source_index + 1,
                byte: pair[1],
            })?;
            bytes[output_index] = (high << 4) | low;
        }

        Ok(Self { bytes })
    }
}

impl fmt::Display for RtcAddress {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(PREFIX)?;
        for byte in self.bytes {
            write!(formatter, "{byte:02x}")?;
        }
        Ok(())
    }
}

impl fmt::Display for AddressError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidLength { expected, actual } => {
                write!(
                    formatter,
                    "invalid RTC address length: expected {expected}, got {actual}"
                )
            }
            Self::InvalidPrefix => formatter.write_str("invalid RTC address prefix: expected RTC"),
            Self::InvalidHex { index, byte } => {
                write!(
                    formatter,
                    "invalid hexadecimal byte 0x{byte:02x} at index {index}"
                )
            }
        }
    }
}

impl std::error::Error for AddressError {}

const fn decode_hex(byte: u8) -> Option<u8> {
    match byte {
        b'0'..=b'9' => Some(byte - b'0'),
        b'a'..=b'f' => Some(byte - b'a' + 10),
        b'A'..=b'F' => Some(byte - b'A' + 10),
        _ => None,
    }
}

fn push_hex(output: &mut String, nibble: u8) {
    let byte = if nibble < 10 {
        b'0' + nibble
    } else {
        b'a' + (nibble - 10)
    };
    output.push(char::from(byte));
}

#[cfg(test)]
mod tests {
    use super::*;

    const ADDRESS: &str = "RTC2fe3c33c77666ff76a1cd0999fd4466ee81250ff";

    #[test]
    fn parses_known_ecosystem_address() {
        let address: RtcAddress = ADDRESS.parse().unwrap();
        assert_eq!(address.to_string(), ADDRESS);
        assert_eq!(address.payload(), &ADDRESS[3..]);
    }

    #[test]
    fn accepts_uppercase_hex_and_normalizes_output() {
        let input = "RTC2FE3C33C77666FF76A1CD0999FD4466EE81250FF";
        let address: RtcAddress = input.parse().unwrap();
        assert_eq!(address.to_string(), ADDRESS);
    }

    #[test]
    fn round_trips_raw_bytes() {
        let bytes = [0xab; 20];
        let address = RtcAddress::from_bytes(bytes);
        assert_eq!(address.as_bytes(), &bytes);
        assert_eq!(address.into_bytes(), bytes);
        assert_eq!(address.to_string(), format!("RTC{}", "ab".repeat(20)));
    }

    #[test]
    fn rejects_short_address() {
        assert_eq!(
            RtcAddress::parse("RTC1234"),
            Err(AddressError::InvalidLength {
                expected: ADDRESS_LEN,
                actual: 7
            })
        );
    }

    #[test]
    fn rejects_wrong_prefix() {
        let input = "rtc2fe3c33c77666ff76a1cd0999fd4466ee81250ff";
        assert_eq!(RtcAddress::parse(input), Err(AddressError::InvalidPrefix));
    }

    #[test]
    fn rejects_non_hex_payload() {
        let input = "RTC2fe3c33c77666ff76a1cd0999fd4466ee81250fg";
        assert!(matches!(
            RtcAddress::parse(input),
            Err(AddressError::InvalidHex {
                index: 42,
                byte: b'g'
            })
        ));
    }

    #[test]
    fn validity_helper_matches_parser() {
        assert!(RtcAddress::is_valid(ADDRESS));
        assert!(!RtcAddress::is_valid("not-an-address"));
    }

    #[test]
    fn error_messages_are_actionable() {
        assert_eq!(
            AddressError::InvalidPrefix.to_string(),
            "invalid RTC address prefix: expected RTC"
        );
        assert_eq!(
            AddressError::InvalidLength {
                expected: 43,
                actual: 4
            }
            .to_string(),
            "invalid RTC address length: expected 43, got 4"
        );
    }
}
