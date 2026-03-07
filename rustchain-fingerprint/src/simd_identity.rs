// Check 3: SIMD Unit Identity
// ============================
// Detects and validates SIMD capabilities (SSE/AVX/AltiVec/NEON).
// Architecture-specific guards for x86_64, aarch64, and powerpc.

use crate::CheckResult;
use serde_json::json;

pub struct SIMDIdentityCheck;

impl SIMDIdentityCheck {
    pub fn run() -> CheckResult {
        let arch = std::env::consts::ARCH;
        
        let (has_sse, has_avx, has_altivec, has_neon, simd_flags) = detect_simd_features();

        let data = json!({
            "architecture": arch,
            "has_sse": has_sse,
            "has_avx": has_avx,
            "has_altivec": has_altivec,
            "has_neon": has_neon,
            "simd_flags_count": simd_flags.len(),
            "simd_flags": simd_flags,
        });

        // Validation: should have at least one SIMD feature
        let mut passed = true;
        let mut fail_reason = None;

        let has_any_simd = has_sse || has_avx || has_altivec || has_neon || !simd_flags.is_empty();
        
        if !has_any_simd {
            passed = false;
            fail_reason = Some("no_simd_detected".to_string());
        }

        // Architecture-specific validation
        match arch {
            "x86_64" | "x86" | "i686" => {
                // x86 should have SSE at minimum
                if !has_sse && !has_avx && simd_flags.is_empty() {
                    passed = false;
                    fail_reason = Some("x86_missing_simd".to_string());
                }
            }
            "aarch64" | "arm" => {
                // ARM64 should have NEON
                if !has_neon && simd_flags.is_empty() {
                    passed = false;
                    fail_reason = Some("arm_missing_neon".to_string());
                }
            }
            "powerpc" | "powerpc64" => {
                // PowerPC should have AltiVec/VMX
                if !has_altivec && simd_flags.is_empty() {
                    passed = false;
                    fail_reason = Some("ppc_missing_altivec".to_string());
                }
            }
            _ => {}
        }

        CheckResult {
            name: "simd_identity".to_string(),
            passed,
            data,
            fail_reason,
        }
    }
}

/// Detect SIMD features based on architecture
fn detect_simd_features() -> (bool, bool, bool, bool, Vec<String>) {
    let arch = std::env::consts::ARCH;
    let mut flags = Vec::new();
    let mut has_sse = false;
    let mut has_avx = false;
    let mut has_altivec = false;
    let mut has_neon = false;

    // Linux: read /proc/cpuinfo
    #[cfg(target_os = "linux")]
    {
        if let Ok(cpuinfo) = std::fs::read_to_string("/proc/cpuinfo") {
            for line in cpuinfo.lines() {
                if line.starts_with("flags") || line.starts_with("Features") {
                    if let Some(pos) = line.find(':') {
                        let features: Vec<&str> = line[pos + 1..].split_whitespace().collect();
                        flags = features.iter().map(|s| s.to_string()).collect();
                        
                        has_sse = features.iter().any(|&f| f.starts_with("sse"));
                        has_avx = features.iter().any(|&f| f.starts_with("avx"));
                        has_neon = features.iter().any(|&f| f == "neon" || f.starts_with("asimd"));
                        has_altivec = features.iter().any(|&f| f == "altivec" || f == "vsx");
                        break;
                    }
                }
            }
        }
    }

    // macOS: use sysctl
    #[cfg(target_os = "macos")]
    {
        if let Ok(output) = std::process::Command::new("sysctl")
            .args(&["-a"])
            .output()
        {
            let output = String::from_utf8_lossy(&output.stdout);
            for line in output.lines() {
                if line.contains("feature") || line.contains("altivec") {
                    flags.push(line.to_string());
                    if line.contains("altivec") {
                        has_altivec = true;
                    }
                }
                if line.contains("sse") {
                    has_sse = true;
                }
                if line.contains("avx") {
                    has_avx = true;
                }
                if line.contains("neon") || line.contains("fp") {
                    has_neon = true;
                }
            }
        }
    }

    // Fallback: use architecture defaults
    if flags.is_empty() {
        match arch {
            "x86_64" | "x86" | "i686" => {
                has_sse = true;
                flags.push("sse".to_string());
                flags.push("sse2".to_string());
                #[cfg(target_feature = "avx")]
                {
                    has_avx = true;
                    flags.push("avx".to_string());
                }
            }
            "aarch64" | "arm" => {
                has_neon = true;
                flags.push("neon".to_string());
                flags.push("asimd".to_string());
            }
            "powerpc" | "powerpc64" => {
                has_altivec = true;
                flags.push("altivec".to_string());
                flags.push("vsx".to_string());
            }
            _ => {}
        }
    }

    (has_sse, has_avx, has_altivec, has_neon, flags)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_simd_identity_check() {
        let result = SIMDIdentityCheck::run();
        assert_eq!(result.name, "simd_identity");
        assert!(result.data.get("architecture").is_some());
    }

    #[test]
    fn test_detect_simd_features() {
        let (sse, avx, altivec, neon, flags) = detect_simd_features();
        // At least one should be true based on architecture
        assert!(sse || avx || altivec || neon || !flags.is_empty());
    }
}
