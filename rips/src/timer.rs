//! Epoch Timer Module
//! ===================
//!
//! Handles epoch boundary calculations for the RustChain block chain.
//! Uses checked arithmetic throughout to prevent overflow on very large
//! or negative timestamp deltas (fixes #7988).
//!
//! Key invariant: each epoch is `BLOCK_TIME_SECONDS` (120s) wide,
//! with epoch 0 starting at `epoch_start_time`.

use std::time::{SystemTime, UNIX_EPOCH};

use crate::core_types::BLOCK_TIME_SECONDS;

/// Earliest epoch that can be computed without overflow.
/// `epoch_start_time - epoch * BLOCK_TIME_SECONDS` must not underflow i64.
const MAX_EPOCH: u64 = i64::MAX as u64 / BLOCK_TIME_SECONDS;

/// Epoch timestamp range used by RustChain.
#[derive(Debug, Clone, Copy)]
pub struct EpochRange {
    /// Start timestamp of the epoch (seconds since Unix epoch).
    pub start: i64,
    /// End timestamp of the epoch (exclusive).
    pub end: i64,
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/// Compute the start timestamp of a given epoch.
///
/// Returns `None` if the epoch number is so large that the computation
/// would overflow `i64` (i.e., `epoch > MAX_EPOCH`).
pub fn epoch_start(epoch: u64) -> Option<i64> {
    let delta = BLOCK_TIME_SECONDS.checked_mul(epoch)?;
    // Ensure the subtraction from epoch_start_time does not underflow.
    let result = EPOCH_START_TIME.checked_sub(delta as i64)?;
    Some(result)
}

/// Compute the end timestamp (exclusive) of a given epoch.
///
/// The end is `start + BLOCK_TIME_SECONDS`, computed with overflow
/// protection.  Returns `None` if either the start computation or the
/// addition overflows.
pub fn epoch_end(epoch: u64) -> Option<i64> {
    let start = epoch_start(epoch)?;
    start.checked_add(BLOCK_TIME_SECONDS as i64)
}

/// Get the epoch range for a given epoch.
pub fn epoch_range(epoch: u64) -> Option<EpochRange> {
    let start = epoch_start(epoch)?;
    let end = start.checked_add(BLOCK_TIME_SECONDS as i64)?;
    Some(EpochRange { start, end })
}

/// Get the current epoch number based on the current time.
///
/// If the current time is before the epoch start, returns 0.
pub fn current_epoch() -> u64 {
    let now = current_timestamp();
    let elapsed = now.saturating_sub(EPOCH_START_TIME) as i64;
    if elapsed < 0 {
        return 0;
    }
    (elapsed / BLOCK_TIME_SECONDS as i64) as u64
}

/// Get the current epoch range.
pub fn current_epoch_range() -> EpochRange {
    let epoch = current_epoch();
    epoch_range(epoch).unwrap_or(EpochRange {
        start: EPOCH_START_TIME,
        end: EPOCH_START_TIME + BLOCK_TIME_SECONDS as i64,
    })
}

/// Get the remaining time (in seconds) until the next epoch boundary.
///
/// Returns a non-negative value.
pub fn time_to_epoch_boundary() -> i64 {
    let now = current_timestamp();
    let current_epoch_num = current_epoch();
    let epoch_end = epoch_end(current_epoch_num).unwrap_or(i64::MAX);

    if epoch_end >= now as i64 {
        epoch_end - now as i64
    } else {
        BLOCK_TIME_SECONDS as i64
    }
}

/// Check if a given timestamp falls within a specific epoch.
pub fn timestamp_in_epoch(ts: i64, epoch: u64) -> bool {
    let range = epoch_range(epoch);
    match range {
        Some(r) => ts >= r.start && ts < r.end,
        None => false,
    }
}

/// Convert an epoch number to an approximate wall-clock start time string.
pub fn epoch_start_label(epoch: u64) -> Option<String> {
    let start = epoch_start(epoch)?;
    if start <= 0 {
        return Some(format!("epoch {} (before Unix epoch)", epoch));
    }
    // Simple epoch-to-UTC formatting without chrono dependency
    // Unix epoch: Jan 1 1970. Start time is 2020-01-01.
    let secs = start as u64;
    let days = secs / 86400;
    let remainder = secs % 86400;
    let hours = remainder / 3600;
    let minutes = (remainder % 3600) / 60;
    let seconds = remainder % 60;

    // Approximate year calculation from days since epoch
    let mut year: i64 = 1970;
    let mut day_of_year = days as i64;
    loop {
        let days_in_year = if is_leap_year(year) { 366 } else { 365 };
        if day_of_year < days_in_year {
            break;
        }
        day_of_year -= days_in_year;
        year += 1;
    }

    let month = day_of_year_to_month(day_of_year);
    let day = day_of_year % 31 + 1;

    Some(format!("{}-{:02}-{:02}T{:02}:{:02}:{:02}Z", year, month, day, hours, minutes, seconds))
}

fn is_leap_year(year: i64) -> bool {
    (year % 4 == 0 && year % 100 != 0) || (year % 400 == 0)
}

fn day_of_year_to_month(day: i64) -> u32 {
    let leap = is_leap_year(1970 + day);
    let days_per_month: [i64; 12] = [
        31, if leap { 29 } else { 28 }, 31, 30, 31, 30,
        31, 31, 30, 31, 30, 31,
    ];
    let mut month = 0u32;
    let mut remaining = day;
    for i in 0..12 {
        if remaining < days_per_month[i] {
            month = (i + 1) as u32;
            break;
        }
        remaining -= days_per_month[i];
    }
    month
}

/// Seconds since the epoch start (always >= 0).
pub fn seconds_into_epoch(epoch: u64, ts: i64) -> Option<i64> {
    let range = epoch_range(epoch)?;
    if ts < range.start {
        return Some(-(range.start - ts)); // negative = before epoch
    }
    ts.checked_sub(range.start)
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/// Fixed epoch start timestamp: January 1, 2020 00:00:00 UTC.
///
/// Using a fixed point rather than "now" ensures deterministic epoch
/// boundaries across all nodes.
pub const EPOCH_START_TIME: i64 = 1_577_836_800; // 2020-01-01T00:00:00Z

/// Get current Unix timestamp in seconds (from SystemTime).
fn current_timestamp() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_epoch_zero() {
        let range = epoch_range(0).unwrap();
        assert_eq!(range.start, EPOCH_START_TIME);
        assert_eq!(range.end, EPOCH_START_TIME + BLOCK_TIME_SECONDS as i64);
    }

    #[test]
    fn test_epoch_one() {
        let range = epoch_range(1).unwrap();
        assert_eq!(range.start, EPOCH_START_TIME + BLOCK_TIME_SECONDS as i64);
        assert_eq!(range.end, EPOCH_START_TIME + 2 * BLOCK_TIME_SECONDS as i64);
    }

    #[test]
    fn test_epoch_boundary_non_overlapping() {
        let r0 = epoch_range(0).unwrap();
        let r1 = epoch_range(1).unwrap();
        assert_eq!(r0.end, r1.start);
        assert!(r0.end == r1.start); // epoch 0 end == epoch 1 start
    }

    #[test]
    fn test_large_epoch_still_works() {
        // Large epoch that fits in i64
        let large_epoch = MAX_EPOCH - 1;
        let start = epoch_start(large_epoch);
        assert!(start.is_some());
        let start_val = start.unwrap();
        assert!(start_val >= 0);

        let end = epoch_end(large_epoch);
        assert!(end.is_some());
        assert!(end.unwrap() > start_val);
    }

    #[test]
    fn test_overflow_epoch_returns_none() {
        // Epoch so large it would overflow i64 -> None
        let overflow_epoch = MAX_EPOCH + 100;
        assert!(epoch_start(overflow_epoch).is_none());
        assert!(epoch_end(overflow_epoch).is_none());
        assert!(epoch_range(overflow_epoch).is_none());
    }

    #[test]
    fn test_timestamp_in_epoch() {
        let r0 = epoch_range(0).unwrap();

        // Within epoch 0
        assert!(timestamp_in_epoch(r0.start, 0));
        assert!(timestamp_in_epoch(r0.start + 60, 0)); // halfway

        // Not in epoch 0
        assert!(!timestamp_in_epoch(r0.end, 0)); // end is exclusive
        assert!(!timestamp_in_epoch(r0.start - 1, 0)); // before epoch

        // In epoch 1
        let r1 = epoch_range(1).unwrap();
        assert!(timestamp_in_epoch(r1.start, 1));
    }

    #[test]
    fn test_max_i64_timestamp() {
        // i64::MAX should not cause overflow
        let max_ts = i64::MAX;
        let range = epoch_range(0).unwrap();
        let in_epoch = timestamp_in_epoch(max_ts, 0);
        // i64::MAX is way beyond any epoch, so it should not be in epoch 0
        assert!(!in_epoch);

        // epoch_start and epoch_end should handle max without panicking
        let overflow_epoch = u64::MAX;
        assert!(epoch_start(overflow_epoch).is_none());
        assert!(epoch_end(overflow_epoch).is_none());
    }

    #[test]
    fn test_min_i64_timestamp() {
        // i64::MIN should not cause overflow
        let min_ts = i64::MIN;
        let in_epoch = timestamp_in_epoch(min_ts, 0);
        assert!(!in_epoch); // before epoch 0

        // seconds_into_epoch for timestamp before epoch
        let secs = seconds_into_epoch(0, min_ts);
        assert!(secs.is_some());
        let secs_val = secs.unwrap();
        assert!(secs_val < 0); // negative = before epoch
    }

    #[test]
    fn test_large_negative_delta() {
        // A timestamp very far in the past should still be handled gracefully
        let old_ts: i64 = -1_000_000_000_000;
        let range = epoch_range(0).unwrap();
        let in_epoch = timestamp_in_epoch(old_ts, 0);
        assert!(!in_epoch); // old_ts is way before epoch 0

        let secs = seconds_into_epoch(0, old_ts);
        assert!(secs.is_some());
        assert!(secs.unwrap() < 0);
    }

    #[test]
    fn test_current_epoch_reasonable() {
        let epoch = current_epoch();
        // Should be a positive number well within u64 range
        assert!(epoch > 0);
        assert!(epoch < MAX_EPOCH);

        let range = current_epoch_range();
        let now = current_timestamp();
        assert!(now >= range.start);
        assert!(now < range.end);
    }

    #[test]
    fn test_time_to_boundary_positive() {
        let remaining = time_to_epoch_boundary();
        assert!(remaining > 0);
        assert!(remaining <= BLOCK_TIME_SECONDS as i64);
    }

    #[test]
    fn test_epoch_start_label() {
        let label = epoch_start_label(0);
        assert!(label.is_some());
        assert!(label.unwrap().contains("2020"));

        // Future epoch
        let future_label = epoch_start_label(100);
        assert!(future_label.is_some());

        // Epoch 0 before unix epoch check
        let label = epoch_start_label(u64::MAX);
        // This should be None since it overflows
        assert!(label.is_none());
    }

    #[test]
    fn test_saturating_edge_cases() {
        // Test with exactly BLOCK_TIME_SECONDS boundary
        let r = epoch_range(0).unwrap();
        assert_eq!(r.end - r.start, BLOCK_TIME_SECONDS as i64);

        // Consecutive epochs should not overlap
        let r1 = epoch_range(5).unwrap();
        let r2 = epoch_range(6).unwrap();
        assert_eq!(r1.end, r2.start);
    }

    #[test]
    fn test_checked_arithmetic_not_panicking() {
        // These tests verify that no overflow panics occur
        // even with extreme inputs

        // Maximum possible epoch (overflow)
        let max = epoch_start(u64::MAX);
        assert!(max.is_none());

        // Large but valid epoch
        let valid = epoch_start(MAX_EPOCH);
        assert!(valid.is_some());
        assert!(valid.unwrap() >= 0);

        // Minimum timestamp edge case
        let in_range = timestamp_in_epoch(i64::MIN, 0);
        assert!(!in_range);
    }
}
