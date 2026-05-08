/// fingerprint.rs — Hardware fingerprinting primitives for RustChain PoA
///
/// Collects CPU identity, cache-timing signatures, clock-drift coefficients,
/// and architecture detection. These values feed the attestation payload and
/// are used by the node to score "proof of antiquity" (genuine old hardware).
use std::time::{Duration, Instant};

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

/// Aggregated CPU descriptor
#[derive(Debug, Clone)]
pub struct CpuInfo {
    /// Architecture string (x86_64, aarch64, powerpc, riscv64, …)
    pub arch: String,
    /// Logical core count
    pub cores: usize,
    /// Human-readable model name (from /proc/cpuinfo or fallback)
    pub model: String,
    /// Detected cache sizes in bytes (L1d, L2, L3 as available)
    pub cache_sizes: Vec<usize>,
    /// SIMD feature string used for identity hash
    pub simd_features: Vec<String>,
}

// ---------------------------------------------------------------------------
// Architecture detection
// ---------------------------------------------------------------------------

/// Return a canonical architecture string for the currently running CPU.
///
/// Falls back gracefully when the architecture is unknown.
pub fn detect_architecture() -> String {
    // Compile-time targets cover the common cases; we refine with runtime
    // probes where useful.
    #[cfg(target_arch = "x86_64")]
    {
        return "x86_64".to_string();
    }
    #[cfg(target_arch = "x86")]
    {
        return "x86".to_string();
    }
    #[cfg(target_arch = "aarch64")]
    {
        return "aarch64".to_string();
    }
    #[cfg(target_arch = "arm")]
    {
        return "arm".to_string();
    }
    #[cfg(target_arch = "powerpc64")]
    {
        return "powerpc64".to_string();
    }
    #[cfg(target_arch = "powerpc")]
    {
        return "powerpc".to_string();
    }
    #[cfg(target_arch = "riscv64")]
    {
        return "riscv64".to_string();
    }
    #[cfg(target_arch = "riscv32")]
    {
        return "riscv32".to_string();
    }
    #[cfg(target_arch = "mips64")]
    {
        return "mips64".to_string();
    }
    #[cfg(target_arch = "mips")]
    {
        return "mips".to_string();
    }
    #[cfg(target_arch = "s390x")]
    {
        return "s390x".to_string();
    }
    #[cfg(target_arch = "sparc64")]
    {
        return "sparc64".to_string();
    }
    // Generic fallback — should never be reached on supported platforms
    #[allow(unreachable_code)]
    "unknown".to_string()
}

// ---------------------------------------------------------------------------
// CPU info
// ---------------------------------------------------------------------------

/// Probe the host CPU and return a populated [`CpuInfo`].
pub fn get_cpu_info() -> CpuInfo {
    let arch = detect_architecture();
    let cores = num_logical_cores();
    let model = cpu_model_name();
    let cache_sizes = probe_cache_sizes();
    let simd_features = detect_simd_features();

    CpuInfo {
        arch,
        cores,
        model,
        cache_sizes,
        simd_features,
    }
}

fn num_logical_cores() -> usize {
    // std::thread::available_parallelism is stable since Rust 1.59
    std::thread::available_parallelism()
        .map(|n| n.get())
        .unwrap_or(1)
}

fn cpu_model_name() -> String {
    // Linux: parse /proc/cpuinfo
    #[cfg(target_os = "linux")]
    {
        if let Ok(content) = std::fs::read_to_string("/proc/cpuinfo") {
            for line in content.lines() {
                let lower = line.to_lowercase();
                if lower.starts_with("model name")
                    || lower.starts_with("cpu model")
                    || lower.starts_with("hardware")
                {
                    if let Some(val) = line.splitn(2, ':').nth(1) {
                        let trimmed = val.trim().to_string();
                        if !trimmed.is_empty() {
                            return trimmed;
                        }
                    }
                }
            }
        }
    }
    // macOS: sysctl
    #[cfg(target_os = "macos")]
    {
        if let Ok(out) = std::process::Command::new("sysctl")
            .args(["-n", "machdep.cpu.brand_string"])
            .output()
        {
            let s = String::from_utf8_lossy(&out.stdout).trim().to_string();
            if !s.is_empty() {
                return s;
            }
        }
    }
    "unknown".to_string()
}

fn probe_cache_sizes() -> Vec<usize> {
    // Linux exposes cache sizes via sysfs
    let mut sizes = Vec::new();
    #[cfg(target_os = "linux")]
    {
        for index in 0..8 {
            let path = format!("/sys/devices/system/cpu/cpu0/cache/index{}/size", index);
            if let Ok(raw) = std::fs::read_to_string(&path) {
                let trimmed = raw.trim();
                if let Some(kb_str) = trimmed.strip_suffix('K') {
                    if let Ok(kb) = kb_str.parse::<usize>() {
                        sizes.push(kb * 1024);
                        continue;
                    }
                }
                if let Some(mb_str) = trimmed.strip_suffix('M') {
                    if let Ok(mb) = mb_str.parse::<usize>() {
                        sizes.push(mb * 1024 * 1024);
                        continue;
                    }
                }
            } else {
                break;
            }
        }
    }
    if sizes.is_empty() {
        // Sensible unknowns — nodes will still score but with no cache signal
        sizes.push(0);
    }
    sizes
}

