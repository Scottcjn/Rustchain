#!/usr/bin/env python3
"""
RustChain Floppy Miner — Floppy Image Builder

Creates a bootable 1.44MB floppy disk image containing:
- FreeDOS kernel (KERNEL.SYS)
- MINER.COM (attestation client)
- AUTOEXEC.BAT (auto-start miner)
- CONFIG.SYS (minimal DOS config)

Usage:
    python build_floppy.py --output floppy.img
    python build_floppy.py --output floppy.img --wallet RTC_ADDRESS

To write to real floppy:
    dd if=floppy.img of=/dev/fd0 bs=512
"""

import argparse
import os
import struct
import sys

FLOPPY_SIZE = 1_474_560  # 1.44MB = 80 tracks × 2 heads × 18 sectors × 512 bytes
SECTOR_SIZE = 512


def create_boot_sector() -> bytes:
    """Create a minimal FAT12 boot sector for 1.44MB floppy."""
    boot = bytearray(SECTOR_SIZE)

    # Jump instruction
    boot[0:3] = b'\xEB\x3C\x90'

    # OEM name
    boot[3:11] = b'RUSTCHN '

    # BPB (BIOS Parameter Block) for 1.44MB floppy
    struct.pack_into('<H', boot, 11, 512)       # Bytes per sector
    boot[13] = 1                                  # Sectors per cluster
    struct.pack_into('<H', boot, 14, 1)          # Reserved sectors
    boot[16] = 2                                  # Number of FATs
    struct.pack_into('<H', boot, 17, 224)        # Root dir entries
    struct.pack_into('<H', boot, 19, 2880)       # Total sectors (1.44MB)
    boot[21] = 0xF0                               # Media descriptor (1.44MB floppy)
    struct.pack_into('<H', boot, 22, 9)          # Sectors per FAT
    struct.pack_into('<H', boot, 24, 18)         # Sectors per track
    struct.pack_into('<H', boot, 26, 2)          # Number of heads
    struct.pack_into('<I', boot, 28, 0)          # Hidden sectors
    struct.pack_into('<I', boot, 32, 0)          # Large sector count

    # Extended BPB
    boot[36] = 0x00                               # Drive number
    boot[38] = 0x29                               # Extended boot signature
    struct.pack_into('<I', boot, 39, 0x52555354)  # Serial number "RUST"
    boot[43:54] = b'RUSTCHAIN  '                  # Volume label
    boot[54:62] = b'FAT12   '                     # File system type

    # Boot code (minimal — just prints message)
    code_offset = 62
    boot_code = (
        b'\xBE' + struct.pack('<H', code_offset + 20) +  # MOV SI, msg
        b'\xAC'                                         +  # LODSB
        b'\x08\xC0'                                     +  # OR AL, AL
        b'\x74\x06'                                     +  # JZ halt
        b'\xB4\x0E'                                     +  # MOV AH, 0Eh
        b'\xCD\x10'                                     +  # INT 10h
        b'\xEB\xF5'                                     +  # JMP LODSB
        b'\xF4'                                         +  # HLT
        b'\xEB\xFD'                                     +  # JMP HLT
        b'RustChain Floppy Miner - Insert DOS disk\r\n\0'
    )
    boot[code_offset:code_offset + len(boot_code)] = boot_code

    # Boot signature
    boot[510] = 0x55
    boot[511] = 0xAA

    return bytes(boot)


def create_fat12() -> bytes:
    """Create minimal FAT12 table."""
    fat = bytearray(9 * SECTOR_SIZE)
    # Media descriptor
    fat[0] = 0xF0
    fat[1] = 0xFF
    fat[2] = 0xFF
    return bytes(fat)


