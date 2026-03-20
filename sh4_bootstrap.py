// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import os
import sys
import time
import struct
import socket
import subprocess
import re
from threading import Thread

# Dreamcast SH4 hardware detection and bootstrap
class DreamcastBootstrap:
    def __init__(self):
        self.hardware_info = {}
        self.network_config = {}
        self.miner_config = {}

    def detect_cpu(self):
        """Detect SH4 CPU variant and clock speed"""
        try:
            with open('/proc/cpuinfo', 'r') as f:
                cpuinfo = f.read()

            # Look for SH4 variants
            if 'SH7750' in cpuinfo:
                self.hardware_info['cpu'] = 'SH7750'
            elif 'SH7751' in cpuinfo:
                self.hardware_info['cpu'] = 'SH7751R'
            else:
                self.hardware_info['cpu'] = 'SH4_unknown'

            # Extract clock speed
            clock_match = re.search(r'cpu MHz\s*:\s*(\d+)', cpuinfo)
            if clock_match:
                self.hardware_info['mhz'] = int(clock_match.group(1))
            else:
                self.hardware_info['mhz'] = 200  # Default DC speed

            print(f"[SH4] Detected: {self.hardware_info['cpu']} @ {self.hardware_info['mhz']}MHz")

        except Exception as e:
            print(f"[ERROR] CPU detection failed: {e}")
            self.hardware_info['cpu'] = 'SH4_fallback'
            self.hardware_info['mhz'] = 200

    def detect_ram(self):
        """Detect RAM configuration - 16MB standard or 32MB modded"""
        try:
            with open('/proc/meminfo', 'r') as f:
                meminfo = f.read()

            mem_match = re.search(r'MemTotal:\s*(\d+)\s*kB', meminfo)
            if mem_match:
                ram_kb = int(mem_match.group(1))
                ram_mb = ram_kb // 1024

                if ram_mb >= 28:  # Account for kernel overhead
                    self.hardware_info['ram_mb'] = 32
                    self.hardware_info['ram_type'] = 'modded'
                else:
                    self.hardware_info['ram_mb'] = 16
                    self.hardware_info['ram_type'] = 'stock'

                print(f"[RAM] Detected: {self.hardware_info['ram_mb']}MB ({self.hardware_info['ram_type']})")

        except Exception as e:
            print(f"[ERROR] RAM detection failed: {e}")
            self.hardware_info['ram_mb'] = 16
            self.hardware_info['ram_type'] = 'unknown'

    def detect_bba(self):
        """Detect broadband adapter type - HIT-0300 or HIT-0400"""
        self.hardware_info['bba_type'] = 'none'

        # Check for ethernet interface
        try:
            result = subprocess.run(['ip', 'link', 'show'], capture_output=True, text=True)
            interfaces = result.stdout

            if 'eth0' in interfaces:
                # Try to determine BBA type from driver/hardware info
                try:
                    with open('/sys/class/net/eth0/device/vendor', 'r') as f:
                        vendor = f.read().strip()

                    if vendor == '0x11db':  # Realtek
                        self.hardware_info['bba_type'] = 'HIT-0400'
                    else:
                        self.hardware_info['bba_type'] = 'HIT-0300'

                except:
                    # Fallback detection via speed/duplex
                    try:
                        result = subprocess.run(['ethtool', 'eth0'], capture_output=True, text=True)
                        if '100Mb/s' in result.stdout:
                            self.hardware_info['bba_type'] = 'HIT-0400'
                        else:
                            self.hardware_info['bba_type'] = 'HIT-0300'
                    except:
                        self.hardware_info['bba_type'] = 'unknown'

                print(f"[BBA] Detected: {self.hardware_info['bba_type']}")
            else:
                print("[BBA] No ethernet interface found")

        except Exception as e:
            print(f"[ERROR] BBA detection failed: {e}")

    def setup_network(self):
        """Configure network based on BBA type"""
        if self.hardware_info['bba_type'] == 'none':
            print("[NET] No BBA detected, skipping network setup")
            return False

        try:
            # Basic network configuration
            if self.hardware_info['bba_type'] == 'HIT-0300':
                # 10Mbps half-duplex optimization
                subprocess.run(['ethtool', '-s', 'eth0', 'speed', '10', 'duplex', 'half'],
                             capture_output=True)
            else:
                # HIT-0400 can do 100Mbps full-duplex
                subprocess.run(['ethtool', '-s', 'eth0', 'speed', '100', 'duplex', 'full'],
                             capture_output=True)

            # Try DHCP first
            print("[NET] Attempting DHCP configuration...")
            result = subprocess.run(['dhclient', '-1', 'eth0'],
                                  timeout=30, capture_output=True)

            if result.returncode == 0:
                # Get assigned IP
                result = subprocess.run(['ip', 'addr', 'show', 'eth0'],
                                      capture_output=True, text=True)
                ip_match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', result.stdout)
                if ip_match:
                    self.network_config['ip'] = ip_match.group(1)
                    self.network_config['method'] = 'dhcp'
                    print(f"[NET] DHCP successful: {self.network_config['ip']}")
                    return True

            # DHCP failed, try static fallback
            print("[NET] DHCP failed, trying static 192.168.1.200...")
            subprocess.run(['ip', 'addr', 'add', '192.168.1.200/24', 'dev', 'eth0'])
            subprocess.run(['ip', 'link', 'set', 'eth0', 'up'])
            subprocess.run(['ip', 'route', 'add', 'default', 'via', '192.168.1.1'])

            self.network_config['ip'] = '192.168.1.200'
            self.network_config['method'] = 'static'
            print("[NET] Static configuration applied")
            return True

        except Exception as e:
            print(f"[ERROR] Network setup failed: {e}")
            return False

    def configure_sh4_optimizations(self):
        """Set SH4-specific compiler and runtime optimizations"""
        # SH4 specific flags
        sh4_cflags = [
            '-m4',  # SH4 instruction set
            '-ml',  # Little endian
            '-O2',  # Optimize for speed
            '-fomit-frame-pointer',
            '-mcpu=sh4',
            '-mfused-madd'
        ]

        # Memory optimizations based on RAM size
        if self.hardware_info['ram_mb'] == 16:
            # Conservative settings for 16MB
            self.miner_config['worker_threads'] = 1
            self.miner_config['hash_buffer_kb'] = 128
            self.miner_config['block_cache_mb'] = 2
        else:
            # More aggressive for 32MB mod
            self.miner_config['worker_threads'] = 2
            self.miner_config['hash_buffer_kb'] = 512
            self.miner_config['block_cache_mb'] = 8

        # BBA-specific network tuning
        if self.hardware_info['bba_type'] == 'HIT-0300':
            self.miner_config['network_timeout'] = 10000  # 10s for slow connection
            self.miner_config['max_peers'] = 3
        else:
            self.miner_config['network_timeout'] = 5000   # 5s for faster HIT-0400
            self.miner_config['max_peers'] = 8

        # SH4 cache optimization
        self.miner_config['use_sh4_cache_hints'] = True
        self.miner_config['prefetch_distance'] = 64

        print(f"[OPT] Configured for {self.miner_config['worker_threads']} threads, "
              f"{self.miner_config['hash_buffer_kb']}KB hash buffer")

    def generate_miner_config(self):
        """Generate optimized miner configuration file"""
        config_content = f"""# Dreamcast SH4 RustChain Miner Configuration
# Hardware: {self.hardware_info['cpu']} @ {self.hardware_info['mhz']}MHz
# RAM: {self.hardware_info['ram_mb']}MB {self.hardware_info['ram_type']}
# BBA: {self.hardware_info['bba_type']}

[hardware]
arch = "sh4"
cpu_mhz = {self.hardware_info['mhz']}
ram_mb = {self.hardware_info['ram_mb']}
bba_type = "{self.hardware_info['bba_type']}"

[mining]
worker_threads = {self.miner_config['worker_threads']}
hash_algorithm = "blake2b_sh4"
difficulty_target = 0x0000ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
enable_antiquity_multiplier = true
antiquity_multiplier = 3.0

[performance]
hash_buffer_kb = {self.miner_config['hash_buffer_kb']}
block_cache_mb = {self.miner_config['block_cache_mb']}
use_sh4_cache_hints = {str(self.miner_config['use_sh4_cache_hints']).lower()}
prefetch_distance = {self.miner_config['prefetch_distance']}

[network]
listen_addr = "{self.network_config.get('ip', '127.0.0.1')}"
listen_port = 8333
max_peers = {self.miner_config['max_peers']}
network_timeout_ms = {self.miner_config['network_timeout']}
bootstrap_nodes = [
    "rustchain.sh4.network:8333",
    "dreamcast.rustchain.io:8333"
]

[logging]
level = "INFO"
enable_performance_stats = true
stats_interval_sec = 60
"""

        with open('dreamcast_miner.conf', 'w') as f:
            f.write(config_content)

        print("[CFG] Generated dreamcast_miner.conf")

    def launch_miner(self):
        """Launch the RustChain miner with Dreamcast optimizations"""
        if not os.path.exists('rustchain_miner'):
            print("[ERROR] rustchain_miner binary not found!")
            print("Please compile the miner for SH4 first:")
            print("  export CC=sh4-linux-gnu-gcc")
            print("  export RUSTFLAGS='-C target-cpu=sh4'")
            print("  cargo build --release --target sh4-unknown-linux-gnu")
            return False

        print(f"[LAUNCH] Starting RustChain miner on Dreamcast...")
        print(f"         Hardware: {self.hardware_info['cpu']} {self.hardware_info['mhz']}MHz")
        print(f"         Memory: {self.hardware_info['ram_mb']}MB {self.hardware_info['ram_type']}")
        print(f"         Network: {self.hardware_info['bba_type']} @ {self.network_config.get('ip', 'N/A')}")
        print(f"         Threads: {self.miner_config['worker_threads']}")
        print("")

        try:
            # Set SH4 performance governor
            subprocess.run(['echo', 'performance'], stdout=open('/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor', 'w'))
        except:
            pass  # Ignore if not supported

        # Launch with nice priority
        cmd = ['nice', '-n', '-10', './rustchain_miner', '--config', 'dreamcast_miner.conf']

        try:
            result = subprocess.run(cmd)
            return result.returncode == 0
        except KeyboardInterrupt:
            print("\n[STOP] Miner stopped by user")
            return True
        except Exception as e:
            print(f"[ERROR] Miner launch failed: {e}")
            return False

def main():
    print("=" * 60)
    print("RustChain Dreamcast Bootstrap v1.0")
    print("SH4 Architecture - 3.0x Antiquity Multiplier")
    print("=" * 60)

    bootstrap = DreamcastBootstrap()

    # Hardware detection phase
    print("\n[PHASE 1] Hardware Detection")
    bootstrap.detect_cpu()
    bootstrap.detect_ram()
    bootstrap.detect_bba()

    # Network setup phase
    print("\n[PHASE 2] Network Configuration")
    if not bootstrap.setup_network():
        print("[WARNING] Network setup failed, mining will be local only")

    # Optimization phase
    print("\n[PHASE 3] SH4 Optimizations")
    bootstrap.configure_sh4_optimizations()
    bootstrap.generate_miner_config()

    # Launch phase
    print("\n[PHASE 4] Miner Launch")
    success = bootstrap.launch_miner()

    if success:
        print("\n[SUCCESS] Dreamcast miner completed successfully!")
    else:
        print("\n[FAILED] Miner launch failed - check configuration")
        sys.exit(1)

if __name__ == '__main__':
    main()
