//! Hardware information collection

use serde::{Deserialize, Serialize};
use sysinfo::System;

/// Hardware information for attestation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HardwareInfo {
    /// Platform (Linux, macOS, Windows)
    pub platform: String,

    /// Machine architecture (x86_64, arm64, etc.)
    pub machine: String,

    /// Hostname
    pub hostname: String,

    /// CPU family (x86, Apple Silicon, PowerPC, etc.)
    pub family: String,

    /// CPU architecture (modern, M1, M2, G4, G5, etc.)
    pub arch: String,

    /// CPU model name
    pub cpu: String,

    /// Number of CPU cores
    pub cores: usize,

    /// Total memory in GB
    pub memory_gb: u64,

    /// Hardware serial number (if available)
    pub serial: Option<String>,

    /// MAC addresses
    pub macs: Vec<String>,

    /// Primary MAC address
    pub mac: String,
}

impl HardwareInfo {
    /// Collect hardware information from the system
    pub fn collect() -> crate::Result<Self> {
        let mut sys = System::new_all();
        sys.refresh_all();

        // Get platform info
        let platform = std::env::consts::OS.to_string();
        let machine = std::env::consts::ARCH.to_string();
        let hostname = hostname::get()
            .map(|h| h.to_string_lossy().to_string())
            .unwrap_or_else(|_| "unknown".to_string());

        // Get CPU info
        let cpu_info = sys.global_cpu_info();
        let cpu = cpu_info.name().to_string();
        let cores = sys.cpus().len();

        // Get memory info
        let memory_gb = sys.total_memory() / (1024 * 1024 * 1024);

        // Detect CPU family and architecture
        let (family, arch) = detect_cpu_family_arch(&cpu, &machine);

        // Get serial number (platform-specific)
        let serial = get_hardware_serial();

        // Get MAC addresses
        let macs = get_mac_addresses();
        let mac = macs
            .first()
            .cloned()
            .unwrap_or_else(|| "00:00:00:00:00:00".to_string());

        Ok(Self {
            platform,
            machine,
            hostname,
            family,
            arch,
            cpu,
            cores,
            memory_gb,
            serial,
            macs,
            mac,
        })
    }

    /// Generate a miner ID from hardware info
    pub fn generate_miner_id(&self) -> String {
        use sha2::{Digest, Sha256};

        let hw_string = format!(
            "{}-{}",
            self.hostname,
            self.serial.as_deref().unwrap_or("unknown")
        );
        let hash = Sha256::digest(hw_string.as_bytes());
        let hw_hash = hex::encode(&hash[..4]);

        format!(
            "{}-{}-{}",
            self.arch.to_lowercase().replace(' ', "_"),
            &self.hostname[..self.hostname.len().min(10)],
            hw_hash
        )
    }

    /// Generate a wallet address from miner ID
    pub fn generate_wallet(&self, miner_id: &str) -> String {
        use sha2::{Digest, Sha256};

        let wallet_string = format!("{}-rustchain", miner_id);
        let hash = Sha256::digest(wallet_string.as_bytes());
        let wallet_hash = hex::encode(&hash[..19]);

        format!(
            "{}_{}RTC",
            self.family.to_lowercase().replace(' ', "_"),
            wallet_hash
        )
    }
}

