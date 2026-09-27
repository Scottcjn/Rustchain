// SPDX-License-Identifier: MIT
//! Minimal RustChain SDK entry point.
//!
//! The example SDK crate is intentionally small until the full client API is
//! implemented, but it must still expose a valid crate root for Cargo.
//! (Approach from Scottcjn/Rustchain#8097 by @qiann0512-gif.)

/// SDK crate version from Cargo metadata.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

#[cfg(test)]
mod tests {
    #[test]
    fn version_is_set() {
        assert!(!super::VERSION.is_empty());
    }
}
