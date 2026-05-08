/// RustChain Native Rust Miner — v0.1.0
///
/// Implements the Proof-of-Antiquity attestation loop:
///   1. Collect hardware fingerprint (CPU, cache, clock)
///   2. Build signed attestation payload
///   3. POST to /attest/submit on the configured node
///   4. Sleep for `--interval` seconds, then repeat
///
/// Usage:
///   rustchain-miner --node-url http://localhost:8333 \
///                   --miner-id my-rig-01 \
///                   --interval 60
mod fingerprint;

use chrono::Utc;
use clap::Parser;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::time::Duration;
use tokio::time::sleep;

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------

/// RustChain native Rust miner — Proof-of-Antiquity attestation client
#[derive(Parser, Debug)]
#[command(name = "rustchain-miner", version = "0.1.0", about)]
struct Args {
    /// Full URL of the RustChain node (e.g. http://localhost:8333)
    #[arg(long, default_value = "http://localhost:8333")]
    node_url: String,

    /// Unique miner identifier (hostname, custom string, wallet address, …)
    #[arg(long, default_value = "default-miner")]
    miner_id: String,

    /// Seconds between attestation submissions
    #[arg(long, default_value_t = 60)]
    interval: u64,

    /// Maximum retry attempts per submission before giving up for this cycle
    #[arg(long, default_value_t = 3)]
    max_retries: u32,

    /// Initial back-off in milliseconds between retries (doubles each attempt)
    #[arg(long, default_value_t = 1000)]
    retry_backoff_ms: u64,
}

// ---------------------------------------------------------------------------
// Payload types
// ---------------------------------------------------------------------------

#[derive(Serialize, Deserialize, Debug)]
struct DeviceInfo {
    arch: String,
    cores: usize,
    model: String,
}

#[derive(Serialize, Deserialize, Debug)]
struct FingerprintPayload {
    clock_drift_cv: f64,
    cache_timing: Vec<f64>,
    thermal_drift: f64,
    simd_identity: String,
}

#[derive(Serialize, Deserialize, Debug)]
struct AttestationPayload {
    miner: String,
    timestamp: String,
    device: DeviceInfo,
    fingerprint: FingerprintPayload,
    /// SHA-256 of canonical JSON fields (miner + timestamp + arch)
    integrity_hash: String,
}

