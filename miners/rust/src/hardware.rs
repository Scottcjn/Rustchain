//! Hardware detection module
//! 
//! Detects CPU, memory, and platform information for attestation.
//! 
//! Phase-1: Basic hardware detection using sysinfo crate
//! Phase-2: Will add RIP-PoA fingerprint checks (clock drift, cache timing, etc.)

use crate::types::{HardwareArch, HardwareFamily, HardwareInfo, Result};
use sysinfo::System;

/// Detect hardware information
pub fn detect_hardware() -> Result<HardwareInfo> {
    let mut sys = System::new_all();
    sys.refresh_all();

    let mut hw = HardwareInfo::new();

    // Detect CPU information
    let cpu = sys.global_cpu_info();
    hw.model = cpu.name().to_string();
    hw.cores = sys.physical_core_count().unwrap_or(1);

    // Detect platform and architecture
    let arch = detect_arch();
    hw.family = arch.0;
    hw.arch = arch.1;

    // Detect total RAM
    hw.total_ram_bytes = sys.total_memory() * 1024; // sysinfo returns KB

    // Detect platform
    hw.platform = std::env::consts::OS.to_string();
    hw.os_version = get_os_version();

    // Try to get hardware serial (platform-specific)
    hw.serial = get_hardware_serial();

    Ok(hw)
}

/// Detect CPU architecture
fn detect_arch() -> (HardwareFamily, HardwareArch) {
    let arch = std::env::consts::ARCH;
    let family = std::env::consts::FAMILY;

    match (family, arch) {
        ("x86", "x86") => detect_x86_arch(),
        ("x86", "x86_64") => detect_x86_64_arch(),
        ("aarch64", "aarch64") => detect_arm64_arch(),
        ("powerpc", _) => detect_powerpc_arch(),
        _ => (HardwareFamily::Unknown, HardwareArch::Unknown),
    }
}

/// Detect x86 architecture variant
fn detect_x86_arch() -> (HardwareFamily, HardwareArch) {
    // For 32-bit x86, try to detect specific generation
    #[cfg(target_arch = "x86")]
    {
        if let Some(brand) = get_cpu_brand() {
            let brand_lower = brand.to_lowercase();
            if brand_lower.contains("pentium") {
                return (HardwareFamily::X86, HardwareArch::Pentium4);
            } else if brand_lower.contains("core") && brand_lower.contains("2") {
                return (HardwareFamily::X86, HardwareArch::Core2);
            }
        }
    }
    (HardwareFamily::X86, HardwareArch::Unknown)
}

/// Detect x86_64 architecture variant
fn detect_x86_64_arch() -> (HardwareFamily, HardwareArch) {
    #[cfg(any(target_arch = "x86", target_arch = "x86_64"))]
    {
        if let Some(brand) = get_cpu_brand() {
            let brand_lower = brand.to_lowercase();
            
            // AMD detection
            if brand_lower.contains("ryzen") {
                return (HardwareFamily::X86_64, HardwareArch::Ryzen);
            }
            
            // Intel detection
            if brand_lower.contains("skylake") || brand_lower.contains("i9-9") || brand_lower.contains("i7-9") {
                return (HardwareFamily::X86_64, HardwareArch::Skylake);
            } else if brand_lower.contains("haswell") || brand_lower.contains("i7-4") || brand_lower.contains("i5-4") {
                return (HardwareFamily::X86_64, HardwareArch::Haswell);
            } else if brand_lower.contains("sandy") || brand_lower.contains("i7-2") || brand_lower.contains("i5-2") {
                return (HardwareFamily::X86_64, HardwareArch::SandyBridge);
            } else if brand_lower.contains("nehalem") || brand_lower.contains("i7-9") {
                return (HardwareFamily::X86_64, HardwareArch::Nehalem);
            }
        }
    }
    (HardwareFamily::X86_64, HardwareArch::Unknown)
}

/// Detect ARM64 architecture variant (Apple Silicon)
fn detect_arm64_arch() -> (HardwareFamily, HardwareArch) {
    #[cfg(target_os = "macos")]
    {
        // Check for Apple Silicon using sysctl
        if let Ok(output) = std::process::Command::new("sysctl")
            .arg("-n")
            .arg("machdep.cpu.brand_string")
            .output()
        {
            if let Ok(brand) = String::from_utf8(output.stdout) {
                let brand_lower = brand.to_lowercase();
                if brand_lower.contains("m3") {
                    return (HardwareFamily::ARM64, HardwareArch::M3);
                } else if brand_lower.contains("m2") {
                    return (HardwareFamily::ARM64, HardwareArch::M2);
                } else if brand_lower.contains("m1") {
                    return (HardwareFamily::ARM64, HardwareArch::M1);
                }
            }
        }
    }
    (HardwareFamily::ARM64, HardwareArch::CortexA)
}

/// Detect PowerPC architecture variant
fn detect_powerpc_arch() -> (HardwareFamily, HardwareArch) {
    #[cfg(any(target_arch = "powerpc", target_arch = "powerpc64"))]
    {
        if let Some(brand) = get_cpu_brand() {
            let brand_lower = brand.to_lowercase();
            if brand_lower.contains("g5") || brand_lower.contains("powerpc g5") {
                return (HardwareFamily::PowerPC, HardwareArch::G5);
            } else if brand_lower.contains("g4") || brand_lower.contains("powerpc g4") {
                return (HardwareFamily::PowerPC, HardwareArch::G4);
            } else if brand_lower.contains("g3") || brand_lower.contains("powerpc g3") {
                return (HardwareFamily::PowerPC, HardwareArch::G3);
            }
        }
        
        // Check for 64-bit PowerPC
        #[cfg(target_arch = "powerpc64")]
        {
            return (HardwareFamily::PowerPC, HardwareArch::Ppc64);
        }
    }
    (HardwareFamily::PowerPC, HardwareArch::Unknown)
}

