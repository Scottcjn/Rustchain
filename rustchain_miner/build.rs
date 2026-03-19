// SPDX-License-Identifier: MIT

use std::env;
use std::process::Command;

fn main() {
    println!("cargo:rerun-if-changed=build.rs");
    
    let target = env::var("TARGET").unwrap();
    let target_arch = env::var("CARGO_CFG_TARGET_ARCH").unwrap();
    let target_os = env::var("CARGO_CFG_TARGET_OS").unwrap();
    
    // PowerPC architecture support
    if target_arch == "powerpc" || target_arch == "powerpc64" {
        println!("cargo:rustc-cfg=powerpc");
        if target_arch == "powerpc64" {
            println!("cargo:rustc-cfg=powerpc64");
        }
        
        // PowerPC specific optimizations
        println!("cargo:rustc-env=RUSTFLAGS=-C target-cpu=native");
    }
    
    // ARM architecture support
    if target_arch.starts_with("arm") || target_arch == "aarch64" {
        println!("cargo:rustc-cfg=arm");
        
        if target_arch == "aarch64" {
            println!("cargo:rustc-cfg=arm64");
        } else if target_arch.starts_with("armv7") {
            println!("cargo:rustc-cfg=armv7");
        } else if target_arch.starts_with("armv6") {
            println!("cargo:rustc-cfg=armv6");
        }
        
        // ARM NEON support detection
        if target_arch == "aarch64" || target_arch.contains("neon") {
            println!("cargo:rustc-cfg=neon");
        }
    }
    
    // x86/x86_64 architecture
    if target_arch == "x86_64" || target_arch == "x86" {
        println!("cargo:rustc-cfg=x86");
        
        // Check for AVX2 support
        if let Ok(output) = Command::new("rustc")
            .args(&["--print", "target-cpus"])
            .output() 
        {
            let cpu_info = String::from_utf8_lossy(&output.stdout);
            if cpu_info.contains("haswell") || cpu_info.contains("skylake") {
                println!("cargo:rustc-cfg=avx2");
            }
        }
    }
    
    // Cross-compilation toolchain setup
    match target_os.as_str() {
        "linux" => {
            if target.contains("musl") {
                println!("cargo:rustc-cfg=musl");
            }
            
            // Link against system libraries for crypto acceleration
            if target_arch == "powerpc64" {
                println!("cargo:rustc-link-lib=crypto");
            }
        },
        "windows" => {
            println!("cargo:rustc-cfg=windows");
            if target_arch.contains("gnu") {
                println!("cargo:rustc-link-lib=ws2_32");
                println!("cargo:rustc-link-lib=userenv");
            }
        },
        _ => {}
    }
    
    // Hardware feature detection flags
    println!("cargo:rustc-cfg=hw_detection");
    
    // Ed25519 backend selection
    if cfg!(feature = "dalek") {
        println!("cargo:rustc-cfg=ed25519_dalek");
    } else {
        println!("cargo:rustc-cfg=ed25519_compact");
    }
    
    // Mining optimization flags
    println!("cargo:rustc-cfg=mining_optimized");
    
    // Attestation support
    println!("cargo:rustc-cfg=attestation");
    
    // Debug vs release specific flags
    if env::var("PROFILE").unwrap() == "release" {
        println!("cargo:rustc-cfg=optimized");
    }
}