#[derive(Deserialize, Debug)]
struct AttestationResponse {
    #[serde(default)]
    accepted: bool,
    #[serde(default)]
    score: f64,
    #[serde(default)]
    message: String,
    #[serde(default)]
    block_reward: Option<f64>,
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/// Compute a simple integrity hash over the most critical fields so the node
/// can detect trivially tampered payloads.
fn integrity_hash(miner: &str, timestamp: &str, arch: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(miner.as_bytes());
    hasher.update(b"|");
    hasher.update(timestamp.as_bytes());
    hasher.update(b"|");
    hasher.update(arch.as_bytes());
    format!("{:x}", hasher.finalize())
}

/// Estimate thermal drift as a proxy metric: compare two rapid clock_drift
/// samples separated by a brief CPU-bound loop.  Older hardware shows more
/// variance here due to less sophisticated thermal management.
fn estimate_thermal_drift() -> f64 {
    let first = fingerprint::measure_clock_drift();
    // Burn ~5 ms on simple arithmetic to warm up the core
    let mut acc: u64 = 1;
    for i in 1u64..=500_000 {
        acc = acc.wrapping_mul(i).wrapping_add(7);
    }
    let _ = acc; // prevent optimisation
    let second = fingerprint::measure_clock_drift();
    (second - first).abs()
}

// ---------------------------------------------------------------------------
// ANSI colour helpers (no external dep)
// ---------------------------------------------------------------------------

const RESET: &str = "\x1b[0m";
const BOLD: &str = "\x1b[1m";
const GREEN: &str = "\x1b[32m";
const YELLOW: &str = "\x1b[33m";
const CYAN: &str = "\x1b[36m";
const RED: &str = "\x1b[31m";
const MAGENTA: &str = "\x1b[35m";

fn log_info(msg: &str) {
    println!("{CYAN}[INFO]{RESET} {msg}");
}

fn log_ok(msg: &str) {
    println!("{GREEN}{BOLD}[ OK ]{RESET} {msg}");
}

fn log_warn(msg: &str) {
    eprintln!("{YELLOW}[WARN]{RESET} {msg}");
}

fn log_err(msg: &str) {
    eprintln!("{RED}[ERR ]{RESET} {msg}");
}

fn log_section(title: &str) {
    println!("\n{MAGENTA}{BOLD}══ {title} ══{RESET}");
}

// ---------------------------------------------------------------------------
// Core attestation loop
// ---------------------------------------------------------------------------

/// Collect the full fingerprint and build the attestation payload.
fn build_payload(miner_id: &str) -> AttestationPayload {
    log_info("Collecting hardware fingerprint…");
    let cpu = fingerprint::get_cpu_info();

    log_info(&format!(
        "  arch={BOLD}{}{RESET}  cores={BOLD}{}{RESET}  model={BOLD}{}{RESET}",
        cpu.arch, cpu.cores, cpu.model
    ));

    let clock_drift_cv = fingerprint::measure_clock_drift();
    log_info(&format!("  clock_drift_cv={:.6}", clock_drift_cv));

    let cache_timing = fingerprint::measure_cache_timing();
    log_info(&format!(
        "  cache_timing=[{}]",
        cache_timing
            .iter()
            .map(|v| format!("{:.1}ns", v))
            .collect::<Vec<_>>()
            .join(", ")
    ));

    let thermal_drift = estimate_thermal_drift();
    log_info(&format!("  thermal_drift={:.6}", thermal_drift));

    let simd_id = fingerprint::simd_identity(&cpu.simd_features);
    log_info(&format!("  simd_identity={}", simd_id));

    let timestamp = Utc::now().to_rfc3339();
    let hash = integrity_hash(miner_id, &timestamp, &cpu.arch);

    AttestationPayload {
        miner: miner_id.to_string(),
        timestamp,
        device: DeviceInfo {
            arch: cpu.arch,
            cores: cpu.cores,
            model: cpu.model,
        },
        fingerprint: FingerprintPayload {
            clock_drift_cv,
            cache_timing,
            thermal_drift,
            simd_identity: simd_id,
        },
        integrity_hash: hash,
    }
}

/// POST the payload to the node, with exponential back-off retries.
async fn submit_attestation(
    client: &Client,
    node_url: &str,
    payload: &AttestationPayload,
    max_retries: u32,
    initial_backoff_ms: u64,
) -> Result<AttestationResponse, String> {
    let endpoint = format!("{}/attest/submit", node_url.trim_end_matches('/'));
    let mut backoff = initial_backoff_ms;

    for attempt in 1..=max_retries {
        log_info(&format!(
            "Submitting attestation (attempt {attempt}/{max_retries}) → {endpoint}"
        ));

        match client
            .post(&endpoint)
            .json(payload)
            .timeout(Duration::from_secs(30))
            .send()
            .await
        {
            Ok(resp) => {
                let status = resp.status();
                if status.is_success() {
                    match resp.json::<AttestationResponse>().await {
                        Ok(body) => return Ok(body),
                        Err(e) => {
                            log_warn(&format!("Response parse error: {e}"));
                            // Treat as accepted if status was 2xx but body is unexpected
                            return Ok(AttestationResponse {
                                accepted: true,
                                score: 0.0,
                                message: "ok (unparsed)".to_string(),
                                block_reward: None,
                            });
                        }
                    }
                } else {
                    let body = resp.text().await.unwrap_or_default();
                    log_warn(&format!("Node returned HTTP {status}: {body}"));
                }
            }
            Err(e) => {
                log_warn(&format!("Request error: {e}"));
            }
        }

        if attempt < max_retries {
            log_info(&format!("Retrying in {backoff} ms…"));
            sleep(Duration::from_millis(backoff)).await;
            backoff = (backoff * 2).min(30_000); // cap at 30 s
        }
    }

    Err(format!(
        "All {max_retries} attempts failed — skipping this cycle"
    ))
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

#[tokio::main]
async fn main() {
    let args = Args::parse();

    log_section("RustChain Native Miner v0.1.0");
    log_info(&format!("Node URL  : {BOLD}{}{RESET}", args.node_url));
    log_info(&format!("Miner ID  : {BOLD}{}{RESET}", args.miner_id));
    log_info(&format!("Interval  : {BOLD}{}s{RESET}", args.interval));

    let client = Client::builder()
        .user_agent("rustchain-miner/0.1.0")
        .build()
        .expect("Failed to build HTTP client");

    let mut cycle: u64 = 0;

    loop {
        cycle += 1;
        log_section(&format!("Attestation Cycle #{cycle}"));

        let payload = build_payload(&args.miner_id);

        match submit_attestation(
            &client,
            &args.node_url,
            &payload,
            args.max_retries,
            args.retry_backoff_ms,
        )
        .await
        {
            Ok(resp) => {
                if resp.accepted {
                    let reward_str = resp
                        .block_reward
                        .map(|r| format!("  reward={BOLD}{r:.4} RTC{RESET}"))
                        .unwrap_or_default();
                    log_ok(&format!(
                        "Attestation accepted — score={BOLD}{:.4}{RESET}{reward_str}  msg={}",
                        resp.score, resp.message
                    ));
                } else {
                    log_warn(&format!("Attestation rejected: {}", resp.message));
                }
            }
            Err(e) => {
                log_err(&e);
            }
        }

        log_info(&format!("Sleeping {}s until next cycle…", args.interval));
        sleep(Duration::from_secs(args.interval)).await;
    }
}
