// SPDX-License-Identifier: Apache-2.0
//! The main attestation loop.
//!
//! Orchestrates: health check → hardware detection → fingerprinting →
//! challenge → payload build → submit → enroll → balance check → sleep → repeat.

use crate::cli::Cli;
use crate::config::*;
use crate::fingerprint;
use crate::hardware;
use crate::network::RustChainClient;
use crate::payload;
use std::thread;
use std::time::Duration;

/// Run the miner in the specified mode based on CLI flags.
pub fn run(cli: &Cli) -> Result<(), Box<dyn std::error::Error>> {
    // ── Test-only mode ──────────────────────────────────────────────────
    if cli.test_only {
        return run_test_only();
    }

    // ── Wallet is required for all other modes ──────────────────────────
    let wallet = cli.wallet.as_deref().ok_or(
        "Error: --wallet is required for mining. Use --test-only to run fingerprint checks only.",
    )?;

    // ── Initialize client ───────────────────────────────────────────────
    let client = RustChainClient::new(&cli.node)?;
    println!("╔══════════════════════════════════════════════════╗");
    println!("║       RustChain Miner v{}           ║", env!("CARGO_PKG_VERSION"));
    println!("╠══════════════════════════════════════════════════╣");
    println!("║  Wallet : {:<38} ║", wallet);
    println!("║  Node   : {:<38} ║", cli.node);
    println!("╚══════════════════════════════════════════════════╝");
    println!();

    // ── Health check ────────────────────────────────────────────────────
    print!("Checking node health... ");
    match client.health() {
        Ok(h) => {
            if h.ok {
                println!(
                    "✓ Online (v{})",
                    h.version.unwrap_or_else(|| "?".to_string())
                );
            } else {
                println!("⚠ Node reports unhealthy state");
            }
        }
        Err(e) => {
            println!("✗ Failed: {}", e);
            println!("  Will retry during attestation loop...");
        }
    }
    println!();

    // ── Hardware detection ──────────────────────────────────────────────
    println!("Detecting hardware...");
    let hw = hardware::detect();
    println!("  CPU    : {}", hw.cpu_model);
    println!("  Cores  : {}", hw.cpu_cores);
    println!("  RAM    : {} GB", hw.ram_gb);
    println!("  OS     : {}", hw.os);
    println!("  Family : {}", hw.device_family);
    println!("  Arch   : {}", hw.device_arch);
    println!("  MACs   : {:?}", hw.macs);
    println!("  Serial : {}", hw.cpu_serial);
    println!();

    // ── Fingerprint checks ──────────────────────────────────────────────
    println!("Running RIP-PoA fingerprint checks...");
    let fp = fingerprint::run_all_checks();
    print_fingerprint_summary(&fp);
    println!();

    // ── Build payload ───────────────────────────────────────────────────
    // For show-payload / dry-run, we use a placeholder nonce
    let placeholder_nonce = payload::generate_local_nonce();
    let attest_payload = payload::build_payload(wallet, &placeholder_nonce, &hw, &fp);

    // ── Show-payload mode ───────────────────────────────────────────────
    if cli.show_payload {
        println!("Attestation payload:");
        println!("{}", serde_json::to_string_pretty(&attest_payload)?);
        return Ok(());
    }

    // ── Dry-run mode ────────────────────────────────────────────────────
    if cli.dry_run {
        println!("=== DRY RUN ===");
        println!("Payload that would be submitted:");
        println!("{}", serde_json::to_string_pretty(&attest_payload)?);
        println!();
        println!(
            "All fingerprints passed: {}",
            if fp.all_passed { "✓ YES" } else { "✗ NO" }
        );
        return Ok(());
    }

    // ── Live attestation loop ───────────────────────────────────────────
    println!("Starting attestation loop (epoch interval: {}s)...", EPOCH_INTERVAL_SECS);
    println!("─────────────────────────────────────────────────────");

    let mut epoch_count: u32 = 0;

    loop {
        epoch_count += 1;
        println!();
        println!("━━━ Epoch cycle #{} ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", epoch_count);

        // 1. Request challenge nonce
        print!("  Requesting challenge... ");
        let nonce = match request_challenge_with_retry(&client) {
            Ok(n) => {
                println!("✓ nonce={}", &n[..16.min(n.len())]);
                n
            }
            Err(e) => {
                println!("✗ {}", e);
                println!("  Sleeping {}s before retry...", EPOCH_INTERVAL_SECS);
                thread::sleep(Duration::from_secs(EPOCH_INTERVAL_SECS));
                continue;
            }
        };

        // 2. Re-run fingerprints (hardware state may change with thermal drift)
        let fp = fingerprint::run_all_checks();

        // 3. Build attestation payload with real nonce
        let attest_payload = payload::build_payload(wallet, &nonce, &hw, &fp);

        // 4. Submit attestation
        print!("  Submitting attestation... ");
        match submit_with_retry(&client, &attest_payload) {
            Ok(resp) => {
                if let Some(err) = &resp.error {
                    println!("⚠ Server error: {}", err);
                } else {
                    println!("✓ Accepted");
                }
            }
            Err(e) => {
                println!("✗ {}", e);
            }
        }

        // 5. Enroll in epoch
        print!("  Enrolling in epoch... ");
        match client.enroll(wallet, &hw.device_family, &hw.device_arch) {
            Ok(_) => println!("✓ Enrolled"),
            Err(e) => println!("⚠ {}", e),
        }

        // 6. Check balance periodically
        if epoch_count % BALANCE_CHECK_INTERVAL == 0 {
            print!("  Checking balance... ");
            match client.balance(wallet) {
                Ok(bal) => {
                    let rtc = bal.amount_rtc.unwrap_or(0.0);
                    println!("◆ {:.6} RTC", rtc);
                }
                Err(e) => println!("⚠ {}", e),
            }
        }

        // 7. Show epoch info
        if let Ok(epoch_info) = client.epoch() {
            println!(
                "  Epoch: {} | Enrolled miners: {}",
                epoch_info.epoch,
                epoch_info.enrolled_miners.unwrap_or(0)
            );
        }

        // 8. Sleep until next epoch
        println!(
            "  Sleeping {}s until next epoch...",
            EPOCH_INTERVAL_SECS
        );
        thread::sleep(Duration::from_secs(EPOCH_INTERVAL_SECS));
    }
}

