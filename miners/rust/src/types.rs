//! Core types for RustChain miner
//! 
//! This module defines the fundamental data structures used throughout the miner.

use serde::{Deserialize, Serialize};

/// Default node URL for the RustChain network
pub const DEFAULT_NODE_URL: &str = "https://rustchain.org";

/// Default epoch duration in seconds (10 minutes)
pub const EPOCH_DURATION_SECS: u64 = 600;

/// Default attestation check interval in seconds
pub const ATTESTATION_INTERVAL_SECS: u64 = 300;

/// Unit for RTC token amounts (1 RTC = 10^6 micro-RTC)
pub const UNIT: u64 = 1_000_000;

/// Hardware family identifiers
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
#[serde(rename_all = "lowercase")]
pub enum HardwareFamily {
    PowerPC,
    X86,
    X86_64,
    ARM,
    ARM64,
    #[serde(other)]
    Unknown,
}

impl std::fmt::Display for HardwareFamily {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            HardwareFamily::PowerPC => write!(f, "powerpc"),
            HardwareFamily::X86 => write!(f, "x86"),
            HardwareFamily::X86_64 => write!(f, "x86_64"),
            HardwareFamily::ARM => write!(f, "arm"),
            HardwareFamily::ARM64 => write!(f, "arm64"),
            HardwareFamily::Unknown => write!(f, "unknown"),
        }
    }
}

/// Hardware architecture identifiers
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
#[serde(rename_all = "lowercase")]
pub enum HardwareArch {
    // PowerPC architectures
    G3,
    G4,
    G5,
    Ppc64,
    Ppc64le,
    // x86 architectures
    Pentium4,
    Core2,
    Nehalem,
    SandyBridge,
    Haswell,
    Skylake,
    Ryzen,
    // ARM architectures
    CortexA,
    M1,
    M2,
    M3,
    // Generic
    #[serde(other)]
    Unknown,
}

impl std::fmt::Display for HardwareArch {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            HardwareArch::G3 => write!(f, "g3"),
            HardwareArch::G4 => write!(f, "g4"),
            HardwareArch::G5 => write!(f, "g5"),
            HardwareArch::Ppc64 => write!(f, "ppc64"),
            HardwareArch::Ppc64le => write!(f, "ppc64le"),
            HardwareArch::Pentium4 => write!(f, "pentium4"),
            HardwareArch::Core2 => write!(f, "core2"),
            HardwareArch::Nehalem => write!(f, "nehalem"),
            HardwareArch::SandyBridge => write!(f, "sandybridge"),
            HardwareArch::Haswell => write!(f, "haswell"),
            HardwareArch::Skylake => write!(f, "skylake"),
            HardwareArch::Ryzen => write!(f, "ryzen"),
            HardwareArch::CortexA => write!(f, "cortex_a"),
            HardwareArch::M1 => write!(f, "m1"),
            HardwareArch::M2 => write!(f, "m2"),
            HardwareArch::M3 => write!(f, "m3"),
            HardwareArch::Unknown => write!(f, "unknown"),
        }
    }
}

/// Hardware information for attestation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HardwareInfo {
    /// CPU family (e.g., "powerpc", "x86_64")
    pub family: HardwareFamily,
    /// CPU architecture (e.g., "g4", "ryzen", "m1")
    pub arch: HardwareArch,
    /// CPU model name
    pub model: String,
    /// Number of CPU cores
    pub cores: usize,
    /// Total system RAM in bytes
    pub total_ram_bytes: u64,
    /// Hardware serial number (if available)
    pub serial: Option<String>,
    /// Platform identifier
    pub platform: String,
    /// OS version
    pub os_version: String,
}

impl HardwareInfo {
    pub fn new() -> Self {
        Self {
            family: HardwareFamily::Unknown,
            arch: HardwareArch::Unknown,
            model: String::new(),
            cores: 0,
            total_ram_bytes: 0,
            serial: None,
            platform: String::new(),
            os_version: String::new(),
        }
    }

    /// Get the device family string for API
    pub fn device_family(&self) -> String {
        self.family.to_string()
    }

    /// Get the device arch string for API
    pub fn device_arch(&self) -> String {
        self.arch.to_string()
    }
}

impl Default for HardwareInfo {
    fn default() -> Self {
        Self::new()
    }
}

