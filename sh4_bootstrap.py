// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import os
import sys
import subprocess
import platform
import socket
import json
import sqlite3
from pathlib import Path

DB_PATH = "rustchain.db"
SH4_TARGET = "sh4-unknown-linux-gnu"
DREAMCAST_IP_RANGE = "192.168.1"

def check_cross_compiler():
    """Check if SH4 cross-compilation tools are available"""
    tools = ["sh4-linux-gnu-gcc", "sh4-linux-gnu-g++", "sh4-linux-gnu-strip"]
    missing = []

    for tool in tools:
        try:
            subprocess.run([tool, "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            missing.append(tool)

    if missing:
        print(f"ERROR: Missing SH4 cross-compilation tools: {', '.join(missing)}")
        print("\nInstall with:")
        print("  sudo apt-get install gcc-sh4-linux-gnu g++-sh4-linux-gnu")
        print("  # or build from source with crosstool-ng")
        return False

    print("✓ SH4 cross-compiler toolchain detected")
    return True

def check_rust_target():
    """Verify Rust SH4 target availability"""
    try:
        result = subprocess.run(["rustup", "target", "list", "--installed"],
                              capture_output=True, text=True, check=True)
        if SH4_TARGET in result.stdout:
            print("✓ Rust SH4 target already installed")
            return True

        print(f"Installing Rust target: {SH4_TARGET}")
        subprocess.run(["rustup", "target", "add", SH4_TARGET], check=True)
        print("✓ Rust SH4 target installed")
        return True
    except subprocess.CalledProcessError:
        print("ERROR: Failed to install Rust SH4 target")
        return False

def validate_network_config():
    """Check network configuration for Dreamcast deployment"""
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)

        if not local_ip.startswith(DREAMCAST_IP_RANGE):
            print(f"WARNING: Local IP {local_ip} not in typical Dreamcast range")
            print("Configure network for 192.168.1.x subnet for BBA compatibility")
        else:
            print(f"✓ Network configured: {local_ip}")

        # Test internet connectivity for pool connection
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.settimeout(3)
        result = test_socket.connect_ex(("8.8.8.8", 53))
        test_socket.close()

        if result == 0:
            print("✓ Internet connectivity verified")
        else:
            print("WARNING: No internet connection detected")

        return True
    except Exception as e:
        print(f"Network check failed: {e}")
        return False

def create_bootstrap_db():
    """Initialize minimal database for SH4 deployment"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sh4_config (
                key TEXT PRIMARY KEY,
                value TEXT,
                timestamp INTEGER DEFAULT (strftime('%s', 'now'))
            )
        """)

        # Store SH4-specific configuration
        config_data = [
            ("arch", "sh4"),
            ("cpu_mhz", "200"),
            ("cache_kb", "32"),
            ("multiplier", "3.0"),
            ("deployment_type", "dreamcast"),
            ("requires_bba", "true")
        ]

        cursor.executemany("INSERT OR REPLACE INTO sh4_config (key, value) VALUES (?, ?)",
                          config_data)
        conn.commit()
        print("✓ Bootstrap database initialized")

def generate_bootable_instructions():
    """Generate instructions for creating bootable media"""
    instructions = """
=== DREAMCAST BOOTABLE MEDIA CREATION ===

OPTION 1: CD-R Boot (MIL-CD Exploit)
1. Create ISO with miner binary in root
2. Use DiscJuggler or ImgBurn with 'Mode 1' format
3. Burn at slowest speed (1x-4x) for compatibility
4. Boot without disc, then swap to burned CD-R
5. Miner auto-starts on network detection

OPTION 2: SD Card (GDEMU/MODE)
1. Format SD card as FAT32
2. Copy miner to /01/track01.bin
3. Create text file: /01/track01.cue
4. Insert SD card into GDEMU
5. Power on Dreamcast

NETWORK SETUP:
- Broadband Adapter required
- Configure DHCP or static IP: 192.168.1.100
- Ensure router allows outbound TCP 8080
- Pool connection: rustchain-pool.network:8080

MINING PARAMETERS:
- Target difficulty: AUTO (adjusts for 200MHz SH4)
- Hash rate: ~50-100 H/s estimated
- Power consumption: ~23W (console + BBA)
- Antiquity multiplier: 3.0x (highest on network)
"""

    with open("dreamcast_deployment.txt", "w") as f:
        f.write(instructions)

    print("✓ Deployment instructions written to dreamcast_deployment.txt")

def compile_for_sh4():
    """Attempt to cross-compile miner for SH4"""
    if not Path("src/main.rs").exists() and not Path("node/rustchain_v2_integrated_v2.2.1_rip200.py").exists():
        print("WARNING: No miner source found, skipping compilation")
        return False

    # Check if we have Rust source
    if Path("Cargo.toml").exists():
        print("Compiling Rust miner for SH4...")
        try:
            env = os.environ.copy()
            env["CARGO_TARGET_SH4_UNKNOWN_LINUX_GNU_LINKER"] = "sh4-linux-gnu-gcc"

            subprocess.run([
                "cargo", "build",
                "--release",
                "--target", SH4_TARGET
            ], env=env, check=True)

            print("✓ SH4 binary compiled successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Compilation failed: {e}")
            return False

    print("No Rust project found, manual compilation required")
    return False

def main():
    print("RustChain SH4/Dreamcast Bootstrap v1.0")
    print("=====================================")

    # System checks
    if platform.machine() not in ["x86_64", "amd64"]:
        print("WARNING: Cross-compilation typically requires x86_64 host")

    success_count = 0
    checks = [
        check_cross_compiler,
        check_rust_target,
        validate_network_config,
        create_bootstrap_db
    ]

    for check in checks:
        if check():
            success_count += 1

    print(f"\nBootstrap Status: {success_count}/{len(checks)} checks passed")

    # Generate deployment materials
    generate_bootable_instructions()
    compile_for_sh4()

    print("\n=== NEXT STEPS ===")
    print("1. Review dreamcast_deployment.txt")
    print("2. Prepare bootable media (CD-R or SD)")
    print("3. Configure Dreamcast network settings")
    print("4. Deploy to console and start mining!")
    print("\nEarn 150 RTC bounty + 3.0x antiquity multiplier! 🚀")

if __name__ == "__main__":
    main()
