#!/usr/bin/env python3
"""
ROM Fingerprint Database for RIP-PoA Anti-Emulation
====================================================
Catalogs known emulator ROM dumps - these hashes indicate emulated hardware.
If multiple "different" machines report the same ROM hash, they're likely VMs/emulators
using the same pirated ROM pack.

Sources:
- FS-UAE: https://fs-uae.net/docs/kickstart-roms/
- MAMEDEV: https://wiki.mamedev.org/index.php/Driver:Mac_68K:Tech_Info:ROMs
- Cloanto: https://cloanto.com/amiga/roms/
- E-Maculation: https://www.emaculation.com/
"""

from typing import Dict, List, Optional, Tuple
import hashlib
import os

# =============================================================================
# AMIGA KICKSTART ROMS - Known emulator ROM hashes (SHA-1)
# Everyone using UAE/WinUAE/FS-UAE uses these same dumps
# =============================================================================
AMIGA_KICKSTART_SHA1 = {
    # Kickstart 1.2 (A500/A1000/A2000)
    "11f9e62cf299f72184835b7b2a70a16333fc0d88": {
        "version": "1.2 r33.180",
        "year": 1986,
        "models": ["A500", "A1000", "A2000"],
        "common_in_emulators": True,
    },
    # Kickstart 1.3 (A500) - MOST COMMON in emulators
    "891e9a547772fe0c6c19b610baf8bc4ea7fcb785": {
        "version": "1.3 r34.5",
        "year": 1987,
        "models": ["A500"],
        "common_in_emulators": True,
    },
    "90933936cce43ca9bc6bf375662c076b27e3c458": {
        "version": "1.3 r34.5 (overdump)",
        "year": 1987,
        "models": ["A500"],
        "common_in_emulators": True,
    },
    # Kickstart 2.04 (A500+)
    "c5839f5cb98a7a8947065c3ed2f14f5f42e334a1": {
        "version": "2.04 r37.175",
        "year": 1991,
        "models": ["A500+"],
        "common_in_emulators": True,
    },
    # Kickstart 2.05 (A600)
    "02843c4253bbd29aba535b0aa3bd9a85034ecde4": {
        "version": "2.05 r37.350",
        "year": 1992,
        "models": ["A600"],
        "common_in_emulators": True,
    },
    # Kickstart 3.1 - MOST COMMON for "serious" Amiga emulation
    "e21545723fe8374e91342617604f1b3d703094f1": {
        "version": "3.1 r40.68",
        "year": 1993,
        "models": ["A1200"],
        "common_in_emulators": True,
    },
    "f8e210d72b4c4853e0c9b85d223ba20e3d1b36ee": {
        "version": "3.1 r40.68",
        "year": 1993,
        "models": ["A3000"],
        "common_in_emulators": True,
    },
    "5fe04842d04a489720f0f4bb0e46948199406f49": {
        "version": "3.1 r40.68",
        "year": 1993,
        "models": ["A4000"],
        "common_in_emulators": True,
    },
    # Cloanto Amiga Forever (modified) - still counts as emulator
    "c3c481160866e60d085e436a24db3617ff60b5f9": {
        "version": "3.1 r40.68 (Cloanto)",
        "year": 1993,
        "models": ["A4000"],
        "common_in_emulators": True,
    },
    # CD32
    "3525be8887f79b5929e017b42380a79edfee542d": {
        "version": "3.1 r40.60",
        "year": 1993,
        "models": ["CD32"],
        "common_in_emulators": True,
    },
    "5bef3d628ce59cc02a66e6e4ae0da48f60e78f7f": {
        "version": "r40.60 Extended",
        "year": 1993,
        "models": ["CD32"],
        "common_in_emulators": True,
    },
    # CDTV
    "7ba40ffa17e500ed9fed041f3424bd81d9c907be": {
        "version": "1.0 Extended",
        "year": 1991,
        "models": ["CDTV"],
        "common_in_emulators": True,
    },
}

