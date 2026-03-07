// Check 6: Anti-Emulation Behavioral Checks
// ==========================================
// Detects VMs, hypervisors, and cloud provider environments.
// Comprehensive detection for traditional hypervisors and cloud metadata.

use crate::CheckResult;
use serde_json::json;
#[cfg(target_os = "linux")]
use std::fs;
use std::process::Command;

/// VM and cloud provider strings to detect
const VM_STRINGS: &[&str] = &[
    // Traditional hypervisors
    "vmware", "virtualbox", "kvm", "qemu", "xen",
    "hyperv", "hyper-v", "parallels", "bhyve",
    // AWS EC2
    "amazon", "amazon ec2", "ec2", "nitro",
    // Google Cloud
    "google", "google compute engine", "gce",
    // Microsoft Azure
    "microsoft corporation", "azure",
    // DigitalOcean
    "digitalocean",
    // Linode/Akamai
    "linode", "akamai",
    // Vultr
    "vultr",
    // Hetzner
    "hetzner",
    // Oracle Cloud
    "oracle", "oraclecloud",
    // OVH
    "ovh", "ovhcloud",
    // Alibaba Cloud
    "alibaba", "alicloud",
    // Generic VM indicators
    "bochs", "innotek", "seabios",
];

/// DMI paths to check for VM indicators
#[cfg(target_os = "linux")]
const DMI_PATHS: &[&str] = &[
    "/sys/class/dmi/id/product_name",
    "/sys/class/dmi/id/sys_vendor",
    "/sys/class/dmi/id/board_vendor",
    "/sys/class/dmi/id/board_name",
    "/sys/class/dmi/id/bios_vendor",
    "/sys/class/dmi/id/chassis_vendor",
    "/sys/class/dmi/id/chassis_asset_tag",
];

/// Environment variables that indicate container/VM
const VM_ENV_VARS: &[&str] = &[
    "KUBERNETES", "DOCKER", "VIRTUAL", "container",
    "AWS_EXECUTION_ENV", "ECS_CONTAINER_METADATA_URI",
    "GOOGLE_CLOUD_PROJECT", "AZURE_FUNCTIONS_ENVIRONMENT",
    "WEBSITE_INSTANCE_ID",
];

/// Cloud metadata endpoint
#[cfg(feature = "full")]
const CLOUD_METADATA_URL: &str = "http://169.254.169.254/";

pub struct AntiEmulationCheck;

impl AntiEmulationCheck {
    pub fn run() -> CheckResult {
        let mut vm_indicators: Vec<String> = Vec::new();

        // Check DMI paths (Linux)
        #[cfg(target_os = "linux")]
        {
            for path in DMI_PATHS {
                if let Ok(content) = fs::read_to_string(path) {
                    let content_lower = content.to_lowercase();
                    for vm_string in VM_STRINGS {
                        if content_lower.contains(vm_string) {
                            vm_indicators.push(format!("{}:{}", path, vm_string));
                        }
                    }
                }
            }

            // Check /proc/cpuinfo for hypervisor flag
            if let Ok(cpuinfo) = fs::read_to_string("/proc/cpuinfo") {
                if cpuinfo.to_lowercase().contains("hypervisor") {
                    vm_indicators.push("cpuinfo:hypervisor".to_string());
                }
            }

            // Check /sys/hypervisor (Xen)
            if let Ok(hv_type) = fs::read_to_string("/sys/hypervisor/type") {
                if !hv_type.trim().is_empty() {
                    vm_indicators.push(format!("sys_hypervisor:{}", hv_type.trim()));
                }
            }

            // Check systemd-detect-virt
            if let Ok(output) = Command::new("systemd-detect-virt").output() {
                if output.status.success() {
                    let virt_type = String::from_utf8_lossy(&output.stdout).trim().to_lowercase();
                    if !virt_type.is_empty() && virt_type != "none" {
                        vm_indicators.push(format!("systemd_detect_virt:{}", virt_type));
                    }
                }
            }
        }

        // Check environment variables
        for key in VM_ENV_VARS {
            if std::env::var(key).is_ok() {
                vm_indicators.push(format!("env:{}", key));
            }
        }

        // Check cloud metadata endpoint (with timeout)
        #[cfg(feature = "full")]
        {
            use std::time::Duration;
            
            // Try IMDSv2 token (AWS)
            if let Ok(client) = reqwest::blocking::ClientBuilder::new()
                .timeout(Duration::from_secs(1))
                .build()
            {
                let token_req = client.put(format!("{}latest/api/token", CLOUD_METADATA_URL))
                    .header("X-aws-ec2-metadata-token-ttl-seconds", "5")
                    .send();
                
                if token_req.is_ok() {
                    vm_indicators.push("cloud_metadata:aws_imdsv2".to_string());
                } else {
                    // Try regular metadata request
                    let meta_req = client.get(CLOUD_METADATA_URL)
                        .header("Metadata", "true")
                        .send();
                    
                    if let Ok(resp) = meta_req {
                        if let Ok(body) = resp.text() {
                            let body_lower = body.to_lowercase();
                            let provider = if body_lower.contains("azure") || body_lower.contains("microsoft") {
                                "azure"
                            } else if body_lower.contains("latest") || body_lower.contains("meta-data") {
                                "aws_or_gcp"
                            } else {
                                "unknown_cloud"
                            };
                            vm_indicators.push(format!("cloud_metadata:{}", provider));
                        }
                    }
                }
            }
        }

        // macOS: Check for VM-specific hardware
        #[cfg(target_os = "macos")]
        {
            if let Ok(output) = Command::new("sysctl").args(&["-a"]).output() {
                let output = String::from_utf8_lossy(&output.stdout);
                let output_lower = output.to_lowercase();
                
                for vm_string in VM_STRINGS {
                    if output_lower.contains(vm_string) {
                        vm_indicators.push(format!("sysctl:{}", vm_string));
                    }
                }
            }
        }

        let indicator_count = vm_indicators.len();
        let is_likely_vm = indicator_count > 0;

        let data = json!({
            "vm_indicators": vm_indicators,
            "indicator_count": indicator_count,
            "is_likely_vm": is_likely_vm,
        });

        // Validation: bare metal should have no VM indicators
        let passed = !is_likely_vm;
        let fail_reason = if is_likely_vm {
            Some("vm_detected".to_string())
        } else {
            None
        };

        CheckResult {
            name: "anti_emulation".to_string(),
            passed,
            data,
            fail_reason,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_anti_emulation_check() {
        let result = AntiEmulationCheck::run();
        assert_eq!(result.name, "anti_emulation");
        assert!(result.data.get("indicator_count").is_some());
        // Note: Will fail in VM environments, which is expected
    }

    #[test]
    fn test_vm_strings_coverage() {
        // Verify we have VM strings defined
        assert!(!VM_STRINGS.is_empty());
        assert!(VM_STRINGS.len() >= 20);
    }

    #[test]
    fn test_dmi_paths_coverage() {
        // Verify we have DMI paths defined (Linux only)
        #[cfg(target_os = "linux")]
        {
            assert!(!DMI_PATHS.is_empty());
        }
    }
}
