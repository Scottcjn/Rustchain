//! Top‑level library entry point for the RustChain repository.
//!
//! The existing codebase already exposes many modules; we add the `bounty`
//! module that contains the human‑reward calculation logic required for
//! bounty #2634.

pub mod bounty;

#[cfg(test)]
mod integration_tests {
    // Placeholder for any integration tests that may be added later.
}