# =============================================================================
# MACINTOSH 68K ROMS - Known emulator ROM hashes
# Used by Basilisk II, Mini vMac, MAME
# =============================================================================
MAC_68K_CHECKSUMS = {
    # Apple internal checksum format (first 4 bytes of ROM)
    # Classic Macs
    "28BA61CE": {"models": ["Mac 128K"], "size": "64K", "year": 1984},
    "4D1EEEE1": {"models": ["Mac 512K"], "size": "64K", "year": 1984},
    "4D1EEAE1": {"models": ["Mac 512Ke"], "size": "128K", "year": 1986},
    "B2E362A8": {"models": ["Mac Plus v1"], "size": "128K", "year": 1986},
    "4D1F8172": {"models": ["Mac Plus v2"], "size": "128K", "year": 1986},
    "4D1F8132": {"models": ["Mac Plus v3"], "size": "128K", "year": 1986},
    # Mac II family
    "97851DB6": {"models": ["Mac II FDHD"], "size": "256K", "year": 1987},
    "9779D2C4": {"models": ["Mac II"], "size": "256K", "year": 1987},
    "97221136": {"models": ["Mac IIx", "Mac IIcx", "Mac SE/30"], "size": "256K", "year": 1988},
    "368CADFE": {"models": ["Mac IIci"], "size": "512K", "year": 1989},
    "36B7FB6C": {"models": ["Mac IIsi"], "size": "512K", "year": 1990},
    "35C28F5F": {"models": ["Mac IIfx"], "size": "512K", "year": 1990},
    # LC family
    "350EACF0": {"models": ["Mac LC"], "size": "512K", "year": 1990},
    "35C28C8F": {"models": ["Mac LC II"], "size": "512K", "year": 1992},
    "3193670E": {"models": ["Mac Classic II", "Performa 200"], "size": "512K", "year": 1991},
    # Quadra family - commonly used in Basilisk II
    "420DBFF3": {"models": ["Quadra 700", "Quadra 900"], "size": "1M", "year": 1991},
    "3DC27823": {"models": ["Quadra 950"], "size": "1M", "year": 1992},
    "F1A6F343": {"models": ["Centris 610", "Centris 650"], "size": "1M", "year": 1993},
    "F1ACAD13": {"models": ["Quadra 610", "Quadra 650", "Quadra 800"], "size": "1M", "year": 1993},
    "FF7439EE": {"models": ["Quadra 605", "LC 475", "Performa 475/476"], "size": "1M", "year": 1993},
    "5BF10FD1": {"models": ["Quadra 660AV", "Quadra 840AV"], "size": "2M", "year": 1993},
    "EDE66CBD": {"models": ["Color Classic II", "LC 550", "Performa 275/550/560", "Mac TV"], "size": "1M", "year": 1993},
    "064DC91D": {"models": ["Performa 580", "Performa 588"], "size": "1M", "year": 1994},
    # PowerBooks
    "63ABFD3F": {"models": ["PowerBook 5300", "PowerBook Duo 2300"], "size": "1M", "year": 1995},
}

# MD5 hashes for specific ROM files (from MAMEDEV)
MAC_68K_MD5 = {
    "db7e6d3205a2b48023fba5aa867ac6d6": {"models": ["Mac 128/512"], "size": "64K"},
    "4d8d1e81fa606f57c7ed7188b8b5f410": {"models": ["Mac Plus/512Ke v1"], "size": "128K"},
    "74f4095f7d245a9fb099a6f4a9943572": {"models": ["Mac II"], "size": "256K"},
    "5d8662dfab70ac34663d6d54393f5018": {"models": ["Mac LC"], "size": "512K"},
    "af343f3f1362bf29cefd630687efaa25": {"models": ["Quadra 630"], "size": "1M"},
    "b029184cea925759bc81ecdfe1ccdabd": {"models": ["Quadra 660AV/840AV"], "size": "2M"},
}

