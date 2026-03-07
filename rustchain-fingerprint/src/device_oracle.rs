// Check 7: Device Age Oracle (Historicity Attestation)
// =====================================================
// Collects CPU model, release year, and architecture information.
// Detects mismatches between claimed CPU and actual architecture.

use crate::CheckResult;
use serde_json::json;

pub struct DeviceOracleCheck;

impl DeviceOracleCheck {
    pub fn run() -> CheckResult {
        let arch = std::env::consts::ARCH.to_string();
        let (cpu_model, cpu_family) = detect_cpu_info();
        
        let mut mismatch_reasons: Vec<String> = Vec::new();
        
        // Architecture vs claimed CPU family mismatches
        let cpu_lower = cpu_model.as_ref().map(|s| s.to_lowercase()).unwrap_or_default();
        
        // x86 claiming non-x86 vintage
        if (arch == "x86_64" || arch == "x86" || arch == "i686") 
            && (cpu_lower.contains("powerpc") || cpu_lower.contains(" g4") 
                || cpu_lower.contains(" g5") || cpu_lower.contains("sparc") 
                || cpu_lower.contains("m68k")) {
            mismatch_reasons.push("arch_x86_but_claims_vintage_non_x86".to_string());
        }
        
        // PPC claiming x86
        if (arch.contains("ppc") || arch.contains("powerpc"))
            && (cpu_lower.contains("intel") || cpu_lower.contains("amd") || cpu_lower.contains("ryzen")) {
            mismatch_reasons.push("arch_ppc_but_claims_x86".to_string());
        }
        
        // ARM claiming Intel (but not Apple Silicon)
        if (arch.contains("arm") || arch == "aarch64")
            && cpu_lower.contains("intel") && !cpu_lower.contains("apple") {
            mismatch_reasons.push("arch_arm_but_claims_intel".to_string());
        }

        // Estimate release year from CPU model
        let (release_year, year_details) = estimate_release_year(&cpu_model);
        
        // Calculate confidence score
        let mut confidence: f64 = 0.2;
        if cpu_model.is_some() {
            confidence += 0.4;
        }
        if release_year.is_some() {
            confidence += 0.2;
        }
        if !mismatch_reasons.is_empty() {
            confidence -= 0.5;
        }
        confidence = confidence.max(0.0).min(1.0);

        let data = json!({
            "architecture": arch,
            "cpu_model": cpu_model,
            "cpu_family": cpu_family,
            "estimated_release_year": release_year,
            "release_year_details": year_details,
            "mismatch_reasons": mismatch_reasons,
            "confidence": (confidence * 100.0).round() / 100.0,
        });

        // Validation: fail on strong spoofing evidence or missing CPU info
        let mut passed = true;
        let mut fail_reason = None;

        if cpu_model.is_none() {
            passed = false;
            fail_reason = Some("cpu_model_unavailable".to_string());
        } else if !mismatch_reasons.is_empty() {
            passed = false;
            fail_reason = Some("device_age_oracle_mismatch".to_string());
        }

        CheckResult {
            name: "device_age_oracle".to_string(),
            passed,
            data,
            fail_reason,
        }
    }
}

/// Detect CPU information from the system
pub fn detect_cpu_info() -> (Option<String>, Option<u32>) {
    let mut cpu_model: Option<String> = None;
    let mut cpu_family: Option<u32> = None;

    // Linux: read /proc/cpuinfo
    #[cfg(target_os = "linux")]
    {
        if let Ok(cpuinfo) = fs::read_to_string("/proc/cpuinfo") {
            for line in cpuinfo.lines() {
                if line.starts_with("model name") || line.starts_with("cpu model") {
                    if let Some(pos) = line.find(':') {
                        cpu_model = Some(line[pos + 1..].trim().to_string());
                    }
                } else if line.starts_with("cpu family") {
                    if let Some(pos) = line.find(':') {
                        if let Ok(family) = line[pos + 1..].trim().parse::<u32>() {
                            cpu_family = Some(family);
                        }
                    }
                }
            }
        }
    }

    // macOS: use sysctl
    #[cfg(target_os = "macos")]
    {
        if let Ok(output) = Command::new("sysctl")
            .args(&["-n", "machdep.cpu.brand_string"])
            .output()
        {
            cpu_model = Some(String::from_utf8_lossy(&output.stdout).trim().to_string());
        }
        
        // Get CPU family on macOS
        if let Ok(output) = Command::new("sysctl")
            .args(&["-n", "machdep.cpu.family"])
            .output()
        {
            if let Ok(family) = String::from_utf8_lossy(&output.stdout).trim().parse::<u32>() {
                cpu_family = Some(family);
            }
        }
    }

    // Windows: would use WMI or registry (not implemented for cross-compile targets)

    (cpu_model, cpu_family)
}