/// Miner configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MinerConfig {
    /// Node URL
    pub node_url: String,
    /// Wallet identifier
    pub wallet: String,
    /// Attestation interval in seconds
    pub attestation_interval_secs: u64,
    /// Enable verbose logging
    pub verbose: bool,
    /// Dry-run mode (no actual API calls)
    pub dry_run: bool,
    /// Show payload mode (print payloads without sending)
    pub show_payload: bool,
    /// Test-only mode (validate locally only)
    pub test_only: bool,
    /// Skip TLS verification (for self-signed certs)
    pub insecure_skip_verify: bool,
}

impl Default for MinerConfig {
    fn default() -> Self {
        Self {
            node_url: DEFAULT_NODE_URL.to_string(),
            wallet: String::new(),
            attestation_interval_secs: ATTESTATION_INTERVAL_SECS,
            verbose: false,
            dry_run: false,
            show_payload: false,
            test_only: false,
            insecure_skip_verify: false,
        }
    }
}

impl MinerConfig {
    pub fn new(wallet: String) -> Self {
        Self {
            wallet,
            ..Default::default()
        }
    }

    pub fn with_node_url(mut self, url: String) -> Self {
        self.node_url = url;
        self
    }

    pub fn with_dry_run(mut self, dry_run: bool) -> Self {
        self.dry_run = dry_run;
        self
    }

    pub fn with_show_payload(mut self, show: bool) -> Self {
        self.show_payload = show;
        self
    }

    pub fn with_test_only(mut self, test: bool) -> Self {
        self.test_only = test;
        self
    }

    pub fn with_verbose(mut self, verbose: bool) -> Self {
        self.verbose = verbose;
        self
    }

    pub fn with_insecure_skip_verify(mut self, skip: bool) -> Self {
        self.insecure_skip_verify = skip;
        self
    }
}

/// Node health response
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HealthResponse {
    pub ok: bool,
    pub version: Option<String>,
    pub uptime_s: Option<u64>,
    pub db_rw: Option<bool>,
    pub backup_age_hours: Option<f64>,
    pub tip_age_slots: Option<u64>,
}

/// Epoch information response
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EpochResponse {
    pub epoch: u64,
    pub slot: u64,
    pub epoch_pot: f64,
    pub enrolled_miners: u64,
    pub blocks_per_epoch: u64,
    pub total_supply_rtc: f64,
}

/// Enrollment request payload
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EnrollRequest {
    pub miner_pubkey: String,
    pub miner_id: String,
    pub device: DeviceInfo,
}

/// Device info for enrollment
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeviceInfo {
    pub family: String,
    pub arch: String,
    pub model: String,
    pub cores: usize,
    pub total_ram_bytes: u64,
}

impl From<&HardwareInfo> for DeviceInfo {
    fn from(hw: &HardwareInfo) -> Self {
        Self {
            family: hw.device_family(),
            arch: hw.device_arch(),
            model: hw.model.clone(),
            cores: hw.cores,
            total_ram_bytes: hw.total_ram_bytes,
        }
    }
}

/// Enrollment response
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EnrollResponse {
    pub ok: bool,
    pub epoch: u64,
    pub weight: f64,
    pub hw_weight: f64,
    pub fingerprint_failed: bool,
    pub miner_pk: String,
    pub miner_id: String,
    pub error: Option<String>,
}

/// Wallet balance response
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BalanceResponse {
    pub miner_id: String,
    pub amount_i64: u64,
    pub amount_rtc: f64,
}

/// Miner info from /api/miners endpoint
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MinerEntry {
    pub miner: String,
    pub last_attest: u64,
    pub first_attest: Option<u64>,
    pub device_family: String,
    pub device_arch: String,
    pub hardware_type: String,
    pub entropy_score: f64,
    pub antiquity_multiplier: f64,
}

/// Miners list response
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MinersResponse {
    #[serde(flatten)]
    pub miners: Vec<MinerEntry>,
}

/// Attestation result
#[derive(Debug, Clone)]
pub struct AttestationResult {
    pub success: bool,
    pub epoch: u64,
    pub weight: f64,
    pub message: String,
}

/// Error types for the miner
#[derive(Debug, thiserror::Error)]
pub enum MinerError {
    #[error("Network error: {0}")]
    Network(#[from] reqwest::Error),

    #[error("Configuration error: {0}")]
    Config(String),

    #[error("Hardware detection error: {0}")]
    Hardware(String),

    #[error("API error: {0}")]
    Api(String),

    #[error("Serialization error: {0}")]
    Serialization(#[from] serde_json::Error),

    #[error("Node returned error: {0}")]
    NodeError(String),
}

pub type Result<T> = std::result::Result<T, MinerError>;
