//! Main miner implementation with enrollment and mining loop

use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};
use ed25519_dalek::Signer;
use tokio::time::{sleep, Instant as TokioInstant};

use crate::attestation::{attest_with_key, FingerprintData};
use crate::config::Config;
use crate::error::{MinerError, Result};
use crate::hardware::HardwareInfo;
use crate::transport::NodeTransport;
use reqwest::Client;
use serde_json::json;

/// Mining statistics
#[derive(Debug, Default)]
pub struct MiningStats {
    /// Number of attestations submitted
    pub attestations_submitted: AtomicU64,

    /// Number of enrollments successful
    pub enrollments_success: AtomicU64,

    /// Number of enrollments failed
    pub enrollments_failed: AtomicU64,

    /// Number of shares submitted
    pub shares_submitted: AtomicU64,

    /// Number of shares accepted
    pub shares_accepted: AtomicU64,

    /// Start time
    pub start_time: std::sync::Mutex<Option<Instant>>,
}

impl MiningStats {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn record_attestation(&self) {
        self.attestations_submitted.fetch_add(1, Ordering::Relaxed);
    }

    pub fn record_enrollment_success(&self) {
        self.enrollments_success.fetch_add(1, Ordering::Relaxed);
    }

    pub fn record_enrollment_failed(&self) {
        self.enrollments_failed.fetch_add(1, Ordering::Relaxed);
    }

    pub fn record_share_submitted(&self) {
        self.shares_submitted.fetch_add(1, Ordering::Relaxed);
    }

    pub fn record_share_accepted(&self) {
        self.shares_accepted.fetch_add(1, Ordering::Relaxed);
    }

    pub fn start_timer(&self) {
        *self.start_time.lock().unwrap() = Some(Instant::now());
    }

    pub fn uptime(&self) -> Option<Duration> {
        self.start_time.lock().unwrap().map(|start| start.elapsed())
    }
}

/// RustChain Miner
pub struct Miner {
    /// Configuration
    config: Config,

    /// Node transport
    transport: NodeTransport,

    /// Wallet address
    wallet: String,

    /// Miner ID
    miner_id: String,

    /// Hardware information
    hw_info: HardwareInfo,

    /// Ed25519 signing keypair (used for attestation + enrollment signatures)
    signing_key: ed25519_dalek::SigningKey,

    /// Hex-encoded public key of the signing keypair
    public_key_hex: String,

    /// Attestation valid until (Unix timestamp)
    attestation_valid_until: AtomicU64,

    /// Whether enrolled in current epoch
    enrolled: AtomicBool,

    /// Mining statistics
    stats: Arc<MiningStats>,

    /// Shutdown flag
    shutdown: Arc<AtomicBool>,
}

fn enrollment_message(miner_pubkey: &str, miner_id: &str, epoch: u64) -> String {
    format!("{}|{}|{}", miner_pubkey, miner_id, epoch)
}

fn enrollment_payload(
    miner_pubkey: &str,
    miner_id: &str,
    hw_info: &HardwareInfo,
    signature_hex: &str,
) -> serde_json::Value {
    serde_json::json!({
        "miner_pubkey": miner_pubkey,
        "miner_id": miner_id,
        "device": {
            "family": hw_info.family,
            "arch": hw_info.arch
        },
        "signature": signature_hex,
        "public_key": miner_pubkey
    })
}

