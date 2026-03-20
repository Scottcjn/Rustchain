// SPDX-License-Identifier: MIT

use std::env;
use std::process::Command;

fn main() {
    println!("cargo:rerun-if-changed=build.rs");
    println!("cargo:rerun-if-env-changed=TARGET");
    println!("cargo:rerun-if-env-changed=CARGO_CFG_TARGET_ARCH");
    println!("cargo:rerun-if-env-changed=CARGO_CFG_TARGET_OS");

    let target = env::var("TARGET").unwrap();
    let target_arch = env::var("CARGO_CFG_TARGET_ARCH").unwrap();
    let target_os = env::var("CARGO_CFG_TARGET_OS").unwrap();

    println!("cargo:rustc-cfg=target=\"{}\"", target);

    // Hardware-specific optimizations
    match target_arch.as_str() {
        "x86_64" => {
            println!("cargo:rustc-cfg=feature=\"x86_64_optimizations\"");
            if is_cpu_feature_available("avx2") {
                println!("cargo:rustc-cfg=feature=\"avx2\"");
            }
            if is_cpu_feature_available("aes") {
                println!("cargo:rustc-cfg=feature=\"aes_ni\"");
            }
        }
        "aarch64" => {
            println!("cargo:rustc-cfg=feature=\"arm_optimizations\"");
            println!("cargo:rustc-cfg=feature=\"neon\"");
        }
        "arm" => {
            println!("cargo:rustc-cfg=feature=\"arm_optimizations\"");
            if target.contains("v7") {
                println!("cargo:rustc-cfg=feature=\"armv7\"");
            }
        }
        "powerpc64" | "powerpc64le" => {
            println!("cargo:rustc-cfg=feature=\"powerpc_optimizations\"");
            println!("cargo:rustc-cfg=feature=\"altivec\"");
        }
        "riscv64gc" => {
            println!("cargo:rustc-cfg=feature=\"riscv_optimizations\"");
        }
        _ => {}
    }

    // OS-specific configurations
    match target_os.as_str() {
        "linux" => {
            println!("cargo:rustc-link-lib=pthread");
            if target_arch == "x86_64" {
                println!("cargo:rustc-link-arg=-Wl,--as-needed");
            }
        }
        "macos" => {
            println!("cargo:rustc-link-lib=framework=Security");
            println!("cargo:rustc-link-lib=framework=IOKit");
        }
        "windows" => {
            println!("cargo:rustc-link-lib=ws2_32");
            println!("cargo:rustc-link-lib=userenv");
        }
        _ => {}
    }

    // Cross-compilation support
    if env::var("CROSS_COMPILE").is_ok() || target != env::var("HOST").unwrap_or_default() {
        println!("cargo:rustc-cfg=cross_compiling");

        // PowerPC-specific cross-compilation flags
        if target_arch.starts_with("powerpc") {
            println!("cargo:rustc-link-arg=-mcpu=native");
            println!("cargo:rustc-env=RUSTFLAGS=-C target-cpu=native");
        }

        // ARM cross-compilation optimizations
        if target_arch == "aarch64" || target_arch == "arm" {
            if let Ok(cc) = env::var("CC") {
                if cc.contains("musl") {
                    println!("cargo:rustc-cfg=feature=\"musl\"");
                }
            }
        }
    }

    // Mining-specific optimizations
    println!("cargo:rustc-cfg=feature=\"mining_optimizations\"");

    // Hardware thread detection for mining
    if let Ok(output) = Command::new("nproc").output() {
        if let Ok(cores) = String::from_utf8(output.stdout) {
            if let Ok(num_cores) = cores.trim().parse::<u32>() {
                println!("cargo:rustc-env=DETECTED_CORES={}", num_cores);
                if num_cores >= 8 {
                    println!("cargo:rustc-cfg=feature=\"high_core_count\"");
                }
            }
        }
    }

    // Memory optimization flags
    if target_arch == "x86_64" {
        println!("cargo:rustc-env=RUSTFLAGS=-C target-feature=+crt-static");
    }

    // Ed25519 acceleration detection
    if is_crypto_acceleration_available() {
        println!("cargo:rustc-cfg=feature=\"crypto_acceleration\"");
    }

    // Debug vs release specific configs
    let profile = env::var("PROFILE").unwrap_or_default();
    if profile == "release" {
        println!("cargo:rustc-cfg=optimized");
        println!("cargo:rustc-env=RUSTFLAGS=-C opt-level=3 -C lto=fat");
    }
}

fn is_cpu_feature_available(feature: &str) -> bool {
    if let Ok(output) = Command::new("grep")
        .args(&["-m1", feature, "/proc/cpuinfo"])
        .output()
    {
        !output.stdout.is_empty()
    } else {
        false
    }
}

fn is_crypto_acceleration_available() -> bool {
    // Check for hardware crypto acceleration
    is_cpu_feature_available("aes") || is_cpu_feature_available("sha")
}
