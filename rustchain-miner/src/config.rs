// SPDX-License-Identifier: Apache-2.0
/// Default node URL (self-signed TLS).
#[allow(dead_code)]
pub const DEFAULT_NODE_URL: &str = "https://50.28.86.131";

/// Epoch interval in seconds (10 minutes).
pub const EPOCH_INTERVAL_SECS: u64 = 600;

/// Number of clock-drift samples to collect.
pub const CLOCK_DRIFT_SAMPLES: usize = 1000;

/// Maximum retry attempts for transient network errors.
pub const MAX_RETRIES: u32 = 3;

/// Initial backoff delay in seconds for 429 rate-limit responses.
pub const BACKOFF_INITIAL_SECS: u64 = 2;

/// Maximum backoff delay in seconds.
pub const BACKOFF_MAX_SECS: u64 = 64;

/// Retry delay for connection errors (seconds).
pub const RETRY_DELAY_SECS: u64 = 10;

/// Balance check interval — every N epochs.
pub const BALANCE_CHECK_INTERVAL: u32 = 3;