/// Run fingerprint checks only (--test-only mode).
fn run_test_only() -> Result<(), Box<dyn std::error::Error>> {
    println!("╔══════════════════════════════════════════════════╗");
    println!("║    RustChain Fingerprint Test Suite              ║");
    println!("╚══════════════════════════════════════════════════╝");
    println!();

    // Hardware summary
    let hw = hardware::detect();
    println!("Hardware: {} ({} / {})", hw.cpu_model, hw.device_family, hw.device_arch);
    println!("Cores: {} | RAM: {} GB | OS: {}", hw.cpu_cores, hw.ram_gb, hw.os);
    println!();

    println!("Running all 6 RIP-PoA fingerprint checks...");
    println!("─────────────────────────────────────────────────────");
    let fp = fingerprint::run_all_checks();
    print_fingerprint_summary(&fp);

    println!();
    if fp.all_passed {
        println!("══ RESULT: ALL CHECKS PASSED ✓ ══");
    } else {
        println!("══ RESULT: SOME CHECKS FAILED ✗ ══");
        println!("   (This may indicate a VM or non-standard hardware)");
    }

    // Print detailed data
    println!();
    println!("Detailed check data:");
    println!("{}", serde_json::to_string_pretty(&fp.checks)?);

    Ok(())
}

/// Print a summary table of fingerprint results.
fn print_fingerprint_summary(fp: &fingerprint::FingerprintResult) {
    let check_order = [
        ("clock_drift", "Clock-Skew & Oscillator Drift"),
        ("cache_timing", "Cache Timing Fingerprint"),
        ("simd_identity", "SIMD Unit Identity"),
        ("thermal_drift", "Thermal Drift Entropy"),
        ("instruction_jitter", "Instruction Path Jitter"),
        ("anti_emulation", "Anti-Emulation / VM Detection"),
    ];

    for (key, name) in &check_order {
        if let Some(result) = fp.checks.get(*key) {
            let status = if result.passed { "✓ PASS" } else { "✗ FAIL" };
            println!("  [{}] {}", status, name);
        }
    }
}

/// Request a challenge nonce with exponential backoff on rate limiting.
fn request_challenge_with_retry(
    client: &RustChainClient,
) -> Result<String, Box<dyn std::error::Error>> {
    let mut delay = BACKOFF_INITIAL_SECS;

    for attempt in 1..=MAX_RETRIES {
        match client.challenge() {
            Ok(resp) => return Ok(resp.nonce),
            Err(e) => {
                let err_str = e.to_string();
                if err_str.contains("rate_limited") {
                    log::warn!(
                        "Rate limited on challenge (attempt {}/{}), backing off {}s",
                        attempt,
                        MAX_RETRIES,
                        delay
                    );
                    thread::sleep(Duration::from_secs(delay));
                    delay = (delay * 2).min(BACKOFF_MAX_SECS);
                } else if attempt < MAX_RETRIES {
                    log::warn!(
                        "Challenge failed (attempt {}/{}): {}, retrying in {}s",
                        attempt,
                        MAX_RETRIES,
                        e,
                        RETRY_DELAY_SECS
                    );
                    thread::sleep(Duration::from_secs(RETRY_DELAY_SECS));
                } else {
                    return Err(e);
                }
            }
        }
    }

    Err("challenge: max retries exceeded".into())
}

/// Submit attestation with exponential backoff on rate limiting.
fn submit_with_retry(
    client: &RustChainClient,
    payload: &serde_json::Value,
) -> Result<crate::network::endpoints::SubmitResponse, Box<dyn std::error::Error>> {
    let mut delay = BACKOFF_INITIAL_SECS;

    for attempt in 1..=MAX_RETRIES {
        match client.submit(payload) {
            Ok(resp) => return Ok(resp),
            Err(e) => {
                let err_str = e.to_string();
                if err_str.contains("rate_limited") {
                    log::warn!(
                        "Rate limited on submit (attempt {}/{}), backing off {}s",
                        attempt,
                        MAX_RETRIES,
                        delay
                    );
                    thread::sleep(Duration::from_secs(delay));
                    delay = (delay * 2).min(BACKOFF_MAX_SECS);
                } else if attempt < MAX_RETRIES {
                    log::warn!(
                        "Submit failed (attempt {}/{}): {}, retrying in {}s",
                        attempt,
                        MAX_RETRIES,
                        e,
                        RETRY_DELAY_SECS
                    );
                    thread::sleep(Duration::from_secs(RETRY_DELAY_SECS));
                } else {
                    return Err(e);
                }
            }
        }
    }

    Err("submit: max retries exceeded".into())
}