fn detect_simd_features() -> Vec<String> {
    let mut features = Vec::new();
    #[cfg(target_arch = "x86_64")]
    {
        if std::is_x86_feature_detected!("sse2") {
            features.push("sse2".to_string());
        }
        if std::is_x86_feature_detected!("sse4.2") {
            features.push("sse4.2".to_string());
        }
        if std::is_x86_feature_detected!("avx") {
            features.push("avx".to_string());
        }
        if std::is_x86_feature_detected!("avx2") {
            features.push("avx2".to_string());
        }
        if std::is_x86_feature_detected!("avx512f") {
            features.push("avx512f".to_string());
        }
    }
    #[cfg(target_arch = "aarch64")]
    {
        // NEON is mandatory on AArch64
        features.push("neon".to_string());
        if std::arch::is_aarch64_feature_detected!("sve") {
            features.push("sve".to_string());
        }
    }
    if features.is_empty() {
        features.push("none".to_string());
    }
    features
}

// ---------------------------------------------------------------------------
// Clock-drift measurement
// ---------------------------------------------------------------------------

/// Measure clock jitter over N short sleep cycles and return the coefficient
/// of variation (stddev / mean) of the observed sleep durations.
///
/// Higher CV → noisier / older clock hardware → higher PoA score.
pub fn measure_clock_drift() -> f64 {
    const SAMPLES: usize = 50;
    const SLEEP_NS: u64 = 1_000; // 1 µs nominal

    let mut durations: Vec<f64> = Vec::with_capacity(SAMPLES);
    for _ in 0..SAMPLES {
        let start = Instant::now();
        std::thread::sleep(Duration::from_nanos(SLEEP_NS));
        durations.push(start.elapsed().as_nanos() as f64);
    }

    let mean = durations.iter().sum::<f64>() / SAMPLES as f64;
    if mean == 0.0 {
        return 0.0;
    }
    let variance = durations.iter().map(|d| (d - mean).powi(2)).sum::<f64>() / SAMPLES as f64;
    let stddev = variance.sqrt();
    stddev / mean // coefficient of variation
}

// ---------------------------------------------------------------------------
// Cache-timing measurement
// ---------------------------------------------------------------------------

/// Probe memory access times at several buffer sizes to infer cache hierarchy.
///
/// Returns a Vec of median access times (in nanoseconds) per buffer size step.
/// The shape of the curve reveals L1/L2/L3 boundaries — distinctive per CPU.
pub fn measure_cache_timing() -> Vec<f64> {
    // Buffer sizes: 4 KiB → 256 KiB → 4 MiB → 64 MiB (one per cache level)
    const SIZES: &[usize] = &[
        4 * 1024,         // L1 territory
        256 * 1024,       // L2 territory
        4 * 1024 * 1024,  // L3 territory
        64 * 1024 * 1024, // RAM
    ];
    const ACCESSES: usize = 1024;

    let mut timings = Vec::with_capacity(SIZES.len());

    for &sz in SIZES {
        // Allocate and fill buffer
        let mut buf: Vec<u8> = vec![1u8; sz];
        let mut idx: usize = 0;
        let stride = sz / ACCESSES;
        let stride = stride.max(64); // at least one cache line

        // Warm up
        for i in (0..sz).step_by(stride) {
            buf[i] = buf[i].wrapping_add(1);
        }

        // Measure
        let start = Instant::now();
        for _ in 0..ACCESSES {
            // Use volatile-style read to prevent optimisation
            let val = unsafe { std::ptr::read_volatile(&buf[idx]) };
            buf[idx] = val.wrapping_add(1);
            idx = (idx + stride) % sz;
        }
        let elapsed_ns = start.elapsed().as_nanos() as f64;
        let per_access_ns = elapsed_ns / ACCESSES as f64;
        timings.push(per_access_ns);

        // Prevent buf being optimised away
        let _ = buf[0];
    }

    timings
}

// ---------------------------------------------------------------------------
// SIMD identity hash
// ---------------------------------------------------------------------------

/// Build a short deterministic string that identifies SIMD capabilities.
/// Used as a cheap attestation field — not security-critical.
pub fn simd_identity(features: &[String]) -> String {
    use sha2::{Digest, Sha256};
    let joined = features.join(",");
    let hash = Sha256::digest(joined.as_bytes());
    format!("{:x}", &hash)[..16].to_string()
}