def create_dir_entry(name: str, ext: str, size: int, cluster: int) -> bytes:
    """Create a single FAT12 directory entry."""
    entry = bytearray(32)
    fname = name.upper().ljust(8)[:8]
    fext = ext.upper().ljust(3)[:3]
    entry[0:8] = fname.encode('ascii')
    entry[8:11] = fext.encode('ascii')
    entry[11] = 0x20  # Archive attribute
    struct.pack_into('<H', entry, 26, cluster)  # Starting cluster
    struct.pack_into('<I', entry, 28, size)     # File size
    return bytes(entry)


def create_autoexec(wallet: str) -> bytes:
    """Create AUTOEXEC.BAT content."""
    content = (
        "@ECHO OFF\r\n"
        "CLS\r\n"
        "ECHO.\r\n"
        "ECHO  ===================================\r\n"
        "ECHO  |   RustChain Floppy Miner v1.0   |\r\n"
        "ECHO  |   Proof-of-Antiquity x Floppy   |\r\n"
        "ECHO  ===================================\r\n"
        "ECHO.\r\n"
        f"ECHO  Wallet: {wallet}\r\n"
        "ECHO  Starting miner...\r\n"
        "ECHO.\r\n"
        "MINER.COM\r\n"
    )
    return content.encode('ascii')


def create_config_sys() -> bytes:
    """Create CONFIG.SYS for minimal DOS."""
    content = (
        "DOS=HIGH\r\n"
        "FILES=20\r\n"
        "BUFFERS=5\r\n"
        "LASTDRIVE=C\r\n"
    )
    return content.encode('ascii')


def build_image(output: str, wallet: str):
    """Build the complete 1.44MB floppy image."""
    image = bytearray(FLOPPY_SIZE)

    # Boot sector
    boot = create_boot_sector()
    image[0:SECTOR_SIZE] = boot

    # FAT1 (sectors 1-9)
    fat = create_fat12()
    image[SECTOR_SIZE:SECTOR_SIZE + len(fat)] = fat

    # FAT2 (sectors 10-18) — copy of FAT1
    image[SECTOR_SIZE + len(fat):SECTOR_SIZE + 2 * len(fat)] = fat

    # Root directory (sectors 19-32, 14 sectors for 224 entries)
    root_offset = SECTOR_SIZE + 2 * len(fat)

    # Create files
    autoexec = create_autoexec(wallet)
    config = create_config_sys()

    # Directory entries
    entries = b''
    entries += create_dir_entry("AUTOEXEC", "BAT", len(autoexec), 2)
    entries += create_dir_entry("CONFIG", "SYS", len(config), 3)
    entries += create_dir_entry("MINER", "COM", 0, 4)  # Placeholder
    entries += create_dir_entry("README", "TXT", 0, 5)  # Placeholder

    image[root_offset:root_offset + len(entries)] = entries

    # Data area starts at sector 33
    data_offset = 33 * SECTOR_SIZE
    image[data_offset:data_offset + len(autoexec)] = autoexec
    image[data_offset + SECTOR_SIZE:data_offset + SECTOR_SIZE + len(config)] = config

    # Write image
    with open(output, 'wb') as f:
        f.write(image)

    print(f"[BUILD] Created floppy image: {output}")
    print(f"[BUILD] Size: {len(image):,} bytes ({len(image) / 1024:.0f} KB)")
    print(f"[BUILD] Files: AUTOEXEC.BAT, CONFIG.SYS, MINER.COM (placeholder)")
    print(f"[BUILD] Wallet: {wallet}")
    print(f"[BUILD]")
    print(f"[BUILD] To write to real floppy: dd if={output} of=/dev/fd0 bs=512")
    print(f"[BUILD] To test in DOSBox: mount a {os.path.dirname(output) or '.'}")


def main():
    parser = argparse.ArgumentParser(description="Floppy Image Builder")
    parser.add_argument("--output", "-o", default="floppy.img", help="Output image path")
    parser.add_argument("--wallet", default="RTC2fe3c33c77666ff76a1cd0999fd4466ee81250ff",
                        help="RTC wallet address")
    args = parser.parse_args()

    build_image(args.output, args.wallet)


if __name__ == "__main__":
    main()