fn balance_query_params(miner_id: &str) -> [(&'static str, &str); 1] {
    [("miner_id", miner_id)]
}

fn wallet_balance_rtc(result: &serde_json::Value) -> Option<f64> {
    const SUBUNITS_PER_RTC: f64 = 1_000_000.0;

    fn finite_number(value: f64) -> Option<f64> {
        if value.is_finite() {
            Some(value)
        } else {
            None
        }
    }

    fn as_finite_f64(value: Option<&serde_json::Value>) -> Option<f64> {
        match value? {
            serde_json::Value::Number(number) => number.as_f64().and_then(finite_number),
            serde_json::Value::String(text) => text.parse::<f64>().ok().and_then(finite_number),
            _ => None,
        }
    }

    for field in ["amount_rtc", "balance_rtc", "rtc_balance", "balance"] {
        if let Some(balance) = as_finite_f64(result.get(field)) {
            return Some(balance);
        }
    }

    for field in ["amount_i64", "balance_i64", "balance_urtc"] {
        if let Some(subunits) = as_finite_f64(result.get(field)) {
            return Some(subunits / SUBUNITS_PER_RTC);
        }
    }

    None
}

impl Miner {
    /// Create a new miner with the given configuration
    pub async fn new(config: Config) -> Result<Self> {
        // Collect hardware info
        let hw_info = HardwareInfo::collect()?;

        // Generate or use provided miner_id
        let miner_id = config.miner_id.clone().unwrap_or_else(|| hw_info.generate_miner_id());

        // Generate or use provided wallet
        let wallet = config.wallet.clone().unwrap_or_else(|| hw_info.generate_wallet(&miner_id));

        // Generate Ed25519 signing keypair (reused for attestation + enrollment)
        let signing_key = ed25519_dalek::SigningKey::generate(&mut rand::rngs::OsRng);
        let verifying_key = signing_key.verifying_key();
        let public_key_hex = hex::encode(verifying_key.as_bytes());

        // Create transport
        let mut transport = NodeTransport::new(
            config.node_url.clone(),
            config.proxy_url.clone(),
            config.timeout(),
        )?;

        // Probe transport to determine best connection method
        transport.probe_transport().await;

        Ok(Self {
            config,
            transport,
            wallet,
            miner_id,
            hw_info,
            signing_key,
            public_key_hex,
            attestation_valid_until: AtomicU64::new(0),
            enrolled: AtomicBool::new(false),
            stats: Arc::new(MiningStats::new()),
            shutdown: Arc::new(AtomicBool::new(false)),
        })
    }

    /// Get the wallet address
    pub fn wallet(&self) -> &str {
        &self.wallet
    }

    /// Get the miner ID
    pub fn miner_id(&self) -> &str {
        &self.miner_id
    }

    /// Get hardware info
    pub fn hardware_info(&self) -> &HardwareInfo {
        &self.hw_info
    }

    /// Get mining statistics
    pub fn stats(&self) -> &MiningStats {
        &self.stats
    }

    /// Get a clone of the shutdown flag for signal handlers.
    pub fn shutdown_flag(&self) -> Arc<AtomicBool> {
        Arc::clone(&self.shutdown)
    }

    /// Print miner banner
    pub fn print_banner(&self) {
        println!("{}", "=".repeat(70));
        println!("RustChain Miner v{} - RIP-PoA Hardware Attestation", env!("CARGO_PKG_VERSION"));
        println!("{}", "=".repeat(70));
        println!("Miner ID:    {}", self.miner_id);
        println!("Wallet:      {}", self.wallet);
        println!("Node:        {}", self.config.node_url);
        if let Some(proxy) = &self.config.proxy_url {
            println!("Proxy:       {}", proxy);
        }
        println!("Transport:   {}", if self.transport.using_proxy() { "HTTP Proxy" } else { "Direct HTTPS" });
        println!("{}", "-".repeat(70));
        println!("Platform:    {} / {}", self.hw_info.platform, self.hw_info.machine);
        println!("CPU:         {}", self.hw_info.cpu);
        println!("Cores:       {}", self.hw_info.cores);
        println!("Memory:      {} GB", self.hw_info.memory_gb);
        if let Some(serial) = &self.hw_info.serial {
            println!("Serial:      {}", serial);
        }
        println!("{}", "=".repeat(70));
    }

    /// Run a dry-run (preflight checks only)
    pub async fn dry_run(&self) -> Result<()> {
        println!("\n[DRY-RUN] RustChain Miner preflight");
        println!("[DRY-RUN] No mining or network state will be modified\n");

        println!("[DRY-RUN] Node URL: {}", self.config.node_url);
        println!("[DRY-RUN] Wallet: {}", self.wallet);
        println!("[DRY-RUN] Miner ID: {}", self.miner_id);
        println!("[DRY-RUN] Hostname: {}", self.hw_info.hostname);
        println!("[DRY-RUN] CPU: {}", self.hw_info.cpu);
        println!("[DRY-RUN] Cores: {}", self.hw_info.cores);
        println!("[DRY-RUN] Memory(GB): {}", self.hw_info.memory_gb);
        println!("[DRY-RUN] MAC count: {}", self.hw_info.macs.len());
        println!(
            "[DRY-RUN] Serial present: {}",
            if self.hw_info.serial.is_some() { "yes" } else { "no" }
        );

        // Health probe
        match self.transport.get("/health").await {
            Ok(response) => {
                println!("[DRY-RUN] Health probe: HTTP {}", response.status());
                if response.status().is_success() {
                    if let Ok(data) = response.json::<serde_json::Value>().await {
                        if let Some(version) = data.get("version").and_then(|v| v.as_str()) {
                            println!("[DRY-RUN] Node version: {}", version);
                        }
                    }
                }
            }
            Err(e) => {
                println!("[DRY-RUN] Health probe failed: {}", e);
            }
        }

        println!("\n[DRY-RUN] Next real steps would be: attest -> enroll -> mine loop");
        Ok(())
    }

    /// Perform hardware attestation
    async fn do_attestation(&self) -> Result<()> {
        tracing::info!("[ATTEST] Starting attestation...");

        // For now, no fingerprint data (can be added later)
        let fingerprint_data: Option<FingerprintData> = None;

        match attest_with_key(
            &self.transport,
            &self.wallet,
            &self.miner_id,
            &self.hw_info,
            &self.signing_key,
            &self.public_key_hex,
            fingerprint_data,
        )
        .await
        {
            Ok(_) => {
                self.stats.record_attestation();
                let valid_until = std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap()
                    .as_secs()
                    + self.config.attestation_ttl_secs;
                self.attestation_valid_until.store(valid_until, Ordering::Relaxed);
                Ok(())
            }
            Err(e) => Err(e),
        }
    }

    /// Check if attestation is still valid
    fn is_attestation_valid(&self) -> bool {
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs();
        now < self.attestation_valid_until.load(Ordering::Relaxed)
    }

    /// Enroll in the current epoch
    async fn enroll(&self) -> Result<bool> {
        tracing::info!("[ENROLL] Enrolling in epoch...");

        let epoch_response = self.transport.get("/epoch").await?;
        let epoch_state: serde_json::Value = epoch_response.json().await?;
        let epoch = epoch_state.get("epoch").and_then(|e| e.as_u64()).unwrap_or(0);

        // Sign enrollment request using the SAME Ed25519 keypair from attestation.
        // The signature binds (miner_pubkey|miner_id|epoch) to prove the enrollment
        // caller is the same entity that performed the attestation.
        let miner_pubkey = self.public_key_hex.as_str();
        let enroll_message = enrollment_message(miner_pubkey, &self.miner_id, epoch);
        let signature = self.signing_key.sign(enroll_message.as_bytes());
        let signature_hex = hex::encode(signature.to_bytes());

        let payload = enrollment_payload(
            miner_pubkey,
            &self.miner_id,
            &self.hw_info,
            &signature_hex,
        );

        let response = self.transport.post_json("/epoch/enroll", &payload).await?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().await.unwrap_or_default();
            return Err(MinerError::Enrollment(format!(
                "HTTP {} - {}",
                status, body
            )));
        }

        let result: serde_json::Value = response.json().await?;

        if result.get("ok").and_then(|v| v.as_bool()).unwrap_or(false) {
            self.enrolled.store(true, Ordering::Relaxed);
            self.stats.record_enrollment_success();

            if let Some(epoch) = result.get("epoch") {
                tracing::info!("[ENROLL] Enrolled in epoch: {:?}", epoch);
            }
            if let Some(weight) = result.get("weight").and_then(|w| w.as_f64()) {
                tracing::info!("[ENROLL] Weight: {}x", weight);
            }

            Ok(true)
        } else {
            self.stats.record_enrollment_failed();
            Err(MinerError::Enrollment(format!("Enrollment rejected: {:?}", result)))
        }
    }

    /// Check balance
    pub async fn check_balance(&self) -> Result<f64> {
        let params = balance_query_params(&self.miner_id);
        let response = self.transport.get_with_params("/wallet/balance", &params).await?;

        if !response.status().is_success() {
            return Ok(0.0);
        }

        let result: serde_json::Value = response.json().await?;
        Ok(wallet_balance_rtc(&result).unwrap_or(0.0))
    }

    /// Run the main mining loop
    pub async fn run(&self) -> Result<()> {
        self.stats.start_timer();
        self.print_banner();

        if self.config.dry_run {
            return self.dry_run().await;
        }

        tracing::info!("[MINER] Starting mining loop...");
        println!("\n⛏️  Starting mining...");
        println!("Block time: {} minutes", self.config.block_time_secs / 60);
        println!("Press Ctrl+C to stop\n");

        // Save wallet to file
        let wallet_path = match std::env::consts::OS {
            "windows" => "C:\\temp\\rustchain_miner_wallet.txt",
            _ => "/tmp/rustchain_miner_wallet.txt",
        };
        if let Err(e) = std::fs::write(wallet_path, &self.wallet) {
            tracing::warn!("[MINER] Could not save wallet file: {}", e);
        } else {
            println!("💾 Wallet saved to: {}", wallet_path);
        }

        let mut cycle = 0;

        loop {
            if self.shutdown.load(Ordering::Relaxed) {
                tracing::info!("[MINER] Shutdown requested");
                break;
            }

            cycle += 1;
            println!("\n{}", "=".repeat(70));
            println!("Cycle #{} - {}", cycle, chrono::Local::now().format("%Y-%m-%d %H:%M:%S"));
            println!("{}", "=".repeat(70));

            // --- Heartbeat: verify network connectivity (Issue #7930) ---
            match self.heartbeat().await {
                Ok(()) => {
                    println!("✅ Node connected");
                }
                Err(e) => {
                    println!("⚠️ Network unreachable: {}", e);
                    println!("   Miner will operate in degraded mode (local tracking only)");
                    let state = self.local_state.load();
                    if state.consecutive_failures > 0 {
                        println!("   Offline for: {:?}", state.outage_duration());
                    }
                }
            }

            // Ensure attestation is valid
            if !self.is_attestation_valid() {
                tracing::info!("[MINER] Attestation expired, re-attesting...");
                if let Err(e) = self.do_attestation().await {
                    tracing::error!("[MINER] Attestation failed: {}", e);
                    println!("❌ Attestation failed: {}", e);
                    self.sleep_or_shutdown(Duration::from_secs(30)).await;
                    continue;
                }
            }

            // Enroll in epoch
            match self.enroll().await {
                Ok(_) => {
                    println!("⏳ Mining for {} minutes...", self.config.block_time_secs / 60);

                    // Mining wait loop
                    let block_duration = Duration::from_secs(self.config.block_time_secs);
                    let check_interval = Duration::from_secs(30);
                    let mut elapsed = Duration::from_secs(0);

                    while elapsed < block_duration {
                        if self.shutdown.load(Ordering::Relaxed) {
                            break;
                        }

                        if self.sleep_or_shutdown(check_interval).await {
                            break;
                        }
                        elapsed += check_interval;
                        let remaining = block_duration - elapsed;
                        println!(
                            "   ⏱️  {}s elapsed, {}s remaining...",
                            elapsed.as_secs(),
                            remaining.as_secs()
                        );
                    }

                    // Check balance after epoch
                    match self.check_balance().await {
                        Ok(balance) => println!("\n💰 Balance: {} RTC", balance),
                        Err(e) => tracing::warn!("[MINER] Balance check failed: {}", e),
                    }
                }
                Err(e) => {
                    tracing::error!("[MINER] Enrollment failed: {}", e);
                    println!("❌ Enrollment failed: {}", e);
                    println!("Retrying in 60s...");
                    self.sleep_or_shutdown(Duration::from_secs(60)).await;
                }
            }
        }

        // Shutdown
        println!("\n\n⛔ Mining stopped");
        println!("   Wallet: {}", self.wallet);
        match self.check_balance().await {
            Ok(balance) => println!("   Balance: {} RTC", balance),
            Err(_) => println!("   Balance: (could not fetch)"),
        }

        Ok(())
    }

    /// Signal the miner to shutdown
    pub fn shutdown(&self) {
        self.shutdown.store(true, Ordering::Relaxed);
    }

    /// Check if shutdown was requested
    pub fn is_shutdown(&self) -> bool {
        self.shutdown.load(Ordering::Relaxed)
    }

    async fn sleep_or_shutdown(&self, duration: Duration) -> bool {
        let deadline = TokioInstant::now() + duration;

        loop {
            if self.is_shutdown() {
                return true;
            }

            let now = TokioInstant::now();
            if now >= deadline {
                return false;
            }

            sleep((deadline - now).min(Duration::from_secs(1))).await;
        }
    }

    /// Verify network connectivity via a lightweight node health check.
    /// Includes retry with exponential backoff, error logging, local state tracking,
    /// and alerting via configured webhook on prolonged outages.
    ///
    /// # Returns
    /// - `Ok(())` when the node is reachable
    /// - `Err(MinerError)` when all retries are exhausted
    ///
    /// This method is critical for preventing silent disconnections (Issue #7930).
    /// Miners that cannot reach the node are operating in degraded mode and
    /// should rely on local state tracking.
    pub async fn heartbeat(&self) -> Result<()> {

        let max_retries = self.config.max_heartbeat_retries.unwrap_or(3);
        let base_delay = self.config.heartbeat_base_delay;
        let mut attempt = 0;

        while attempt < max_retries {
            attempt += 1;
            
            // Check if we should shutdown mid-retry
            if self.is_shutdown() {
                return Err(MinerError::MinerError(
                    "Heartbeat aborted: miner shutting down".to_string(),
                ));
            }

            match self.transport.node_health().await {
                Ok(()) => {
                    // Success: reset failure tracking
                    self.heartbeat_success();
                    return Ok(());
                }
                Err(e) => {
                    let msg = format!(
                        "Heartbeat attempt {}/{} failed: {}",
                        attempt, max_retries, e
                    );
                    eprintln!("⚠️ [Heartbeat] {}", msg);
                    
                    if attempt < max_retries {
                        let delay = base_delay * 2u32.pow(attempt - 1);
                        eprintln!("   Retrying in {:?}", delay);
                        sleep(delay).await;
                    }
                }
            }
        }

        // All retries exhausted - record failure in local state
        let state = self.local_state.load();
        let state = state.with_consecutive_failure();
        self.local_state.save(&state);

        // Alert operator if outage persists
        if state.consecutive_failures == 1 {
            // First failure after being healthy - alert immediately
            if let Some(webhook) = &self.alert_webhook {
                let alert_msg = format!(
                    "🚨 Miner {} lost connection to node. Attempting {} retries.",
                    self.miner_id, max_retries
                );
                eprintln!("📢 [Alert] {}", alert_msg);
                // Fire-and-forget the alert
                let wh = webhook.clone();
                let miner_id = self.miner_id.clone();
                tokio::spawn(async move {
                    if let Err(e) = Self::send_alert(&wh, &miner_id, &alert_msg).await {
                        eprintln!("⚠️ Failed to send alert: {}", e);
                    }
                });
            }
        }

        if state.consecutive_failures > 0 {
            eprintln!(
                "📊 [Heartbeat] Offline for {:?} ({} consecutive failures)",
                state.outage_duration(),
                state.consecutive_failures
            );
        }

        Err(MinerError::MinerError(
            format!("Heartbeat failed after {} retries", max_retries),
        ))
    }

    /// Signal that a heartbeat succeeded - resets failure tracking.
    fn heartbeat_success(&self) {
        let state = self.local_state.load();
        let state = state.with_recovery();
        self.local_state.save(&state);
    }

    /// Send an alert notification via webhook.
    async fn send_alert(webhook_url: &str, miner_id: &str, message: &str) -> Result<()> {
        use reqwest::Client;
        use serde_json::json;

        let payload = json!({
            "miner_id": miner_id,
            "alert": message,
            "timestamp": chrono::Utc::now().to_rfc3339()
        });

        let client = Client::new();
        match client
            .post(webhook_url)
            .json(&payload)
            .send()
            .await
        {
            Ok(resp) => {
                if resp.status().is_success() {
                    Ok(())
                } else {
                    Err(MinerError::MinerError(
                        format!("Alert webhook returned status {}", resp.status()),
                    ))
                }
            }
            Err(e) => Err(MinerError::MinerError(format!("Alert webhook error: {}", e))),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::{Read, Write};
    use std::net::TcpListener;
    use std::sync::mpsc;
    use std::thread;

    fn hardware_fixture() -> HardwareInfo {
        HardwareInfo {
            platform: "linux".to_string(),
            machine: "x86_64".to_string(),
            hostname: "test-host".to_string(),
            family: "x86_64".to_string(),
            arch: "modern".to_string(),
            cpu: "test-cpu".to_string(),
            cores: 4,
            memory_gb: 16,
            serial: Some("serial-1".to_string()),
            macs: vec!["00:11:22:33:44:55".to_string()],
            mac: "00:11:22:33:44:55".to_string(),
        }
    }


    /// Helper to create a minimal Miner for tests.
    fn test_miner() -> Miner {
        let signing_key = ed25519_dalek::SigningKey::generate(&mut rand::rngs::OsRng);
        let local_state = StateStore::new(PathBuf::from("/tmp/test_miner_state.json"));
        let _ = std::fs::remove_file("/tmp/test_miner_state.json");

        Miner {
            config: Config::default(),
            transport: NodeTransport::new(
                "https://unused.example.com".to_string(),
                None,
                Duration::from_secs(5),
            )
            .unwrap(),
            wallet: "test-wallet".to_string(),
            miner_id: "test-miner-1".to_string(),
            hw_info: hardware_fixture(),
            public_key_hex: hex::encode(signing_key.verifying_key().as_bytes()),
            signing_key,
            attestation_valid_until: AtomicU64::new(0),
            enrolled: AtomicBool::new(false),
            stats: Arc::new(MiningStats::new()),
            shutdown: Arc::new(AtomicBool::new(false)),
            local_state,
            local_block_height: 0,
            alert_webhook: None,
        }
    }
    #[test]
    fn enrollment_payload_uses_public_key_for_miner_pubkey() {
        let public_key_hex = "aabbccdd";
        let payload = enrollment_payload(
            public_key_hex,
            "miner-123",
            &hardware_fixture(),
            "signature-hex",
        );

        assert_eq!(payload["miner_pubkey"], public_key_hex);
        assert_eq!(payload["public_key"], public_key_hex);
        assert_eq!(payload["miner_id"], "miner-123");
        assert_eq!(payload["device"]["family"], "x86_64");
        assert_eq!(payload["device"]["arch"], "modern");
        assert_eq!(payload["signature"], "signature-hex");
    }

    #[test]
    fn enrollment_signature_binds_the_ed25519_public_key() {
        let signing_key = ed25519_dalek::SigningKey::generate(&mut rand::rngs::OsRng);
        let public_key_hex = hex::encode(signing_key.verifying_key().as_bytes());
        let miner_id = "miner-123";
        let epoch = 42;

        let message = enrollment_message(&public_key_hex, miner_id, epoch);
        let signature = signing_key.sign(message.as_bytes());

        assert_eq!(message, format!("{}|{}|{}", public_key_hex, miner_id, epoch));
        assert!(signing_key
            .verifying_key()
            .verify_strict(message.as_bytes(), &signature)
            .is_ok());

        let wallet_bound_message = enrollment_message("rtc-wallet-address", miner_id, epoch);
        assert!(signing_key
            .verifying_key()
            .verify_strict(wallet_bound_message.as_bytes(), &signature)
            .is_err());
    }

    #[test]
    fn wallet_balance_rtc_accepts_live_balance_fields() {
        assert_eq!(
            wallet_balance_rtc(&serde_json::json!({"amount_rtc": 2.5})),
            Some(2.5)
        );
        assert_eq!(
            wallet_balance_rtc(&serde_json::json!({"amount_i64": 3_750_000})),
            Some(3.75)
        );
        assert_eq!(
            wallet_balance_rtc(&serde_json::json!({"balance_urtc": "1250000"})),
            Some(1.25)
        );
        assert_eq!(
            wallet_balance_rtc(&serde_json::json!({"amount_rtc": true, "balance": ["bad"]})),
            None
        );
    }

    #[test]
    fn balance_query_uses_current_wallet_endpoint() {
        assert_eq!(balance_query_params("miner one"), [("miner_id", "miner one")]);
    }

    #[tokio::test]
    async fn check_balance_requests_current_wallet_endpoint() {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let node_url = format!("http://{}", listener.local_addr().unwrap());
        let (request_tx, request_rx) = mpsc::channel();

        let server = thread::spawn(move || {
            let (mut stream, _) = listener.accept().unwrap();
            let mut buffer = [0; 2048];
            let len = stream.read(&mut buffer).unwrap();
            let request = String::from_utf8_lossy(&buffer[..len]).to_string();
            request_tx.send(request).unwrap();

            let body = r#"{"amount_i64":2500000,"miner_id":"miner%20one"}"#;
            let response = format!(
                "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
                body.len(),
                body
            );
            stream.write_all(response.as_bytes()).unwrap();
        });

        let signing_key = ed25519_dalek::SigningKey::generate(&mut rand::rngs::OsRng);
        let miner = Miner {
            config: Config {
                node_url: node_url.clone(),
                ..Config::default()
        let local_state = StateStore::new(PathBuf::from("/tmp/test_balance_state.json"));
        let _ = std::fs::remove_file("/tmp/test_balance_state.json");
            },
            transport: NodeTransport::new(node_url, None, Duration::from_secs(5)).unwrap(),
            wallet: "wallet-one".to_string(),
            miner_id: "miner one".to_string(),
            hw_info: hardware_fixture(),
            public_key_hex: hex::encode(signing_key.verifying_key().as_bytes()),
            signing_key,
            attestation_valid_until: AtomicU64::new(0),
            enrolled: AtomicBool::new(false),
            stats: Arc::new(MiningStats::new()),
            shutdown: Arc::new(AtomicBool::new(false)),
            local_state,
            local_block_height: 0,
            alert_webhook: None,
        };

        assert_eq!(miner.check_balance().await.unwrap(), 2.5);

        let request = request_rx.recv().unwrap();
        assert!(request.starts_with("GET /wallet/balance?miner_id=miner+one HTTP/1.1"));
        assert!(!request.contains("/balance/wallet-one"));

        server.join().unwrap();
    }

    // --- Heartbeat network failure tests (Issue #7930) ---

    #[tokio::test]
    async fn heartbeat_records_failure_when_node_unreachable() {
        let miner = test_miner();
        
        // Heartbeat should attempt retries and log failure when node is unreachable
        let result = miner.heartbeat().await;
        
        // Expect failure because the transport targets an unreachable URL
        assert!(result.is_err());
        
        // Verify local state recorded the failure
        let state = miner.local_state.load();
        assert!(state.consecutive_failures > 0);
    }

    #[tokio::test]
    async fn heartbeat_retries_on_failure() {
        let miner = test_miner();
        
        // Call heartbeat multiple times to verify retry counter
        let mut fail_count = 0;
        for _ in 0..3 {
            if miner.heartbeat().await.is_err() {
                fail_count += 1;
            }
        }
        
        assert_eq!(fail_count, 3);
        
        let state = miner.local_state.load();
        assert_eq!(state.consecutive_failures, 3);
        assert!(state.outage_start.is_some());
    }

    #[test]
    fn local_state_persists_across_network_outages() {
        let path = std::path::PathBuf::from("/tmp/test_persist_state.json");
        let _ = std::fs::remove_file(&path);
        
        let store = StateStore::new(path.clone());
        
        // Save some state
        let mut s = LocalState::default();
        s.consecutive_failures = 5;
        s.local_block_height = 42;
        s.last_seen_peers = 10;
        store.save(&s).unwrap();
        
        // Load it back (simulating restart after outage)
        let loaded = store.load();
        assert_eq!(loaded.consecutive_failures, 5);
        assert_eq!(loaded.local_block_height, 42);
        assert_eq!(loaded.last_seen_peers, 10);
        
        let _ = std::fs::remove_file(&path);
    }

    #[tokio::test]
    async fn heartbeat_recovery_resets_after_success() {
        // Create a miner with an artificially healthy state
        let miner = test_miner();
        
        // Simulate recovery: set a healthy peer response via transport
        // Since we can't mock the HTTP client easily, we verify the 
        // state load path works and the counter can be reset
        
        // Load current state - should show failures from previous tests
        let state_before = miner.local_state.load();
        
        // In a real scenario, heartbeat_success() would be called after a
        // successful heartbeat, resetting the counter. Verify that function exists.
        miner.heartbeat_success();
        
        // After a successful heartbeat, counter should be 0
        // (even if previous attempts failed)
        let state_after = miner.local_state.load();
        assert_eq!(state_after.consecutive_failures, 0);
        // outage_start should be reset
        assert_eq!(state_after.outage_start, None);
    }

    #[test]
    fn local_state_outage_duration_calculation() {
        let path = std::path::PathBuf::from("/tmp/test_duration.json");
        let _ = std::fs::remove_file(&path);
        
        let store = StateStore::new(path.clone());
        
        // Save state with an outage start time 2 seconds ago
        let mut s = LocalState::default();
        s.consecutive_failures = 3;
        s.outage_start = Some(std::time::SystemTime::now() - std::time::Duration::from_secs(2));
        store.save(&s).unwrap();
        
        let loaded = store.load();
        let duration = loaded.outage_duration();
        // Duration should be >= 1 second (allowing for test timing)
        assert!(duration.as_secs() >= 1);
        
        // State with no outage_start should return zero
        let mut s2 = LocalState::default();
        s2.consecutive_failures = 0;
        s2.outage_start = None;
        store.save(&s2).unwrap();
        
        let loaded2 = store.load();
        assert!(loaded2.outage_duration().as_secs() == 0);
        
        let _ = std::fs::remove_file(&path);
    }
}
