// SPDX-License-Identifier: Apache-2.0
use sysinfo::System;

/// Get the CPU brand/model string.
pub fn get_cpu_model() -> String {
    let sys = System::new_all();
    sys.cpus()
        .first()
        .map(|cpu| cpu.brand().trim().to_string())
        .unwrap_or_else(|| "Unknown CPU".to_string())
}

/// Get the number of physical CPU cores.
pub fn get_cpu_cores() -> usize {
    let sys = System::new_all();
    sys.physical_core_count().unwrap_or(1)
}

/// Attempt to read a hardware serial / CPU ID.
///
/// On Linux, tries `/proc/cpuinfo` for a `Serial` or `physical id` field.
/// On Windows, falls back to the processor brand hash.
/// On macOS, tries `ioreg`.
pub fn get_cpu_serial() -> String {
    #[cfg(target_os = "linux")]
    {
        if let Ok(contents) = std::fs::read_to_string("/proc/cpuinfo") {
            // Look for Serial line (common on ARM/PPC/RISC-V StarFive)
            for line in contents.lines() {
                let lower = line.to_lowercase();
                if lower.starts_with("serial") {
                    if let Some(val) = line.split(':').nth(1) {
                        let serial = val.trim().to_string();
                        if !serial.is_empty() {
                            return serial;
                        }
                    }
                }
            }
            // Fallback: first physical id
            for line in contents.lines() {
                if line.starts_with("physical id") {
                    if let Some(val) = line.split(':').nth(1) {
                        return format!("phys-{}", val.trim());
                    }
                }
            }
            // RISC-V: extract mhartid (hardware thread ID) as serial proxy
            for line in contents.lines() {
                let lower = line.to_lowercase();
                if lower.starts_with("hart") || lower.starts_with("mhartid") {
                    if let Some(val) = line.split(':').nth(1) {
                        let hart = val.trim().to_string();
                        if !hart.is_empty() && hart != "0" {
                            return format!("riscv-hart-{}", hart);
                        }
                    }
                }
            }
        }
    }

    #[cfg(target_os = "windows")]
    {
        // Use the PROCESSOR_IDENTIFIER env var as a rough fingerprint
        if let Ok(id) = std::env::var("PROCESSOR_IDENTIFIER") {
            return id;
        }
    }

    #[cfg(target_os = "macos")]
    {
        if let Ok(output) = std::process::Command::new("ioreg")
            .args(["-rd1", "-c", "IOPlatformExpertDevice"])
            .output()
        {
            let stdout = String::from_utf8_lossy(&output.stdout);
            for line in stdout.lines() {
                if line.contains("IOPlatformSerialNumber") {
                    if let Some(val) = line.split('"').nth(3) {
                        return val.to_string();
                    }
                }
            }
        }
    }

    // Ultimate fallback: hash the brand string
    let model = get_cpu_model();
    use sha2::{Digest, Sha256};
    let hash = Sha256::digest(model.as_bytes());
    hex::encode(&hash[..8])
}