/// Get CPU brand string
fn get_cpu_brand() -> Option<String> {
    let mut sys = System::new();
    sys.refresh_cpu();
    let cpu = sys.global_cpu_info();
    let brand = cpu.name().trim().to_string();
    if brand.is_empty() {
        None
    } else {
        Some(brand)
    }
}

/// Get OS version string
fn get_os_version() -> String {
    #[cfg(target_os = "linux")]
    {
        // Try to read /etc/os-release
        if let Ok(content) = std::fs::read_to_string("/etc/os-release") {
            for line in content.lines() {
                if line.starts_with("PRETTY_NAME=") {
                    return line.trim_start_matches("PRETTY_NAME=").trim_matches('"').to_string();
                }
            }
        }
        format!("Linux {}", std::env::consts::ARCH)
    }

    #[cfg(target_os = "macos")]
    {
        if let Ok(output) = std::process::Command::new("sw_vers")
            .args(["-productVersion"])
            .output()
        {
            if let Ok(version) = String::from_utf8(output.stdout) {
                return format!("macOS {}", version.trim());
            }
        }
        format!("macOS {}", std::env::consts::ARCH)
    }

    #[cfg(target_os = "windows")]
    {
        format!("Windows {}", std::env::consts::ARCH)
    }

    #[cfg(not(any(target_os = "linux", target_os = "macos", target_os = "windows")))]
    {
        format!("{} {}", std::env::consts::OS, std::env::consts::ARCH)
    }
}

/// Get hardware serial number (platform-specific)
fn get_hardware_serial() -> Option<String> {
    #[cfg(target_os = "linux")]
    {
        // Try various sources for serial
        let serial_sources = [
            "/sys/class/dmi/id/product_serial",
            "/sys/class/dmi/id/board_serial",
            "/sys/class/dmi/id/chassis_serial",
        ];
        
        for path in &serial_sources {
            if let Ok(serial) = std::fs::read_to_string(path) {
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
        if let Ok(machine_id) = std::fs::read_to_string("/etc/machine-id") {
            return Some(machine_id.trim().chars().take(16).collect());
        }
    }

    #[cfg(target_os = "macos")]
    {
        if let Ok(output) = std::process::Command::new("system_profiler")
            .args(["SPHardwareDataType", "-json"])
            .output()
        {
            if let Ok(json_str) = String::from_utf8(output.stdout) {
                if let Ok(json) = serde_json::from_str::<serde_json::Value>(&json_str) {
                    if let Some(serial) = json
                        .get("SPHardwareDataType")
                        .and_then(|arr| arr.as_array())
                        .and_then(|arr| arr.first())
                        .and_then(|item| item.get("serial_number"))
                        .and_then(|s| s.as_str())
                    {
                        return Some(serial.to_string());
                    }
                }
            }
        }
    }

    #[cfg(target_os = "windows")]
    {
        if let Ok(output) = std::process::Command::new("wmic")
            .args(["bios", "get", "serialnumber"])
            .output()
        {
            if let Ok(serial) = String::from_utf8(output.stdout) {
                let serial = serial.lines()
                    .skip(1) // Skip header
                    .next()
                    .unwrap_or("")
                    .trim()
                    .to_string();
                if !serial.is_empty() && serial != "Default String" {
                    return Some(serial);
                }
            }
        }
    }

    None
}

/// Generate a unique miner identifier from hardware info
pub fn generate_miner_id(hw: &HardwareInfo) -> String {
    use sha2::{Sha256, Digest};
    
    let mut hasher = Sha256::new();
    hasher.update(hw.model.as_bytes());
    hasher.update(hw.serial.as_deref().unwrap_or(""));
    hasher.update(hw.platform.as_bytes());
    
    let hash = hasher.finalize();
    format!("RTC_{}", hex::encode(&hash[..8]))
}

/// Validate hardware info (placeholder for phase-2 fingerprint checks)
pub fn validate_hardware(_hw: &HardwareInfo) -> Result<bool> {
    // Phase-1: Basic validation only
    // Phase-2: Will add 6 RIP-PoA fingerprint checks:
    // 1. Clock-Skew & Oscillator Drift
    // 2. Cache Timing Fingerprint
    // 3. SIMD Unit Identity
    // 4. Thermal Drift Entropy
    // 5. Instruction Path Jitter
    // 6. Anti-Emulation Checks
    
    Ok(true)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_detect_hardware() {
        let hw = detect_hardware().expect("Failed to detect hardware");
        assert!(!hw.model.is_empty());
        assert!(hw.cores > 0);
        assert!(hw.total_ram_bytes > 0);
        assert!(!hw.platform.is_empty());
    }

    #[test]
    fn test_generate_miner_id() {
        let hw = HardwareInfo {
            model: "Test CPU".to_string(),
            serial: Some("TEST123".to_string()),
            platform: "linux".to_string(),
            ..Default::default()
        };
        let id = generate_miner_id(&hw);
        assert!(id.starts_with("RTC_"));
        // "RTC_" (4) + 16 hex chars = 20
        assert_eq!(id.len(), 20);
    }
}