/// Detect CPU family and architecture from CPU brand string
fn detect_cpu_family_arch(cpu: &str, machine: &str) -> (String, String) {
    let cpu_lower = cpu.to_lowercase();

    // RISC-V (2010+) - Open ISA, emerging vintage hardware
    if machine.contains("riscv") || machine.contains("risc-v") {
        // Detect specific RISC-V implementations
        if cpu_lower.contains("sifive") {
            if cpu_lower.contains("u74") {
                return ("RISC-V".to_string(), "SiFive U74".to_string());
            } else if cpu_lower.contains("u54") {
                return ("RISC-V".to_string(), "SiFive U54".to_string());
            } else if cpu_lower.contains("e51") {
                return ("RISC-V".to_string(), "SiFive E51".to_string());
            }
            return ("RISC-V".to_string(), "SiFive".to_string());
        } else if cpu_lower.contains("starfive") {
            if cpu_lower.contains("jh7110") {
                return ("RISC-V".to_string(), "StarFive JH7110".to_string());
            } else if cpu_lower.contains("jh7100") {
                return ("RISC-V".to_string(), "StarFive JH7100".to_string());
            }
            return ("RISC-V".to_string(), "StarFive".to_string());
        } else if cpu_lower.contains("visionfive") {
            return ("RISC-V".to_string(), "VisionFive".to_string());
        } else if cpu_lower.contains("hifive") {
            return ("RISC-V".to_string(), "HiFive".to_string());
        } else if cpu_lower.contains("kendryte") {
            return ("RISC-V".to_string(), "Kendryte".to_string());
        } else if cpu_lower.contains("allwinner") {
            if cpu_lower.contains("d1") || cpu_lower.contains("sunxi") {
                return ("RISC-V".to_string(), "Allwinner D1".to_string());
            }
            return ("RISC-V".to_string(), "Allwinner".to_string());
        } else if cpu_lower.contains("thead") {
            if cpu_lower.contains("c910") || cpu_lower.contains("c906") {
                return ("RISC-V".to_string(), "T-Head C910/C906".to_string());
            }
            return ("RISC-V".to_string(), "T-Head".to_string());
        } else if machine.contains("64") {
            return ("RISC-V".to_string(), "RISC-V 64-bit".to_string());
        } else if machine.contains("32") {
            return ("RISC-V".to_string(), "RISC-V 32-bit".to_string());
        }
        return ("RISC-V".to_string(), "Generic".to_string());
    }

    // Apple Silicon (M1/M2/M3/M4)
    if machine == "aarch64" || machine == "arm64" {
        if cpu_lower.contains("m4") {
            return ("Apple Silicon".to_string(), "M4".to_string());
        } else if cpu_lower.contains("m3") {
            return ("Apple Silicon".to_string(), "M3".to_string());
        } else if cpu_lower.contains("m2") {
            return ("Apple Silicon".to_string(), "M2".to_string());
        } else if cpu_lower.contains("m1") {
            return ("Apple Silicon".to_string(), "M1".to_string());
        }
        return ("Apple Silicon".to_string(), "apple_silicon".to_string());
    }

    // x86_64
    if machine == "x86_64" {
        if cpu_lower.contains("core 2") || cpu_lower.contains("core(tm)2") {
            return ("x86_64".to_string(), "core2".to_string());
        } else if cpu_lower.contains("xeon") {
            if cpu_lower.contains("e5-16") || cpu_lower.contains("e5-26") {
                return ("x86_64".to_string(), "ivy_bridge".to_string());
            }
            return ("x86_64".to_string(), "xeon".to_string());
        } else if cpu_lower.contains("i7-3")
            || cpu_lower.contains("i5-3")
            || cpu_lower.contains("i3-3")
        {
            return ("x86_64".to_string(), "ivy_bridge".to_string());
        } else if cpu_lower.contains("i7-2")
            || cpu_lower.contains("i5-2")
            || cpu_lower.contains("i3-2")
        {
            return ("x86_64".to_string(), "sandy_bridge".to_string());
        } else if cpu_lower.contains("i7-9") && cpu_lower.contains("900") {
            return ("x86_64".to_string(), "nehalem".to_string());
        } else if cpu_lower.contains("i7-4") || cpu_lower.contains("i5-4") {
            return ("x86_64".to_string(), "haswell".to_string());
        } else if cpu_lower.contains("pentium") {
            return ("x86_64".to_string(), "pentium4".to_string());
        }
        return ("x86_64".to_string(), "modern".to_string());
    }

    // PowerPC (legacy Macs)
    if machine.contains("ppc") || machine.contains("powerpc") {
        if cpu_lower.contains("g5") {
            return ("PowerPC".to_string(), "G5".to_string());
        } else if cpu_lower.contains("g4") || cpu_lower.contains("powerbook") {
            return ("PowerPC".to_string(), "G4".to_string());
        } else if cpu_lower.contains("g3") {
            return ("PowerPC".to_string(), "G3".to_string());
        }
        return ("PowerPC".to_string(), "G4".to_string());
    }

    // ARM (generic, non-Apple)
    if machine.contains("arm") || machine.contains("aarch") {
        if cpu_lower.contains("cortex-a72") {
            return ("ARM".to_string(), "Cortex-A72".to_string());
        } else if cpu_lower.contains("cortex-a53") {
            return ("ARM".to_string(), "Cortex-A53".to_string());
        } else if cpu_lower.contains("cortex-a76") {
            return ("ARM".to_string(), "Cortex-A76".to_string());
        } else if cpu_lower.contains("neoverse") {
            return ("ARM".to_string(), "Neoverse".to_string());
        }
        return ("ARM".to_string(), "Generic ARM".to_string());
    }

    // Default
    ("unknown".to_string(), "unknown".to_string())
}