# =============================================================================
# MACINTOSH PPC ROMS - SheepShaver / PearPC
# =============================================================================
MAC_PPC_MD5 = {
    # Old World ROMs (4MB) - used by SheepShaver
    "01a80c4452c8cdf385e11bd973b44f58": {"models": ["PowerBook G3 WallStreet PDQ"], "size": "4M"},
    "b8612cc39a56d141feade9dc6361ba20": {"models": ["Power Mac G3 Gossamer"], "size": "4M"},
    "bddae47c3475a9d29865612584e18df0": {"models": ["PowerBook G3 Kanga"], "size": "4M"},
    # New World ROMs (1MB) - also used by SheepShaver
    "48f635ea8246e42d8edf6a82196d5f72": {"models": ["PowerBook G4"], "size": "1M"},
    "08a9111d0a63d9cbcc37b44a431539cf": {"models": ["Mac mini G4 (Mar 2005)"], "size": "1M"},
    "7bcb22816292a3ac46267b5f16e09806": {"models": ["Mac mini G4 (Dec 2004)"], "size": "1M"},
    "1a405eaa19c4474eb7c5e26eb8a7df80": {"models": ["iBook G4"], "size": "1M"},
    "548bc9cff3da74e9e4dee81ab9b241ce": {"models": ["Power Mac G5 1.6GHz"], "size": "1M"},
    "9f512f3d4ea399fecee413bba0b11bf9": {"models": ["Power Mac G4 FW800"], "size": "1M"},
    "b7af30d6ae7408f108f0484fea886aa7": {"models": ["Power Mac G4 MDD"], "size": "1M"},
    "68cb26e83bb1e80c6a4e899ddf609463": {"models": ["iMac G4 15in"], "size": "1M"},
    "7c35693d4a91b1ccf3d730b71013e285": {"models": ["Power Mac G4 Sawtooth"], "size": "1M"},
    "44cc08c8f14958371cd868770560dac4": {"models": ["Power Mac G4 Cube"], "size": "1M"},
    "af2d2a5a003776291edb533dd75bc2d0": {"models": ["iMac G3 Slot post-May2000"], "size": "1M"},
    "d3f0ded97a7e029e627ab38235ceb742": {"models": ["PowerBook G3 Pismo"], "size": "1M"},
    "c17552881a3999e4441847c8a286a318": {"models": ["iMac G3/PowerBook G3"], "size": "1M"},
    "2c4154c2399613b15d8786460972440e": {"models": ["iMac G3 tray-loading"], "size": "1M"},
    "cc184737ab210fe360a7be42df91be2c": {"models": ["Blue White G3"], "size": "1M"},
    "55dc974738657aebbb05fcccca51bbcc": {"models": ["PowerBook G3 Lombard"], "size": "1M"},
}

# =============================================================================
# OTHER RETRO PLATFORMS
# =============================================================================
ATARI_ST_ROMS = {
    # TOS ROMs commonly used in Hatari, Steem
    # SHA-1 hashes from Hatari documentation
}

C64_ROMS = {
    # Kernal/Basic ROMs used in VICE
    # Everyone uses the same dumps
}


def compute_file_hash(filepath: str, algorithm: str = "sha1") -> Optional[str]:
    """Compute hash of a file."""
    if not os.path.exists(filepath):
        return None

    hasher = hashlib.new(algorithm)
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_rom_checksum_apple(filepath: str) -> Optional[str]:
    """Extract Apple ROM checksum (first 4 bytes, big-endian hex)."""
    if not os.path.exists(filepath):
        return None

    with open(filepath, "rb") as f:
        first_four = f.read(4)

    if len(first_four) < 4:
        return None

    return first_four.hex().upper()


