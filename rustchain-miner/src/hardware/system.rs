// SPDX-License-Identifier: Apache-2.0
use sysinfo::System;

/// Get total RAM in gigabytes.
pub fn get_ram_gb() -> u64 {
    let sys = System::new_all();
    sys.total_memory() / (1024 * 1024 * 1024)
}

/// Get OS name and version string.
pub fn get_os_string() -> String {
    let name = System::name().unwrap_or_else(|| "Unknown".to_string());
    let version = System::os_version().unwrap_or_else(|| "".to_string());
    let kernel = System::kernel_version().unwrap_or_else(|| "".to_string());

    if !kernel.is_empty() {
        format!("{} {}", name, kernel)
    } else if !version.is_empty() {
        format!("{} {}", name, version)
    } else {
        name
    }
}

/// Get system uptime in seconds.
pub fn get_uptime_secs() -> u64 {
    System::uptime()
}

/// Get all available MAC addresses as hex strings.
pub fn get_mac_addresses() -> Vec<String> {
    let mut macs = Vec::new();

    // Try the mac_address crate first
    match mac_address::mac_address_by_name("eth0") {
        Ok(Some(addr)) => macs.push(addr.to_string().to_lowercase()),
        _ => {}
    }
    match mac_address::mac_address_by_name("wlan0") {
        Ok(Some(addr)) => macs.push(addr.to_string().to_lowercase()),
        _ => {}
    }
    match mac_address::mac_address_by_name("en0") {
        Ok(Some(addr)) => macs.push(addr.to_string().to_lowercase()),
        _ => {}
    }
    // Windows interfaces
    match mac_address::mac_address_by_name("Ethernet") {
        Ok(Some(addr)) => macs.push(addr.to_string().to_lowercase()),
        _ => {}
    }
    match mac_address::mac_address_by_name("Wi-Fi") {
        Ok(Some(addr)) => macs.push(addr.to_string().to_lowercase()),
        _ => {}
    }

    // Fallback: get the default/first MAC
    if macs.is_empty() {
        match mac_address::get_mac_address() {
            Ok(Some(addr)) => macs.push(addr.to_string().to_lowercase()),
            _ => macs.push("00:00:00:00:00:00".to_string()),
        }
    }

    // Deduplicate
    macs.sort();
    macs.dedup();
    macs
}
