// SPDX-License-Identifier: Apache-2.0
//! Check 6: Anti-Emulation / VM Detection
//!
//! Multi-layered detection of virtual machines, hypervisors, and emulators.
//! Scans system files, CPUID flags, MAC address OUIs, and timing uniformity
//! to determine if the host is real hardware.

use super::CheckResult;

/// Known virtual NIC MAC address OUI prefixes.
const VM_MAC_OUIS: &[&str] = &[
    "00:05:69", // VMware
    "00:0c:29", // VMware
    "00:1c:14", // VMware
    "00:50:56", // VMware
    "08:00:27", // VirtualBox
    "0a:00:27", // VirtualBox
    "52:54:00", // QEMU/KVM
    "00:16:3e", // Xen
    "00:15:5d", // Hyper-V
];

/// Known VM vendor strings in DMI/SMBIOS data.
const VM_VENDORS: &[&str] = &[
    "qemu",
    "vmware",
    "virtualbox",
    "innotek",
    "xen",
    "kvm",
    "microsoft corporation", // Hyper-V
    "parallels",
    "bochs",
];

/// Additional RISC-V specific VM indicators (QEMU for RISC-V is common).
const RISCV_VM_INDICATORS: &[&str] = &[
    "qemu-riscv",
    "riscv,qemu",
    "virt, qemu",
    "riscv-virtio",
];

/// Known virtual disk identifiers in SCSI info.
#[allow(dead_code)]
const VIRTUAL_SCSI: &[&str] = &[
    "vbox",
    "vmware",
    "qemu",
    "virtual",
    "virtio",
];

/// Check a file's contents for any of the given patterns (case-insensitive).
#[allow(dead_code)]
fn file_contains_any(path: &str, patterns: &[&str]) -> Vec<String> {
    let mut found = Vec::new();
    if let Ok(contents) = std::fs::read_to_string(path) {
        let lower = contents.to_lowercase();
        for &pattern in patterns {
            if lower.contains(pattern) {
                found.push(format!("{}:{}", path, pattern));
            }
        }
    }
    found
}

/// Check MAC addresses against known virtual NIC OUIs.
fn check_mac_ouis() -> Vec<String> {
    let mut indicators = Vec::new();

    let macs = crate::hardware::system::get_mac_addresses();
    for mac in &macs {
        let mac_lower = mac.to_lowercase();
        // Normalize separators: accept both ':' and '-'
        let normalized: String = mac_lower.chars().map(|c| if c == '-' { ':' } else { c }).collect();
        for &oui in VM_MAC_OUIS {
            if normalized.starts_with(oui) {
                indicators.push(format!("vm_mac:{}", mac));
            }
        }
    }

    indicators
}

/// Run platform-specific VM detection.
fn detect_vm_indicators() -> Vec<String> {
    let mut indicators = Vec::new();

    // --- Linux-specific checks ---
    #[cfg(target_os = "linux")]
    {
        // DMI sys_vendor
        indicators.extend(file_contains_any(
            "/sys/class/dmi/id/sys_vendor",
            VM_VENDORS,
        ));

        // DMI product_name
        indicators.extend(file_contains_any(
            "/sys/class/dmi/id/product_name",
            VM_VENDORS,
        ));

        // DMI board_vendor
        indicators.extend(file_contains_any(
            "/sys/class/dmi/id/board_vendor",
            VM_VENDORS,
        ));

        // Hypervisor flag in /proc/cpuinfo
        if let Ok(cpuinfo) = std::fs::read_to_string("/proc/cpuinfo") {
            let lower = cpuinfo.to_lowercase();
            if lower.contains("hypervisor") {
                indicators.push("cpuinfo:hypervisor_flag".to_string());
            }
            // RISC-V QEMU detection via cpuinfo model name
            for pattern in RISCV_VM_INDICATORS {
                if lower.contains(pattern) {
                    indicators.push(format!("riscv_vm:{}", pattern));
                }
            }
        }

        // Virtual SCSI devices
        indicators.extend(file_contains_any(
            "/proc/scsi/scsi",
            VIRTUAL_SCSI,
        ));

        // Check for /.dockerenv (container)
        if std::path::Path::new("/.dockerenv").exists() {
            indicators.push("container:docker".to_string());
        }

        // Check cgroup for container hints
        if let Ok(cgroup) = std::fs::read_to_string("/proc/1/cgroup") {
            let lower = cgroup.to_lowercase();
            if lower.contains("docker") || lower.contains("lxc") || lower.contains("kubepods") {
                indicators.push("container:cgroup".to_string());
            }
        }

        // RISC-V: check /proc/device-tree/compatible for QEMU
        if let Ok(contents) = std::fs::read_to_string("/proc/device-tree/compatible") {
            let lower = contents.to_lowercase();
            for pattern in RISCV_VM_INDICATORS {
                if lower.contains(pattern) {
                    indicators.push(format!("device_tree:{}", pattern));
                }
            }
        }
    }

    // --- Windows-specific checks ---
    #[cfg(target_os = "windows")]
    {
        // Check SystemManufacturer via environment or registry heuristics
        if let Ok(output) = std::process::Command::new("wmic")
            .args(["computersystem", "get", "manufacturer"])
            .output()
        {
            let stdout = String::from_utf8_lossy(&output.stdout).to_lowercase();
            for &vendor in VM_VENDORS {
                if stdout.contains(vendor) {
                    indicators.push(format!("wmic_manufacturer:{}", vendor));
                }
            }
        }

        // Check model
        if let Ok(output) = std::process::Command::new("wmic")
            .args(["computersystem", "get", "model"])
            .output()
        {
            let stdout = String::from_utf8_lossy(&output.stdout).to_lowercase();
            for &vendor in VM_VENDORS {
                if stdout.contains(vendor) {
                    indicators.push(format!("wmic_model:{}", vendor));
                }
            }
        }
    }

    // --- macOS-specific checks ---
    #[cfg(target_os = "macos")]
    {
        if let Ok(output) = std::process::Command::new("sysctl")
            .args(["-n", "machdep.cpu.features"])
            .output()
        {
            let stdout = String::from_utf8_lossy(&output.stdout).to_lowercase();
            if stdout.contains("vmm") {
                indicators.push("sysctl:vmm_flag".to_string());
            }
        }
    }

    // --- Cross-platform MAC check ---
    indicators.extend(check_mac_ouis());

    indicators
}

/// Run the anti-emulation fingerprint check.
pub fn run() -> CheckResult {
    let vm_indicators = detect_vm_indicators();
    let passed = vm_indicators.is_empty();

    if !passed {
        log::warn!("VM/emulation indicators detected: {:?}", vm_indicators);
    } else {
        log::debug!("Anti-emulation: no VM indicators found");
    }

    CheckResult {
        passed,
        data: serde_json::json!({
            "vm_indicators": vm_indicators,
            "checks_performed": {
                "dmi_vendor": cfg!(target_os = "linux"),
                "cpuinfo_hypervisor": cfg!(target_os = "linux"),
                "riscv_vm_detection": cfg!(target_os = "linux"),
                "scsi_virtual": cfg!(target_os = "linux"),
                "mac_oui": true,
                "container_detection": cfg!(target_os = "linux"),
            },
        }),
    }
}
