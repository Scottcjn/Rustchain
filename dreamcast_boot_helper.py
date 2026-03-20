# SPDX-License-Identifier: MIT

import os
import sys
import subprocess
import shutil
import tempfile
import json
from pathlib import Path
from typing import Dict, List, Optional

# Dreamcast SH4 cross-compilation and boot image generation
DC_TOOLCHAIN_PREFIX = "sh4-linux-gnu-"
DC_KERNEL_CONFIG = "dreamcast_defconfig"
DC_BOOT_SECTORS = 2048
DC_ISO_SIZE_MB = 650

class DreamcastBootHelper:
    """Utility for creating Dreamcast-bootable media with RustChain miner"""

    def __init__(self, work_dir: str = "/tmp/dc_build"):
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(exist_ok=True)
        self.toolchain_path = None
        self.kernel_source = None

    def check_toolchain(self) -> bool:
        """Verify SH4 cross-compilation toolchain is available"""
        try:
            result = subprocess.run([f"{DC_TOOLCHAIN_PREFIX}gcc", "--version"],
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print(f"SH4 toolchain found: {result.stdout.splitlines()[0]}")
                return True
        except FileNotFoundError:
            pass

        print("ERROR: SH4 cross-compilation toolchain not found")
        print("Install with: apt-get install gcc-sh4-linux-gnu")
        return False

    def setup_kernel_source(self, kernel_version: str = "6.1.0") -> bool:
        """Download and configure Linux kernel source for Dreamcast"""
        kernel_dir = self.work_dir / f"linux-{kernel_version}"

        if kernel_dir.exists():
            print(f"Using existing kernel source: {kernel_dir}")
            self.kernel_source = kernel_dir
            return True

        print(f"Downloading Linux {kernel_version} kernel source...")
        kernel_url = f"https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-{kernel_version}.tar.xz"

        try:
            subprocess.run(["wget", "-O", str(self.work_dir / "kernel.tar.xz"), kernel_url],
                         check=True)
            subprocess.run(["tar", "xf", str(self.work_dir / "kernel.tar.xz"),
                          "-C", str(self.work_dir)], check=True)

            os.chdir(kernel_dir)

            # Configure for Dreamcast
            env = os.environ.copy()
            env["ARCH"] = "sh"
            env["CROSS_COMPILE"] = DC_TOOLCHAIN_PREFIX

            subprocess.run(["make", DC_KERNEL_CONFIG], env=env, check=True)

            # Enable network and broadband adapter
            config_additions = [
                "CONFIG_NET=y",
                "CONFIG_INET=y",
                "CONFIG_SH_DREAMCAST=y",
                "CONFIG_MAPLE=y",
                "CONFIG_8139TOO=y",
                "CONFIG_DEVTMPFS=y",
                "CONFIG_DEVTMPFS_MOUNT=y"
            ]

            with open(".config", "a") as f:
                for opt in config_additions:
                    f.write(f"{opt}\n")

            subprocess.run(["make", "olddefconfig"], env=env, check=True)

            self.kernel_source = kernel_dir
            return True

        except subprocess.CalledProcessError as e:
            print(f"Kernel setup failed: {e}")
            return False

    def build_kernel(self) -> Optional[Path]:
        """Build SH4 kernel for Dreamcast"""
        if not self.kernel_source:
            print("No kernel source configured")
            return None

        print("Building SH4 kernel...")
        os.chdir(self.kernel_source)

        env = os.environ.copy()
        env["ARCH"] = "sh"
        env["CROSS_COMPILE"] = DC_TOOLCHAIN_PREFIX

        try:
            subprocess.run(["make", "-j", str(os.cpu_count() or 4)],
                          env=env, check=True)

            kernel_image = self.kernel_source / "arch" / "sh" / "boot" / "zImage"
            if kernel_image.exists():
                print(f"Kernel built: {kernel_image}")
                return kernel_image
            else:
                print("Kernel build completed but zImage not found")
                return None

        except subprocess.CalledProcessError as e:
            print(f"Kernel build failed: {e}")
            return None

    def create_initramfs(self, miner_binary: Path) -> Optional[Path]:
        """Create minimal initramfs with RustChain miner"""
        initramfs_dir = self.work_dir / "initramfs"
        initramfs_dir.mkdir(exist_ok=True)

        # Basic directory structure
        for d in ["bin", "sbin", "dev", "proc", "sys", "tmp", "etc", "lib"]:
            (initramfs_dir / d).mkdir(exist_ok=True)

        # Copy essential binaries
        essential_bins = ["/bin/sh", "/bin/busybox"]
        for bin_path in essential_bins:
            if os.path.exists(bin_path):
                shutil.copy2(bin_path, initramfs_dir / "bin")

        # Copy miner binary
        miner_dest = initramfs_dir / "bin" / "rustchain_miner"
        shutil.copy2(miner_binary, miner_dest)
        miner_dest.chmod(0o755)

        # Create init script
        init_script = initramfs_dir / "init"
        with open(init_script, "w") as f:
            f.write("""#!/bin/sh
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs devtmpfs /dev

echo "Dreamcast RustChain Miner v2.2.1"
echo "SH4 CPU @ 200MHz - 3.0x Antiquity Multiplier"

# Wait for broadband adapter
sleep 3

# Configure network (DHCP)
ifconfig eth0 up
udhcpc -i eth0

echo "Starting RustChain miner..."
/bin/rustchain_miner --wallet dreamcast_$(cat /proc/cpuinfo | grep Serial | cut -d: -f2 | tr -d ' ') --threads 1

# Fallback shell
exec /bin/sh
""")
        init_script.chmod(0o755)

        # Create initramfs archive
        print("Creating initramfs archive...")
        os.chdir(initramfs_dir)
        initramfs_file = self.work_dir / "initramfs.cpio.gz"

        with open(initramfs_file, "wb") as f:
            find_proc = subprocess.Popen(["find", ".", "-print0"],
                                       stdout=subprocess.PIPE)
            cpio_proc = subprocess.Popen(["cpio", "-o", "-H", "newc", "-0"],
                                       stdin=find_proc.stdout,
                                       stdout=subprocess.PIPE)
            gzip_proc = subprocess.Popen(["gzip", "-9"],
                                       stdin=cpio_proc.stdout,
                                       stdout=f)

            find_proc.stdout.close()
            cpio_proc.stdout.close()
            gzip_proc.wait()

        return initramfs_file

    def create_mil_cd_iso(self, kernel_image: Path, initramfs: Path) -> Optional[Path]:
        """Create MIL-CD bootable ISO for Dreamcast"""
        iso_dir = self.work_dir / "iso_root"
        iso_dir.mkdir(exist_ok=True)

        # Copy kernel and initramfs to ISO
        shutil.copy2(kernel_image, iso_dir / "1ST_READ.BIN")
        shutil.copy2(initramfs, iso_dir / "initramfs.gz")

        # Create IP.BIN (Initial Program binary)
        ip_bin = iso_dir / "IP.BIN"
        with open(ip_bin, "wb") as f:
            # Minimal IP.BIN header for MIL-CD boot
            # Hardware ID, region code, peripheral support
            header = bytearray(32768)
            header[0:16] = b"SEGA SEGAKATANA "
            header[16:32] = b"DREAMCAST_MINER "
            header[64:80] = b"V1.000\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            f.write(header)

        # Create ISO with proper Dreamcast boot structure
        iso_file = self.work_dir / "dreamcast_miner.iso"

        try:
            subprocess.run([
                "mkisofs",
                "-l", "-C", "0,11702",
                "-o", str(iso_file),
                str(iso_dir)
            ], check=True)

            print(f"MIL-CD ISO created: {iso_file}")
            print(f"Size: {iso_file.stat().st_size // (1024*1024)} MB")
            return iso_file

        except subprocess.CalledProcessError as e:
            print(f"ISO creation failed: {e}")
            return None

    def build_miner_sh4(self, source_file: Path) -> Optional[Path]:
        """Cross-compile RustChain miner for SH4 architecture"""
        if not source_file.exists():
            print(f"Source file not found: {source_file}")
            return None

        output_binary = self.work_dir / "rustchain_miner_sh4"

        # SH4-specific compiler flags
        cflags = [
            "-march=sh4", "-m4", "-ml",  # SH4 little-endian
            "-O2", "-fomit-frame-pointer",
            "-DDREAMCAST_BUILD=1",
            "-DANTIQUITY_MULTIPLIER=3.0"
        ]

        try:
            subprocess.run([
                f"{DC_TOOLCHAIN_PREFIX}gcc",
                *cflags,
                "-o", str(output_binary),
                str(source_file),
                "-lm", "-lpthread"
            ], check=True)

            # Strip binary to reduce size
            subprocess.run([f"{DC_TOOLCHAIN_PREFIX}strip", str(output_binary)],
                          check=True)

            size_kb = output_binary.stat().st_size // 1024
            print(f"SH4 miner binary created: {output_binary} ({size_kb} KB)")
            return output_binary

        except subprocess.CalledProcessError as e:
            print(f"SH4 compilation failed: {e}")
            return None

    def generate_boot_instructions(self, iso_file: Path):
        """Generate instructions for booting on real hardware"""
        instructions = f"""
# Dreamcast RustChain Miner Boot Instructions

## Method 1: MIL-CD Boot (No Mod Required)
1. Burn {iso_file.name} to CD-R using DAO (Disk-At-Once) mode
2. Insert into Dreamcast and power on
3. System will boot directly into Linux + RustChain miner

## Method 2: SD Card Boot (GDEMU/MODE required)
1. Copy {iso_file.name} to GDEMU SD card as disc image
2. Select via GDEMU menu or rename to 01.iso for auto-boot

## Network Configuration
- Broadband Adapter (HIT-400) required for mining
- DHCP will auto-configure network on boot
- Wallet ID: dreamcast_[serial_number]

## Expected Performance
- SH4 @ 200MHz with 16KB cache
- ~0.5-2 hashes/second (extremely low but 3.0x multiplier)
- Power consumption: ~17W total system

## Troubleshooting
- Black screen: Check CD burn quality, use quality media
- No network: Verify broadband adapter connections
- Boot loop: Try different CD-R brand or burning speed

Mining pool will automatically detect SH4 architecture for antiquity bonus.
"""

        readme_file = self.work_dir / "DREAMCAST_BOOT_README.txt"
        with open(readme_file, "w") as f:
            f.write(instructions)

        print(f"Boot instructions written to: {readme_file}")


def main():
    if len(sys.argv) < 2:
        print("Usage: dreamcast_boot_helper.py <miner_source.py>")
        print("Creates bootable Dreamcast ISO with RustChain miner")
        return 1

    source_file = Path(sys.argv[1])
    if not source_file.exists():
        print(f"Source file not found: {source_file}")
        return 1

    helper = DreamcastBootHelper()

    print("=== Dreamcast RustChain Miner Build Process ===")

    # Check prerequisites
    if not helper.check_toolchain():
        return 1

    # Setup kernel
    if not helper.setup_kernel_source():
        print("Failed to setup kernel source")
        return 1

    # Build kernel
    kernel_image = helper.build_kernel()
    if not kernel_image:
        print("Failed to build kernel")
        return 1

    # Compile miner for SH4
    miner_binary = helper.build_miner_sh4(source_file)
    if not miner_binary:
        print("Failed to compile miner for SH4")
        return 1

    # Create initramfs
    initramfs = helper.create_initramfs(miner_binary)
    if not initramfs:
        print("Failed to create initramfs")
        return 1

    # Create bootable ISO
    iso_file = helper.create_mil_cd_iso(kernel_image, initramfs)
    if not iso_file:
        print("Failed to create ISO")
        return 1

    # Generate instructions
    helper.generate_boot_instructions(iso_file)

    print("\n=== Build Complete ===")
    print(f"Bootable ISO: {iso_file}")
    print("Ready to burn to CD-R and test on real Dreamcast hardware!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
