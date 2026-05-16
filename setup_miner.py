#!/usr/bin/env python3
"""
RustChain Miner Setup Script
Automated setup for RustChain Universal Miner
"""

import os
import sys
import subprocess
import platform
import json
import urllib.request
import urllib.error
import hashlib
import time
from urllib.parse import urlparse
from pathlib import Path

MINER_ARTIFACTS = {
    "Linux": {
        "url": "https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners/linux/rustchain_linux_miner.py",
        "sha256": "9475fe15d149ef7b3824c0009453c55e17fb6d1d411ea37e9f24f58c6313871c",
    },
    "Darwin": {
        "url": "https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners/macos/rustchain_mac_miner_v2.5.py",
        "sha256": "e50cea51a24c8c0337e340287a05e6431f6d95883ab913a1a79c19e99bc03dd8",
    },
    "Windows": {
        "url": "https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners/windows/rustchain_windows_miner.py",
        "sha256": "51fe431cbee3c5b81218a738c221d45e675dafa5d67f9aff716d4ea11f304662",
    },
}

class MinerSetup:
    def __init__(self):
        self.system = platform.system()
        self.arch = platform.machine()
        self.python_version = sys.version_info
        self.setup_dir = Path.home() / "rustchain_miner"
        self.config_file = self.setup_dir / "miner_config.json"
        
    def log(self, message):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {message}")
        
    def check_requirements(self):
        """Check system requirements and Python version"""
        self.log("Checking system requirements...")
        
        if self.python_version < (3, 7):
            raise Exception("Python 3.7 or higher required")
            
        # Check for required modules
        required_modules = ['hashlib', 'json', 'threading', 'time', 'socket']
        for module in required_modules:
            try:
                __import__(module)
            except ImportError:
                raise Exception(f"Required module {module} not found")
                
        self.log(f"System: {self.system} {self.arch}")
        self.log(f"Python: {self.python_version.major}.{self.python_version.minor}.{self.python_version.micro}")
        self.log("Requirements check passed")
        
    def detect_hardware(self):
        """Detect available hardware for mining"""
        self.log("Detecting hardware capabilities...")
        
        hardware_info = {
            "cpu_cores": os.cpu_count() or 1,
            "system": self.system,
            "arch": self.arch,
            "recommended_threads": max(1, (os.cpu_count() or 1) - 1),
            "gpu_available": False,
            "memory_mb": 0
        }
        
        # Try to detect memory
        try:
            if self.system == "Linux":
                with open("/proc/meminfo", "r") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            hardware_info["memory_mb"] = int(line.split()[1]) // 1024
                            break
            elif self.system == "Darwin":  # macOS
                result = subprocess.run(["sysctl", "hw.memsize"], capture_output=True, text=True)
                if result.returncode == 0:
                    hardware_info["memory_mb"] = int(result.stdout.split(":")[1].strip()) // (1024 * 1024)
        except:
            pass
            
        # Basic GPU detection
        try:
            if self.system == "Linux":
                result = subprocess.run(["lspci"], capture_output=True, text=True)
                if "VGA" in result.stdout or "3D" in result.stdout:
                    hardware_info["gpu_available"] = True
            elif self.system == "Windows":
                result = subprocess.run(["wmic", "path", "win32_VideoController", "get", "name"], capture_output=True, text=True)
                if result.returncode == 0 and len(result.stdout.strip().split('\n')) > 2:
                    hardware_info["gpu_available"] = True
        except:
            pass
            
        self.log(f"CPU Cores: {hardware_info['cpu_cores']}")
        self.log(f"Recommended mining threads: {hardware_info['recommended_threads']}")
        self.log(f"Memory: {hardware_info['memory_mb']} MB")
        self.log(f"GPU Available: {hardware_info['gpu_available']}")
        
        return hardware_info
        
    def create_directories(self):
        """Create necessary directories"""
        self.log("Creating directories...")
        self.setup_dir.mkdir(exist_ok=True)
        (self.setup_dir / "logs").mkdir(exist_ok=True)
        (self.setup_dir / "data").mkdir(exist_ok=True)
        
    def _miner_artifact(self):
        return MINER_ARTIFACTS.get(self.system, MINER_ARTIFACTS["Linux"])

    def download_miner(self):
        """Download and verify the platform miner script."""
        self.log("Downloading RustChain miner...")

        artifact = self._miner_artifact()
        miner_url = artifact["url"]
        expected_hash = artifact["sha256"]
        miner_file = self.setup_dir / "rustchain_universal_miner.py"

        parsed = urlparse(miner_url)
        if parsed.scheme != "https":
            raise Exception(f"Refusing non-HTTPS miner URL: {miner_url}")

        try:
            self.log(f"Downloading from: {miner_url}")
            with urllib.request.urlopen(miner_url, timeout=30) as response:
                content = response.read()
        except Exception as exc:
            raise Exception(f"Failed to download RustChain miner: {exc}") from exc

        actual_hash = hashlib.sha256(content).hexdigest()
        if actual_hash != expected_hash:
            raise Exception(
                "Downloaded miner SHA-256 mismatch: "
                f"expected {expected_hash}, got {actual_hash}"
            )

        with open(miner_file, 'wb') as f:
            f.write(content)

        self.log("Miner downloaded and verified successfully")
        
    def create_local_miner(self, miner_file):
        """Create a basic local miner implementation"""
        self.log("Creating local miner implementation...")
        
        miner_content = '''#!/usr/bin/env python3
"""
RustChain Universal Miner - Local Implementation
Basic CPU miner for RustChain network
"""

import hashlib
import json
import time
import threading
import random
import sys
from datetime import datetime

class RustChainMiner:
    def __init__(self, config_file="miner_config.json"):
        self.config = self.load_config(config_file)
        self.mining = False
        self.stats = {
            "hashes": 0,
            "blocks_found": 0,
            "start_time": time.time(),
            "last_block": None
        }
        
    def load_config(self, config_file):
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except:
            return {
                "threads": 1,
                "wallet_address": "RTC_DEFAULT_WALLET",
                "pool_url": "pool.rustchain.io:8080",
                "difficulty": 4
            }
    
    def mine_block(self, thread_id):
        """Simple proof-of-work mining"""
        while self.mining:
            nonce = random.randint(0, 2**32)
            timestamp = int(time.time())
            
            block_data = {
                "timestamp": timestamp,
                "nonce": nonce,
                "miner": self.config["wallet_address"],
                "thread": thread_id
            }
            
            block_string = json.dumps(block_data, sort_keys=True)
            hash_result = hashlib.sha256(block_string.encode()).hexdigest()
            
            self.stats["hashes"] += 1
            
            # Check if hash meets difficulty
            if hash_result.startswith("0" * self.config["difficulty"]):
                self.stats["blocks_found"] += 1
                self.stats["last_block"] = hash_result
                print(f"[{datetime.now()}] Block found! Hash: {hash_result}")
                print(f"Block data: {block_string}")
                
            if self.stats["hashes"] % 1000 == 0:
                elapsed = time.time() - self.stats["start_time"]
                hashrate = self.stats["hashes"] / elapsed if elapsed > 0 else 0
                print(f"[{datetime.now()}] Thread {thread_id}: {self.stats['hashes']} hashes, {hashrate:.2f} H/s")
                
            time.sleep(0.001)  # Small delay to prevent excessive CPU usage
    
    def start_mining(self):
        """Start mining with configured number of threads"""
        print(f"Starting RustChain miner with {self.config['threads']} threads...")
        print(f"Wallet: {self.config['wallet_address']}")
        print(f"Difficulty: {self.config['difficulty']}")
        
        self.mining = True
        threads = []
        
        for i in range(self.config["threads"]):
            thread = threading.Thread(target=self.mine_block, args=(i,))
            thread.daemon = True
            thread.start()
            threads.append(thread)
            
        try:
            while self.mining:
                time.sleep(10)
                elapsed = time.time() - self.stats["start_time"]
                hashrate = self.stats["hashes"] / elapsed if elapsed > 0 else 0
                print(f"[{datetime.now()}] Mining stats - Hashes: {self.stats['hashes']}, Blocks: {self.stats['blocks_found']}, Rate: {hashrate:.2f} H/s")
                
        except KeyboardInterrupt:
            print("\\nStopping miner...")
            self.mining = False
            
        for thread in threads:
            thread.join(timeout=1)
            
        print("Miner stopped")

if __name__ == "__main__":
    miner = RustChainMiner()
    miner.start_mining()
'''
        
        with open(miner_file, 'w') as f:
            f.write(miner_content)
            
        # Make executable on Unix-like systems
        if self.system in ["Linux", "Darwin"]:
            os.chmod(miner_file, 0o755)
            
        self.log("Local miner implementation created")
        
    def create_config(self, hardware_info):
        """Create miner configuration"""
        self.log("Creating miner configuration...")
        
        # Get wallet address from user
        wallet_address = input("Enter your RustChain wallet address (or press Enter for default): ").strip()
        if not wallet_address:
            wallet_address = "RTC_" + hashlib.sha256(str(time.time()).encode()).hexdigest()[:16].upper()
            self.log(f"Generated default wallet address: {wallet_address}")
        
        config = {
            "wallet_address": wallet_address,
            "threads": hardware_info["recommended_threads"],
            "pool_url": "pool.rustchain.io:8080",
            "difficulty": 4,
            "log_level": "INFO",
            "hardware_info": hardware_info,
            "created": time.time(),
            "version": "1.0.0"
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)
            
        self.log(f"Configuration saved to: {self.config_file}")
        return config
        
    def create_start_script(self):
        """Create platform-specific start scripts"""
        self.log("Creating start scripts...")
        
        python_cmd = sys.executable
        miner_path = self.setup_dir / "rustchain_universal_miner.py"
        
        if self.system == "Windows":
            script_path = self.setup_dir / "start_miner.bat"
            with open(script_path, 'w') as f:
                f.write(f'''@echo off
cd /d "{self.setup_dir}"
echo Starting RustChain Miner...
"{python_cmd}" "{miner_path}"
pause
''')
        else:
            script_path = self.setup_dir / "start_miner.sh"
            with open(script_path, 'w') as f:
                f.write(f'''#!/bin/bash
cd "{self.setup_dir}"
echo "Starting RustChain Miner..."
"{python_cmd}" "{miner_path}"
''')
            os.chmod(script_path, 0o755)
            
        self.log(f"Start script created: {script_path}")
        
    def install_service(self):
        """Optional: Install as system service"""
        response = input("Install miner as system service? (y/N): ").strip().lower()
        if response != 'y':
            return
            
        self.log("Installing as system service...")
        
        try:
            if self.system == "Linux":
                self.install_systemd_service()
            elif self.system == "Darwin":
                self.install_launchd_service()
            elif self.system == "Windows":
                self.install_windows_service()
        except Exception as e:
            self.log(f"Service installation failed: {e}")
            
    def install_systemd_service(self):
        """Install systemd service on Linux"""
        service_content = f'''[Unit]
Description=RustChain Miner
After=network.target

[Service]
Type=simple
User={os.getlogin()}
WorkingDirectory={self.setup_dir}
ExecStart={sys.executable} {self.setup_dir}/rustchain_universal_miner.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
'''
        
        service_path = "/tmp/rustchain-miner.service"
        with open(service_path, 'w') as f:
            f.write(service_content)
            
        print(f"Service file created at {service_path}")
        print("To install, run as root:")
        print(f"sudo cp {service_path} /etc/systemd/system/")
        print("sudo systemctl daemon-reload")
        print("sudo systemctl enable rustchain-miner")
        print("sudo systemctl start rustchain-miner")
        
    def run_setup(self):
        """Main setup process"""
        try:
            print("=" * 60)
            print("RustChain Miner Setup")
            print("=" * 60)
            
            self.check_requirements()
            hardware_info = self.detect_hardware()
            self.create_directories()
            self.download_miner()
            config = self.create_config(hardware_info)
            self.create_start_script()
            self.install_service()
            
            print("\n" + "=" * 60)
            print("Setup Complete!")
            print("=" * 60)
            print(f"Installation directory: {self.setup_dir}")
            print(f"Wallet address: {config['wallet_address']}")
            print(f"Mining threads: {config['threads']}")
            print("\nTo start mining:")
            if self.system == "Windows":
                print(f"  Double-click: {self.setup_dir}/start_miner.bat")
            else:
                print(f"  Run: {self.setup_dir}/start_miner.sh")
            print(f"  Or: python {self.setup_dir}/rustchain_universal_miner.py")
            print("\nHappy mining! 🚀")
            
        except Exception as e:
            self.log(f"Setup failed: {e}")
            sys.exit(1)

if __name__ == "__main__":
    setup = MinerSetup()
    setup.run_setup()
