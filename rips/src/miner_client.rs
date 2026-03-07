// RustChain Miner Client
// ======================
// Native Rust miner component integrated with RustChain node API endpoints
// Implements hardware fingerprint attestation and epoch-based mining

use std::collections::HashMap;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use serde::{Serialize, Deserialize};
use reqwest::Client;
use tracing::{info, warn, error, debug};

use crate::core_types::{WalletAddress, HardwareInfo, HardwareTier};
use crate::proof_of_antiquity::ProofOfAntiquity;

/// Default node URL for RustChain
pub const DEFAULT_NODE_URL: &str = "https://rustchain.org";

/// Mining epoch duration in seconds (10 minutes)
pub const EPOCH_DURATION_SECS: u64 = 600;

/// Attestation validity period in seconds
pub const ATTESTATION_VALIDITY_SECS: u64 = 3600;

/// Hardware fingerprint client for attestation
#[derive(Debug, Clone)]
pub struct FingerprintAttestation {
    /// Cache timing baseline (nanoseconds)
    pub cache_latencies: CacheLatencies,
    /// CPU feature flags
    pub cpu_flags: Vec<String>,
    /// SIMD capabilities
    pub simd_caps: SimdCapabilities,
    /// Thermal characteristics
    pub thermal_profile: ThermalProfile,
    /// Hardware serial/binding
    pub hardware_serial: Option<String>,
    /// Timestamp of last attestation
    pub attested_at: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CacheLatencies {
    pub l1_ns: f64,
    pub l2_ns: f64,
    pub l3_ns: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SimdCapabilities {
    pub has_altivec: bool,
    pub has_sse: bool,
    pub has_sse2: bool,
    pub has_sse3: bool,
    pub has_ssse3: bool,
    pub has_sse41: bool,
    pub has_sse42: bool,
    pub has_avx: bool,
    pub has_avx2: bool,
    pub has_neon: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ThermalProfile {
    pub baseline_temp_c: f32,
    pub thermal_coefficient: f32,
    pub cooling_efficiency: f32,
}

impl FingerprintAttestation {
    /// Generate a new fingerprint attestation from current hardware
    pub fn generate() -> Result<Self, FingerprintError> {
        let cache_latencies = Self::measure_cache_latencies()?;
        let cpu_flags = Self::detect_cpu_flags();
        let simd_caps = Self::detect_simd_capabilities();
        let thermal_profile = Self::measure_thermal_profile();
        let hardware_serial = Self::get_hardware_serial();

        Ok(FingerprintAttestation {
            cache_latencies,
            cpu_flags,
            simd_caps,
            thermal_profile,
            hardware_serial,
            attested_at: current_timestamp(),
        })
    }

    /// Measure cache latencies using timing benchmarks
    fn measure_cache_latencies() -> Result<CacheLatencies, FingerprintError> {
        // Simplified implementation - in production would do actual timing
        // This is where the 6-check fingerprint system measures cache timing
        let l1_ns = Self::benchmark_cache_level(1);
        let l2_ns = Self::benchmark_cache_level(2);
        let l3_ns = Self::benchmark_cache_level(3);

        Ok(CacheLatencies { l1_ns, l2_ns, l3_ns })
    }

    fn benchmark_cache_level(level: u32) -> f64 {
        use sysinfo::System;
        let mut sys = System::new_all();
        sys.refresh_all();
        
        // Get cache info from CPU - use available methods
        if let Some(cpu) = sys.cpus().first() {
            // sysinfo 0.30 doesn't expose cache sizes directly
            // Use reasonable estimates based on CPU brand
            let brand = cpu.brand();
            if brand.contains("M1") || brand.contains("M2") || brand.contains("M3") {
                // Apple Silicon
                match level {
                    1 => return 12.0,  // 128KB unified
                    2 => return 128.0, // 12MB shared
                    3 => return 500.0, // Large shared
                    _ => {}
                }
            } else if brand.contains("Ryzen") {
                match level {
                    1 => return 16.0,
                    2 => return 256.0,
                    3 => return 1024.0,
                    _ => {}
                }
            } else if brand.contains("Intel") {
                match level {
                    1 => return 16.0,
                    2 => return 256.0,
                    3 => return 2048.0,
                    _ => {}
                }
            }
        }
        
        // Fallback estimates based on typical values
        match level {
            1 => 16.0,   // 32KB * 0.5ns
            2 => 512.0,  // 256KB * 2ns
            3 => 2500.0, // 512KB * 5ns
            _ => 100.0,
        }
    }

    /// Detect CPU feature flags
    fn detect_cpu_flags() -> Vec<String> {
        let mut flags = Vec::new();
        
        // Use Rust's built-in target_feature macros
        #[cfg(target_arch = "x86_64")]
        {
            if cfg!(target_feature = "sse") { flags.push("sse".to_string()); }
            if cfg!(target_feature = "sse2") { flags.push("sse2".to_string()); }
            if cfg!(target_feature = "sse3") { flags.push("sse3".to_string()); }
            if cfg!(target_feature = "ssse3") { flags.push("ssse3".to_string()); }
            if cfg!(target_feature = "sse4.1") { flags.push("sse4.1".to_string()); }
            if cfg!(target_feature = "sse4.2") { flags.push("sse4.2".to_string()); }
            if cfg!(target_feature = "avx") { flags.push("avx".to_string()); }
            if cfg!(target_feature = "avx2") { flags.push("avx2".to_string()); }
        }

        // PowerPC AltiVec detection
        #[cfg(target_arch = "powerpc64")]
        {
            flags.push("altivec".to_string());
            flags.push("vsx".to_string());
        }

        // ARM NEON detection
        #[cfg(target_arch = "aarch64")]
        {
            flags.push("neon".to_string());
        }

        flags
    }

    /// Detect SIMD capabilities
    fn detect_simd_capabilities() -> SimdCapabilities {
        SimdCapabilities {
            has_altivec: cfg!(target_arch = "powerpc64"),
            has_sse: cfg!(all(target_arch = "x86_64", target_feature = "sse")),
            has_sse2: cfg!(all(target_arch = "x86_64", target_feature = "sse2")),
            has_sse3: cfg!(all(target_arch = "x86_64", target_feature = "sse3")),
            has_ssse3: cfg!(all(target_arch = "x86_64", target_feature = "ssse3")),
            has_sse41: cfg!(all(target_arch = "x86_64", target_feature = "sse4.1")),
            has_sse42: cfg!(all(target_arch = "x86_64", target_feature = "sse4.2")),
            has_avx: cfg!(all(target_arch = "x86_64", target_feature = "avx")),
            has_avx2: cfg!(all(target_arch = "x86_64", target_feature = "avx2")),
            has_neon: cfg!(target_arch = "aarch64"),
        }
    }

    /// Measure thermal profile (simplified)
    fn measure_thermal_profile() -> ThermalProfile {
        // In production, would read from hardware sensors
        // For now, use reasonable defaults
        ThermalProfile {
            baseline_temp_c: 45.0,
            thermal_coefficient: 0.8,
            cooling_efficiency: 0.7,
        }
    }

    /// Get hardware serial number
    fn get_hardware_serial() -> Option<String> {
        #[cfg(target_os = "linux")]
        {
            use std::fs;
            let serial_sources = [
                "/sys/class/dmi/id/product_serial",
                "/sys/class/dmi/id/board_serial",
                "/sys/class/dmi/id/chassis_serial",
            ];
            
            for path in &serial_sources {
                if let Ok(serial) = fs::read_to_string(path) {
                    let serial = serial.trim().to_string();
                    if !serial.is_empty() 
                        && serial != "None" 
                        && serial != "To Be Filled By O.E.M."
                        && serial != "Default string" 
                    {
                        return Some(serial);
                    }
                }
            }
            
            // Fallback to machine-id
            if let Ok(machine_id) = fs::read_to_string("/etc/machine-id") {
                return Some(machine_id.trim().chars().take(16).collect());
            }
        }

        #[cfg(target_os = "macos")]
        {
            use std::process::Command;
            if let Ok(output) = Command::new("system_profiler")
                .args(&["SPHardwareDataType", "-json"])
                .output()
            {
                if let Ok(json) = serde_json::from_slice::<serde_json::Value>(&output.stdout) {
                    if let Some(serial) = json["SPHardwareDataType"][0]["serial_number"].as_str() {
                        return Some(serial.to_string());
                    }
                }
            }
        }

        None
    }

    /// Validate attestation against expected hardware profile
    pub fn validate(&self, expected_tier: HardwareTier) -> Result<ValidationResult, FingerprintError> {
        // Check cache latencies match expected tier
        let cache_valid = self.validate_cache_profile(expected_tier);
        
        // Check CPU flags match architecture
        let cpu_valid = self.validate_cpu_flags();
        
        // Check for emulation signatures
        let emulation_check = self.check_emulation_signatures();

        Ok(ValidationResult {
            cache_valid,
            cpu_valid,
            emulation_detected: !emulation_check,
            attestation_age_secs: current_timestamp() - self.attested_at,
            is_fresh: (current_timestamp() - self.attested_at) < ATTESTATION_VALIDITY_SECS,
        })
    }

    fn validate_cache_profile(&self, _tier: HardwareTier) -> bool {
        // L1 cache should be < 50ns for real hardware
        self.cache_latencies.l1_ns < 50.0 &&
        // L2 cache should be < 200ns
        self.cache_latencies.l2_ns < 200.0 &&
        // L3 cache ratio should be reasonable
        self.cache_latencies.l3_ns / self.cache_latencies.l2_ns > 2.0
    }

    fn validate_cpu_flags(&self) -> bool {
        // Must have at least some SIMD capabilities
        self.simd_caps.has_altivec || 
        self.simd_caps.has_sse || 
        self.simd_caps.has_neon
    }

    fn check_emulation_signatures(&self) -> bool {
        // Check for common emulator signatures
        // Real hardware has specific cache timing patterns
        // Emulators often have uniform or unrealistic timings
        
        // QEMU signature: uniform cache latencies
        let qemu_uniform = (self.cache_latencies.l2_ns - self.cache_latencies.l1_ns).abs() < 5.0;
        
        // Bochs signature: extremely slow cache
        let bochs_slow = self.cache_latencies.l1_ns > 100.0;
        
        !qemu_uniform && !bochs_slow
    }

    /// Convert to API-compatible format
    pub fn to_api_format(&self) -> FingerprintApiData {
        FingerprintApiData {
            cache_l1_ns: self.cache_latencies.l1_ns,
            cache_l2_ns: self.cache_latencies.l2_ns,
            cache_l3_ns: self.cache_latencies.l3_ns,
            cpu_flags: self.cpu_flags.clone(),
            simd_caps: self.simd_caps.clone(),
            thermal_baseline: self.thermal_profile.baseline_temp_c,
            hardware_serial: self.hardware_serial.clone(),
            attested_at: self.attested_at,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FingerprintApiData {
    pub cache_l1_ns: f64,
    pub cache_l2_ns: f64,
    pub cache_l3_ns: f64,
    pub cpu_flags: Vec<String>,
    pub simd_caps: SimdCapabilities,
    pub thermal_baseline: f32,
    pub hardware_serial: Option<String>,
    pub attested_at: u64,
}

#[derive(Debug, Clone)]
pub struct ValidationResult {
    pub cache_valid: bool,
    pub cpu_valid: bool,
    pub emulation_detected: bool,
    pub attestation_age_secs: u64,
    pub is_fresh: bool,
}

#[derive(Debug)]
pub enum FingerprintError {
    MeasurementFailed(String),
    EmulationDetected,
    InvalidProfile,
    ExpiredAttestation,
}

impl std::fmt::Display for FingerprintError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            FingerprintError::MeasurementFailed(msg) => write!(f, "Measurement failed: {}", msg),
            FingerprintError::EmulationDetected => write!(f, "Emulation detected"),
            FingerprintError::InvalidProfile => write!(f, "Invalid hardware profile"),
            FingerprintError::ExpiredAttestation => write!(f, "Attestation expired"),
        }
    }
}

impl std::error::Error for FingerprintError {}

/// RustChain miner client for interacting with node API
pub struct MinerClient {
    client: Client,
    node_url: String,
    wallet: WalletAddress,
    hardware_info: HardwareInfo,
    fingerprint: Option<FingerprintAttestation>,
}

/// Miner enrollment response
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EnrollmentResponse {
    pub ok: bool,
    pub miner_id: String,
    pub epoch: u64,
    pub slot: u64,
    pub multiplier: f64,
}

/// Mining proof submission result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MiningResult {
    pub ok: bool,
    pub accepted: bool,
    pub reward_rtc: f64,
    pub epoch: u64,
    pub message: Option<String>,
}

/// Epoch information from node API
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EpochInfo {
    pub epoch: u64,
    pub slot: u64,
    pub blocks_per_epoch: u64,
    pub epoch_pot: f64,
    pub enrolled_miners: u64,
}

/// Health check response
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HealthStatus {
    pub ok: bool,
    pub version: String,
    pub uptime_s: u64,
    pub db_rw: bool,
    pub tip_age_slots: u64,
}

impl MinerClient {
    /// Create a new miner client
    pub fn new(node_url: &str, wallet: &str, hardware: HardwareInfo) -> Result<Self, MinerError> {
        let client = Client::builder()
            .danger_accept_invalid_certs(true) // Node uses self-signed cert
            .timeout(Duration::from_secs(30))
            .build()
            .map_err(|e| MinerError::ConnectionFailed(e.to_string()))?;

        Ok(MinerClient {
            client,
            node_url: node_url.trim_end_matches('/').to_string(),
            wallet: WalletAddress::new(wallet),
            hardware_info: hardware,
            fingerprint: None,
        })
    }

    /// Create with default node URL
    pub fn with_default_node(wallet: &str, hardware: HardwareInfo) -> Result<Self, MinerError> {
        Self::new(DEFAULT_NODE_URL, wallet, hardware)
    }

    /// Enroll miner with the node
    pub async fn enroll(&mut self) -> Result<EnrollmentResponse, MinerError> {
        info!("Enrolling miner {} with node {}", self.wallet.0, self.node_url);

        // Generate fresh fingerprint
        self.fingerprint = Some(FingerprintAttestation::generate()?);
        let fp = self.fingerprint.as_ref().unwrap();

        let payload = EnrollmentRequest {
            wallet: self.wallet.0.clone(),
            hardware_model: self.hardware_info.model.clone(),
            hardware_generation: self.hardware_info.generation.clone(),
            age_years: self.hardware_info.age_years,
            multiplier: self.hardware_info.multiplier,
            fingerprint: fp.to_api_format(),
        };

        let response = self.client
            .post(format!("{}/api/miner/enroll", self.node_url))
            .json(&payload)
            .send()
            .await
            .map_err(|e| MinerError::ConnectionFailed(e.to_string()))?;

        if !response.status().is_success() {
            return Err(MinerError::EnrollmentFailed(
                format!("HTTP {}", response.status())
            ));
        }

        let result: EnrollmentResponse = response.json().await
            .map_err(|e| MinerError::ParseError(e.to_string()))?;

        info!("Miner enrolled successfully: epoch={}, multiplier={}", 
              result.epoch, result.multiplier);

        Ok(result)
    }

    /// Submit mining proof for current epoch
    pub async fn submit_proof(&self) -> Result<MiningResult, MinerError> {
        debug!("Submitting mining proof for wallet {}", self.wallet.0);

        let payload = MiningProofRequest {
            wallet: self.wallet.0.clone(),
            timestamp: current_timestamp(),
            fingerprint_hash: self.get_fingerprint_hash(),
        };

        let response = self.client
            .post(format!("{}/api/miner/submit", self.node_url))
            .json(&payload)
            .send()
            .await
            .map_err(|e| MinerError::ConnectionFailed(e.to_string()))?;

        let result: MiningResult = response.json().await
            .map_err(|e| MinerError::ParseError(e.to_string()))?;

        if result.ok && result.accepted {
            info!("Mining proof accepted: reward={} RTC", result.reward_rtc);
        } else {
            warn!("Mining proof rejected: {:?}", result.message);
        }

        Ok(result)
    }

    /// Get current epoch information
    pub async fn get_epoch_info(&self) -> Result<EpochInfo, MinerError> {
        let response = self.client
            .get(format!("{}/epoch", self.node_url))
            .send()
            .await
            .map_err(|e| MinerError::ConnectionFailed(e.to_string()))?;

        response.json().await
            .map_err(|e| MinerError::ParseError(e.to_string()))
    }

    /// Check node health
    pub async fn check_health(&self) -> Result<HealthStatus, MinerError> {
        let response = self.client
            .get(format!("{}/health", self.node_url))
            .send()
            .await
            .map_err(|e| MinerError::ConnectionFailed(e.to_string()))?;

        response.json().await
            .map_err(|e| MinerError::ParseError(e.to_string()))
    }

    /// Get wallet balance
    pub async fn get_balance(&self) -> Result<f64, MinerError> {
        let response = self.client
            .get(format!("{}/wallet/balance?miner_id={}", self.node_url, self.wallet.0))
            .send()
            .await
            .map_err(|e| MinerError::ConnectionFailed(e.to_string()))?;

        let result: serde_json::Value = response.json().await
            .map_err(|e| MinerError::ParseError(e.to_string()))?;

        result["amount_rtc"].as_f64()
            .ok_or_else(|| MinerError::ParseError("Invalid balance response".to_string()))
    }

    /// Get fingerprint hash for proof submission
    fn get_fingerprint_hash(&self) -> String {
        use sha2::{Sha256, Digest};
        
        if let Some(fp) = &self.fingerprint {
            let data = format!(
                "{}:{}:{}:{}:{}",
                fp.cache_latencies.l1_ns,
                fp.cache_latencies.l2_ns,
                fp.cache_latencies.l3_ns,
                fp.cpu_flags.join(","),
                fp.hardware_serial.as_deref().unwrap_or("none")
            );
            
            let mut hasher = Sha256::new();
            hasher.update(data.as_bytes());
            hex::encode(hasher.finalize())
        } else {
            hex::encode([0u8; 32])
        }
    }

    /// Check if fingerprint attestation is still valid
    pub fn is_attestation_valid(&self) -> bool {
        if let Some(fp) = &self.fingerprint {
            (current_timestamp() - fp.attested_at) < ATTESTATION_VALIDITY_SECS
        } else {
            false
        }
    }

    /// Refresh fingerprint attestation
    pub async fn refresh_attestation(&mut self) -> Result<(), MinerError> {
        self.fingerprint = Some(FingerprintAttestation::generate()?);
        Ok(())
    }
}

#[derive(Debug, Serialize)]
struct EnrollmentRequest {
    wallet: String,
    hardware_model: String,
    hardware_generation: String,
    age_years: u32,
    multiplier: f64,
    fingerprint: FingerprintApiData,
}

#[derive(Debug, Serialize)]
struct MiningProofRequest {
    wallet: String,
    timestamp: u64,
    fingerprint_hash: String,
}

/// Miner client errors
#[derive(Debug)]
pub enum MinerError {
    ConnectionFailed(String),
    EnrollmentFailed(String),
    ParseError(String),
    FingerprintError(FingerprintError),
    Timeout,
}

impl std::fmt::Display for MinerError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            MinerError::ConnectionFailed(msg) => write!(f, "Connection failed: {}", msg),
            MinerError::EnrollmentFailed(msg) => write!(f, "Enrollment failed: {}", msg),
            MinerError::ParseError(msg) => write!(f, "Parse error: {}", msg),
            MinerError::FingerprintError(e) => write!(f, "Fingerprint error: {}", e),
            MinerError::Timeout => write!(f, "Request timeout"),
        }
    }
}

impl std::error::Error for MinerError {}

impl From<FingerprintError> for MinerError {
    fn from(e: FingerprintError) -> Self {
        MinerError::FingerprintError(e)
    }
}

/// Helper to get current Unix timestamp
fn current_timestamp() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or(Duration::ZERO)
        .as_secs()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_fingerprint_generation() {
        let fp = FingerprintAttestation::generate();
        assert!(fp.is_ok());
        
        let fp = fp.unwrap();
        assert!(fp.cache_latencies.l1_ns > 0.0);
        assert!(!fp.cpu_flags.is_empty());
    }

    #[test]
    fn test_simd_detection() {
        let simd = FingerprintAttestation::detect_simd_capabilities();
        
        // At least one SIMD capability should be detected
        assert!(
            simd.has_altivec || 
            simd.has_sse || 
            simd.has_neon ||
            simd.has_avx
        );
    }

    #[test]
    fn test_miner_client_creation() {
        let hardware = HardwareInfo::new(
            "Test CPU".to_string(),
            "Test".to_string(),
            10
        );
        
        let client = MinerClient::with_default_node("test-wallet", hardware);
        assert!(client.is_ok());
    }
}
