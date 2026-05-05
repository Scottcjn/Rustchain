// SPDX-License-Identifier: Apache-2.0
//! Main miner implementation with enrollment and mining loop

use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};
use ed25519_dalek::Signer;
use tokio::time::sleep;

use crate::attestation::{attest_with_key, FingerprintData};
use crate::config::Config;
use crate::error::{MinerError, Result};
use crate::hardware::HardwareInfo;
use crate::transport::NodeTransport;

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
        let enroll_message = format!("{}|{}|{}", self.wallet, self.miner_id, epoch);
        let signature = self.signing_key.sign(enroll_message.as_bytes());
        let signature_hex = hex::encode(signature.to_bytes());

        let payload = serde_json::json!({
            "miner_pubkey": self.wallet,
            "miner_id": self.miner_id,
            "device": {
                "family": self.hw_info.family,
                "arch": self.hw_info.arch
            },
            "signature": signature_hex,
            "public_key": self.public_key_hex
        });

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
        let response = self.transport.get(&format!("/balance/{}", self.wallet)).await?;

        if !response.status().is_success() {
            return Ok(0.0);
        }

        let result: serde_json::Value = response.json().await?;
        Ok(result
            .get("balance_rtc")
            .and_then(|b| b.as_f64())
            .unwrap_or(0.0))
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

            // Ensure attestation is valid
            if !self.is_attestation_valid() {
                tracing::info!("[MINER] Attestation expired, re-attesting...");
                if let Err(e) = self.do_attestation().await {
                    tracing::error!("[MINER] Attestation failed: {}", e);
                    println!("❌ Attestation failed: {}", e);
                    sleep(Duration::from_secs(30)).await;
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

                        sleep(check_interval).await;
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
                    sleep(Duration::from_secs(60)).await;
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
}