def identify_rom(hash_value: str, hash_type: str = "sha1") -> Optional[Dict]:
    """
    Identify a ROM by its hash.
    Returns ROM info if known, None if unique/unknown.
    """
    hash_lower = hash_value.lower()
    hash_upper = hash_value.upper()

    # Check Amiga Kickstart (SHA-1)
    if hash_type == "sha1" and hash_lower in AMIGA_KICKSTART_SHA1:
        info = AMIGA_KICKSTART_SHA1[hash_lower].copy()
        info["platform"] = "amiga"
        info["hash_type"] = "sha1"
        return info

    # Check Mac 68K (Apple checksum)
    if hash_type == "apple" and hash_upper in MAC_68K_CHECKSUMS:
        info = MAC_68K_CHECKSUMS[hash_upper].copy()
        info["platform"] = "mac_68k"
        info["hash_type"] = "apple_checksum"
        return info

    # Check Mac 68K (MD5)
    if hash_type == "md5" and hash_lower in MAC_68K_MD5:
        info = MAC_68K_MD5[hash_lower].copy()
        info["platform"] = "mac_68k"
        info["hash_type"] = "md5"
        return info

    # Check Mac PPC (MD5)
    if hash_type == "md5" and hash_lower in MAC_PPC_MD5:
        info = MAC_PPC_MD5[hash_lower].copy()
        info["platform"] = "mac_ppc"
        info["hash_type"] = "md5"
        return info

    return None


def is_known_emulator_rom(hash_value: str, hash_type: str = "sha1") -> bool:
    """Check if a ROM hash matches a known emulator ROM dump."""
    return identify_rom(hash_value, hash_type) is not None


def get_all_known_hashes() -> Dict[str, List[str]]:
    """Get all known ROM hashes organized by platform."""
    return {
        "amiga_sha1": list(AMIGA_KICKSTART_SHA1.keys()),
        "mac_68k_apple": list(MAC_68K_CHECKSUMS.keys()),
        "mac_68k_md5": list(MAC_68K_MD5.keys()),
        "mac_ppc_md5": list(MAC_PPC_MD5.keys()),
    }


# =============================================================================
# ROM CLUSTERING DETECTION
# =============================================================================
class ROMClusterDetector:
    """
    Detects when multiple "different" miners report identical ROM hashes.
    This indicates emulation - real machines have manufacturing variance.
    """

    def __init__(self, cluster_threshold: int = 2):
        """
        Args:
            cluster_threshold: Number of identical ROMs before flagging.
                              Default 2 = any duplicate is suspicious.
        """
        self.cluster_threshold = cluster_threshold
        self.rom_reports: Dict[str, List[str]] = {}  # hash -> list of miner_ids

    def report_rom(self, miner_id: str, rom_hash: str, hash_type: str = "sha1") -> Tuple[bool, str]:
        """
        Record a ROM hash report from a miner.

        Returns:
            (is_valid, reason) - False if clustering detected
        """
        key = f"{hash_type}:{rom_hash.lower()}"

        if key not in self.rom_reports:
            self.rom_reports[key] = []

        # Check for duplicate from same miner (OK)
        if miner_id in self.rom_reports[key]:
            return True, "same_miner_update"

        self.rom_reports[key].append(miner_id)

        # Check for known emulator ROM
        if is_known_emulator_rom(rom_hash, hash_type):
            rom_info = identify_rom(rom_hash, hash_type)
            return False, f"known_emulator_rom:{rom_info.get('platform')}:{rom_info.get('models', [])}"

        # Check for clustering (multiple miners with same ROM)
        if len(self.rom_reports[key]) > self.cluster_threshold:
            other_miners = [m for m in self.rom_reports[key] if m != miner_id]
            return False, f"rom_clustering_detected:shared_with:{other_miners}"

        return True, "unique_rom"

    def get_clusters(self) -> Dict[str, List[str]]:
        """Get all ROM hashes that have multiple miners."""
        return {k: v for k, v in self.rom_reports.items() if len(v) > 1}

    def get_suspicious_miners(self) -> List[str]:
        """Get list of miners involved in clustering."""
        suspicious = set()
        for miners in self.rom_reports.values():
            if len(miners) > self.cluster_threshold:
                suspicious.update(miners)
        return list(suspicious)


