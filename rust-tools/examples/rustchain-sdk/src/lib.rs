//! Minimal RustChain SDK entry point.
//!
//! The example SDK crate is intentionally small until the full client API is
//! implemented, but it must still expose a valid crate root for Cargo.

/// SDK crate version from Cargo metadata.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