/// Estimate CPU release year from model string
fn estimate_release_year(cpu_model: &Option<String>) -> (Option<u32>, String) {
    let model = match cpu_model {
        Some(m) => m.to_lowercase(),
        None => return (None, "no_model".to_string()),
    };

    // Apple Silicon
    if let Some(m) = regex::Regex::new(r"apple\s+m(\d)").unwrap().captures(&model) {
        let gen: u32 = m[1].parse().unwrap_or(1);
        let year = match gen {
            1 => 2020,
            2 => 2022,
            3 => 2023,
            4 => 2025,
            _ => 2020 + (gen - 1) * 2,
        };
        return (Some(year), format!("apple_m{}", gen));
    }

    // Intel Core i-series
    if let Some(m) = regex::Regex::new(r"i[3579]-\s*(\d{4,5})").unwrap().captures(&model) {
        let num = &m[1];
        let gen = if num.len() == 5 {
            num[..2].parse::<u32>().unwrap_or(10)
        } else {
            let first = num.chars().next().unwrap().to_digit(10).unwrap_or(2);
            if first >= 1 && first <= 9 { first } else { 2 }
        };
        
        let intel_gen_year = [
            (2, 2011), (3, 2012), (4, 2013), (5, 2014),
            (6, 2015), (7, 2016), (8, 2017), (9, 2018),
            (10, 2019), (11, 2021), (12, 2021), (13, 2022), (14, 2023),
        ];
        
        for (g, y) in intel_gen_year {
            if gen == g {
                return (Some(y), format!("intel_core_gen{}", gen));
            }
        }
    }

    // AMD Ryzen
    if let Some(m) = regex::Regex::new(r"ryzen\s+\d\s+(\d{4})").unwrap().captures(&model) {
        let series: u32 = m[1].chars().next().unwrap().to_digit(10).unwrap_or(1);
        let ryzen_year = [
            (1, 2017), (2, 2018), (3, 2019), (4, 2022),
            (5, 2020), (6, 2021), (7, 2022), (8, 2024), (9, 2025),
        ];
        
        for (s, y) in ryzen_year {
            if series == s {
                return (Some(y), format!("amd_ryzen_{}xxx", series));
            }
        }
    }

    // Vintage families
    if model.contains("g5") || model.contains("970") {
        return (Some(2003), "ppc_g5_family".to_string());
    }
    if model.contains("powerpc") || model.contains("ppc") || model.contains("g4") || model.contains("7450") || model.contains("7447") {
        return (Some(1999), "ppc_g4_family".to_string());
    }
    if model.contains("g3") || model.contains("750") {
        return (Some(1997), "ppc_g3_family".to_string());
    }
    if model.contains("sparc") || model.contains("ultrasparc") {
        return (Some(1995), "sparc_family".to_string());
    }
    if model.contains("core 2") || model.contains("core2") {
        return (Some(2006), "core2_family".to_string());
    }
    if model.contains("pentium") {
        return (Some(2000), "pentium_family".to_string());
    }
    if model.contains("athlon") || model.contains("phenom") {
        return (Some(2003), "amd_k8_family".to_string());
    }

    (None, "unknown".to_string())
}

#[cfg(target_os = "macos")]
use std::process::Command;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_device_oracle_check() {
        let result = DeviceOracleCheck::run();
        assert_eq!(result.name, "device_age_oracle");
        assert!(result.data.get("architecture").is_some());
    }

    #[test]
    fn test_estimate_release_year_apple() {
        let model = Some("Apple M1".to_string());
        let (year, details) = estimate_release_year(&model);
        assert_eq!(year, Some(2020));
        assert_eq!(details, "apple_m1");
    }

    #[test]
    fn test_estimate_release_year_intel() {
        let model = Some("Intel(R) Core(TM) i7-8700K".to_string());
        let (year, _details) = estimate_release_year(&model);
        assert_eq!(year, Some(2017));
    }

    #[test]
    fn test_estimate_release_year_amd() {
        let model = Some("AMD Ryzen 9 5950X".to_string());
        let (year, _details) = estimate_release_year(&model);
        assert_eq!(year, Some(2020));
    }

    #[test]
    fn test_estimate_release_year_ppc() {
        let model = Some("PowerPC G4 (7450)".to_string());
        let (year, details) = estimate_release_year(&model);
        assert_eq!(year, Some(1999));
        assert!(details.contains("ppc_g4"));
    }
}
