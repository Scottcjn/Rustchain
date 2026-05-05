// SPDX-License-Identifier: Apache-2.0
pub mod cpu;
pub mod arch;
pub mod system;

use serde::Serialize;

/// Complete hardware information for attestation payload.
#[derive(Debug, Clone, Serialize)]
pub struct HardwareInfo {
    pub cpu_model: String,
    pub cpu_cores: usize,
    pub ram_gb: u64,
    pub os: String,
    pub device_family: String,
    pub device_arch: String,
    pub device_model: String,
    pub macs: Vec<String>,
    pub uptime: u64,
    pub cpu_serial: String,
}

/// Collect all hardware information.
pub fn detect() -> HardwareInfo {
    let cpu_model = cpu::get_cpu_model();
    let cpu_cores = cpu::get_cpu_cores();
    let ram_gb = system::get_ram_gb();
    let os = system::get_os_string();
    let (device_family, device_arch) = arch::classify(&cpu_model);
    let macs = system::get_mac_addresses();
    let uptime = system::get_uptime_secs();
    let cpu_serial = cpu::get_cpu_serial();

    HardwareInfo {
        cpu_model: cpu_model.clone(),
        cpu_cores,
        ram_gb,
        os,
        device_family: device_family.to_string(),
        device_arch: device_arch.to_string(),
        device_model: cpu_model,
        macs,
        uptime,
        cpu_serial,
    }
}