/// Get hardware serial number (platform-specific)
#[cfg(target_os = "macos")]
fn get_hardware_serial() -> Option<String> {
    use std::process::Command;

    // Try system_profiler first
    if let Ok(output) = Command::new("system_profiler")
        .arg("SPHardwareDataType")
        .output()
    {
        let stdout = String::from_utf8_lossy(&output.stdout);
        for line in stdout.lines() {
            if line.contains("Serial Number") {
                if let Some(parts) = line.split(':').nth(1) {
                    return Some(parts.trim().to_string());
                }
            }
        }
    }

    // Fallback to ioreg
    if let Ok(output) = Command::new("ioreg").arg("-l").output() {
        let stdout = String::from_utf8_lossy(&output.stdout);
        for line in stdout.lines() {
            if line.contains("IOPlatformSerialNumber") {
                let parts: Vec<&str> = line.split('"').collect();
                if parts.len() >= 2 {
                    return Some(parts[parts.len() - 2].to_string());
                }
            }
        }
    }

    None
}

#[cfg(target_os = "linux")]
fn get_hardware_serial() -> Option<String> {
    use std::fs;

    // Try various DMI sources
    let serial_sources = [
        "/sys/class/dmi/id/product_serial",
        "/sys/class/dmi/id/board_serial",
        "/sys/class/dmi/id/chassis_serial",
    ];

    for path in &serial_sources {
        if let Ok(serial) = fs::read_to_string(path) {
            let serial = serial.trim();
            if !serial.is_empty()
                && serial != "None"
                && serial != "To Be Filled By O.E.M."
                && serial != "Default string"
            {
                return Some(serial.to_string());
            }
        }
    }

    // Fallback to machine-id
    if let Ok(machine_id) = fs::read_to_string("/etc/machine-id") {
        return Some(machine_id.trim().chars().take(16).collect());
    }

    None
}

#[cfg(target_os = "windows")]
fn get_hardware_serial() -> Option<String> {
    use std::process::Command;

    if let Ok(output) = Command::new("wmic")
        .args(&["bios", "get", "serialnumber"])
        .output()
    {
        let stdout = String::from_utf8_lossy(&output.stdout);
        let lines: Vec<&str> = stdout.lines().collect();
        if lines.len() >= 2 {
            let serial = lines[1].trim();
            if !serial.is_empty() && serial != "To Be Filled By O.E.M." {
                return Some(serial.to_string());
            }
        }
    }

    None
}

/// Get MAC addresses (platform-agnostic using sysinfo)
fn get_mac_addresses() -> Vec<String> {
    // Use network_interfaces crate or fallback
    // For now, use a simple approach with sysinfo network interfaces
    let mut macs = Vec::new();

    #[cfg(target_os = "linux")]
    {
        if let Ok(output) = std::process::Command::new("ip")
            .args(&["-o", "link"])
            .output()
        {
            let stdout = String::from_utf8_lossy(&output.stdout);
            for line in stdout.lines() {
                if let Some(start) = line.find("link/ether") {
                    let rest = &line[start + 10..];
                    if let Some(end) = rest.find(' ') {
                        let mac = rest[..end].to_lowercase();
                        if mac != "00:00:00:00:00:00" {
                            macs.push(mac);
                        }
                    }
                }
            }
        }
    }

    #[cfg(target_os = "macos")]
    {
        if let Ok(output) = std::process::Command::new("ifconfig").output() {
            let stdout = String::from_utf8_lossy(&output.stdout);
            for line in stdout.lines() {
                if line.contains("ether") {
                    let parts: Vec<&str> = line.split_whitespace().collect();
                    if parts.len() >= 2 {
                        let mac = parts[1].to_lowercase();
                        if mac != "00:00:00:00:00:00" {
                            macs.push(mac);
                        }
                    }
                }
            }
        }
    }

    #[cfg(target_os = "windows")]
    {
        if let Ok(output) = std::process::Command::new("ipconfig")
            .args(&["/all"])
            .output()
        {
            let stdout = String::from_utf8_lossy(&output.stdout);
            for line in stdout.lines() {
                if line.contains("Physical Address") {
                    let parts: Vec<&str> = line.split(':').collect();
                    if parts.len() >= 2 {
                        let mac = parts[1].trim().replace('-', ":").to_lowercase();
                        if !mac.is_empty() && mac != "00:00:00:00:00:00" {
                            macs.push(mac);
                        }
                    }
                }
            }
        }
    }

    if macs.is_empty() {
        macs.push("00:00:00:00:00:01".to_string());
    }

    macs
}

// Need hostname crate
fn _hostname_fallback() -> String {
    "unknown".to_string()
}