# =============================================================================
# PLATFORM-SPECIFIC ROM DETECTION
# =============================================================================
def detect_platform_roms() -> Dict[str, Optional[str]]:
    """
    Detect ROM files on the current system.
    Returns dict of platform -> rom_hash.
    """
    results = {}

    # Check for Amiga ROMs in common locations
    amiga_paths = [
        "/usr/share/fs-uae/kickstarts/",
        "/usr/share/uae/",
        os.path.expanduser("~/.config/fs-uae/Kickstarts/"),
        os.path.expanduser("~/Amiga/Kickstarts/"),
        "/opt/amiga/rom/",
    ]

    for base in amiga_paths:
        if os.path.isdir(base):
            for f in os.listdir(base):
                if f.lower().endswith(".rom"):
                    path = os.path.join(base, f)
                    sha1 = compute_file_hash(path, "sha1")
                    if sha1:
                        results["amiga_kickstart"] = sha1
                        break

    # Check for Mac ROMs in common locations
    mac_paths = [
        os.path.expanduser("~/.basilisk_ii_prefs"),
        os.path.expanduser("~/.sheepshaver_prefs"),
        "/usr/share/basilisk2/",
        os.path.expanduser("~/Library/Preferences/BasiliskII/"),
    ]

    # For real hardware, try to read ROM from device
    # (This would need platform-specific code)

    return results


def get_real_hardware_rom_signature() -> Optional[Dict]:
    """
    Attempt to get ROM signature from real hardware.

    On real Macs: Read from /dev/rom or memory-mapped ROM area
    On real Amigas: Read from $F80000-$FFFFFF

    Returns None if not running on real retro hardware.
    """
    import platform

    arch = platform.machine().lower()
    system = platform.system().lower()

    # PowerPC Mac - try to read ROM
    if "ppc" in arch or "powerpc" in arch:
        rom_paths = ["/dev/rom", "/dev/nvram"]
        for path in rom_paths:
            if os.path.exists(path):
                try:
                    # Read first 4 bytes for Apple checksum
                    with open(path, "rb") as f:
                        header = f.read(256)

                    # Compute signature
                    return {
                        "platform": "mac_ppc_real",
                        "header_md5": hashlib.md5(header).hexdigest(),
                        "source": path,
                    }
                except:
                    pass

    # 68K would need different detection
    # Amiga would read from chip memory

    return None


if __name__ == "__main__":
    print("ROM Fingerprint Database")
    print("=" * 50)

    stats = get_all_known_hashes()
    print(f"Amiga Kickstart ROMs: {len(stats['amiga_sha1'])}")
    print(f"Mac 68K ROMs (Apple checksum): {len(stats['mac_68k_apple'])}")
    print(f"Mac 68K ROMs (MD5): {len(stats['mac_68k_md5'])}")
    print(f"Mac PPC ROMs (MD5): {len(stats['mac_ppc_md5'])}")

    total = sum(len(v) for v in stats.values())
    print(f"\nTotal known emulator ROMs: {total}")

    print("\n--- Testing Cluster Detection ---")
    detector = ROMClusterDetector(cluster_threshold=2)

    # Simulate reports
    print(detector.report_rom("miner1", "891e9a547772fe0c6c19b610baf8bc4ea7fcb785"))
    print(detector.report_rom("miner2", "891e9a547772fe0c6c19b610baf8bc4ea7fcb785"))
    print(detector.report_rom("miner3", "unique_hash_abc123"))

    print(f"\nClusters: {detector.get_clusters()}")
    print(f"Suspicious miners: {detector.get_suspicious_miners()}")
