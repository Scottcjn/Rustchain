# Linux Kernel Build for Sega Dreamcast (SH4)

Reference kernel build instructions for Dreamcast Linux with the RustChain miner.

## Build Prerequisites

```bash
# Debian/Ubuntu
sudo apt-get install gcc-sh4-linux-gnu binutils-sh4-linux-gnu

# Clone mainline kernel
git clone https://github.com/torvalds/linux.git
cd linux
git checkout -b dreamcast origin/sh-latest 2>/dev/null || git checkout -b dreamcast
```

## Configure for Dreamcast

```bash
make ARCH=sh CROSS_COMPILE=sh4-linux-gnu- dreamcast_defconfig
```

Key configs: `CONFIG_SH_DREAMCAST=y`, `CONFIG_SH7750=y`, `CONFIG_SH_FPU=y`,
`CONFIG_8139CP=y` (BBA), `CONFIG_BLK_DEV_INITRD=y`

## Build Kernel

```bash
make ARCH=sh CROSS_COMPILE=sh4-linux-gnu- -j$(nproc)
# Output: arch/sh/boot/zImage
```

## Create initramfs with miner

```bash
mkdir -p initramfs/{bin,sbin,etc,proc,sys}
cp /path/to/dreamcast_miner initramfs/bin/
# Add busybox static binary
cat > initramfs/init << 'EOF'
#!/bin/sh
mount -t proc none /proc
mount -t sysfs none /sys
udhcpc -i eth0
/miner --wallet "${WALLET:-dreamcast-default}"
EOF
chmod +x initramfs/init
find initramfs -print0 | cpio -ov --format=newc | gzip > initramfs.gz
```

## Boot Methods

1. **GDEMU/SD**: Copy cdi4cc ISO to SD card, boot GDEMU
2. **MIL-CD**: Burn ISO to CD-R, use homebrew exploit

## References

- Linux SH4: https://www.kernel.org/doc/html/latest/sh/
- KallistiOS: http://gamedev.allusion.net/softprj/kos/
- Marcus Comstedt's DC pages: http://mc.pp.se/dc/
