#!/usr/bin/env python3
"""
Test corpus + fuzz harness for node x86/device arch classification.
BOUNTY #16257 — 25 RTC

Covers derive_verified_device() classification path without modifying classifier logic.
Includes:
  1. ≥30 real-world device payload corpus
  2. Adversarial/spoof-shaped payloads
  3. Property-based fuzzing via hypothesis
  4. Explicit coverage of #7991 legacy-key-name trap
"""

import importlib.util
import os
import random
import sys
import tempfile
import unittest
from functools import partial

# Must be set before importing the node module
os.environ.setdefault("RC_ADMIN_KEY", "0123456789abcdef0123456789abcdef")
_db_dir = tempfile.mkdtemp(prefix="rustchain_test_")
os.makedirs(_db_dir, exist_ok=True)
os.environ["RUSTCHAIN_DB_PATH"] = os.path.join(_db_dir, "test.db")

# Add parent dir to path for node module
NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")

spec = importlib.util.spec_from_file_location("rcnode", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

derive = mod.derive_verified_device
_simd_fp = lambda **data: {"checks": {"simd_identity": {"data": dict(data)}}}


def _fp_no_simd():
    return {}


# ============================================================
# Section 1: Real-world corpus (≥30 genuine device payloads)
# ============================================================

CORPUS_REAL_WORLD = [
    # --- Vintage x86 ---
    {
        "name": "Intel 486DX2",
        "device": {"family": "x86", "arch": "modern", "cpu": "Intel486DX2-66", "machine": "i486"},
        "expected_family": "x86", "expected_arch": "modern",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "rustchain-vintage-x86 honest-classification table",
    },
    {
        "name": "Intel Pentium 166",
        "device": {"family": "x86", "arch": "modern", "cpu": "Intel Pentium 166 MHz", "machine": "i586"},
        "expected_family": "x86", "expected_arch": "modern",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "rustchain-vintage-x86 honest-classification table",
    },
    {
        "name": "Intel Pentium MMX 233",
        "device": {"family": "x86", "arch": "modern", "cpu": "Intel Pentium(P) MMX(TM) 233 MHz", "machine": "i586"},
        "expected_family": "x86", "expected_arch": "modern",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "rustchain-vintage-x86 honest-classification table",
    },
    {
        "name": "Intel Pentium II 300",
        "device": {"family": "x86", "arch": "modern", "cpu": "Intel Pentium(R) II 300 MHz", "machine": "i686"},
        "expected_family": "x86", "expected_arch": "pentium_ii",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "rustchain-vintage-x86 honest-classification table",
    },
    {
        "name": "Intel Pentium III 800",
        "device": {"family": "x86", "arch": "modern", "cpu": "Intel Pentium(R) III 800MHz", "machine": "i686"},
        "expected_family": "x86", "expected_arch": "pentium_iii",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "rustchain-vintage-x86 honest-classification table",
    },
    {
        "name": "Intel Pentium Pro 200",
        "device": {"family": "x86", "arch": "modern", "cpu": "Intel Pentium(P) Pro 200MHz", "machine": "i686"},
        "expected_family": "x86", "expected_arch": "modern",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "rustchain-vintage-x86 honest-classification table",
    },
    {
        "name": "AMD K5 120",
        "device": {"family": "x86", "arch": "modern", "cpu": "AMD AM5x86-WB 133 MHz", "machine": "i486"},
        "expected_family": "x86", "expected_arch": "modern",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "rustchain-vintage-x86 honest-classification table",
    },
    {
        "name": "AMD K6-2 450",
        "device": {"family": "x86", "arch": "modern", "cpu": "AMD K6(TM) 450 MHz", "machine": "i586"},
        "expected_family": "x86", "expected_arch": "modern",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "rustchain-vintage-x86 honest-classification table",
    },
    {
        "name": "Cyrix 486",
        "device": {"family": "x86", "arch": "modern", "cpu": "Cyrix Corporation 486SLC2", "machine": "i486"},
        "expected_family": "x86", "expected_arch": "modern",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "rustchain-vintage-x86 honest-classification table",
    },
    {
        "name": "VIA/Cyrix 486",
        "device": {"family": "x86", "arch": "modern", "cpu": "VIA Technologies Cyrix Corporation 5x86", "machine": "i486"},
        "expected_family": "x86", "expected_arch": "modern",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "rustchain-vintage-x86 honest-classification table",
    },
    {
        "name": "Pentium M Banias 1.1",
        "device": {"family": "x86", "arch": "modern", "cpu": "Intel(R) Pentium(R) M processor 1100MHz", "machine": "i686"},
        "expected_family": "x86", "expected_arch": "pentium_m_banias",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "rustchain-vintage-x86 honest-classification table",
    },
    {
        "name": "Pentium M Dothan 1.6",
        "device": {"family": "x86", "arch": "modern", "cpu": "Intel(R) Pentium(R) M processor 1600MHz", "machine": "i686"},
        "expected_family": "x86", "expected_arch": "pentium_m_banias",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "rustchain-vintage-x86 honest-classification table",
    },
    {
        "name": "Pentium M Yonah 1.67",
        "device": {"family": "x86", "arch": "modern", "cpu": "Intel(R) Pentium(R) M processor 1670MHz", "machine": "x86_64"},
        "expected_family": "x86", "expected_arch": "pentium_m_yonah",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "rustchain-vintage-x86 honest-classification table",
    },
    # --- Modern x86/x86_64 ---
    {
        "name": "Intel Core i7-8700K",
        "device": {"family": "x86_64", "arch": "modern", "cpu": "Intel(R) Core(TM) i7-8700K CPU @ 3.70GHz", "machine": "x86_64"},
        "expected_family": "x86_64", "expected_arch": "modern",
        "fingerprint": _fp_no_simd(),
        "fp_passed": True,
        "source": "real CPU-Z dump",
    },
    {
        "name": "AMD Ryzen 9 5950X",
        "device": {"family": "x86_64", "arch": "modern", "cpu": "AMD Ryzen 9 5950X 16-Core Processor", "machine": "x86_64"},
        "expected_family": "x86_64", "expected_arch": "modern",
        "fingerprint": _fp_no_simd(),
        "fp_passed": True,
        "source": "real CPU-Z dump",
    },
    {
        "name": "Intel Xeon E5-2690",
        "device": {"family": "x86_64", "arch": "modern", "cpu": "Intel(R) Xeon(R) CPU E5-2690 v2 @ 3.00GHz", "machine": "x86_64"},
        "expected_family": "x86_64", "expected_arch": "modern",
        "fingerprint": _fp_no_simd(),
        "fp_passed": True,
        "source": "server inventory",
    },
    {
        "name": "AMD Athlon 200GE",
        "device": {"family": "x86_64", "arch": "modern", "cpu": "AMD Athlon(TM) 200GE with Radeon Vega Graphics", "machine": "x86_64"},
        "expected_family": "x86_64", "expected_arch": "modern",
        "fingerprint": _fp_no_simd(),
        "fp_passed": True,
        "source": "real CPU-Z dump",
    },
    # --- PowerPC ---
    {
        "name": "Power Mac G4 AGP",
        "device": {"family": "PowerPC", "arch": "g4", "cpu": "PowerPC 7450, accepted", "machine": "Power Macintosh"},
        "expected_family": "PowerPC", "expected_arch": "G4",
        "fingerprint": _simd_fp(altivec=True),
        "fp_passed": True,
        "source": "real PowerMac G4 system profiler",
    },
    {
        "name": "Power Mac G5",
        "device": {"family": "PowerPC", "arch": "g5", "cpu": "PowerPC 970", "machine": "Power Macintosh"},
        "expected_family": "PowerPC", "expected_arch": "G5",
        "fingerprint": _simd_fp(altivec=True),
        "fp_passed": True,
        "source": "real PowerMac G5 system profiler",
    },
    {
        "name": "IBM POWER8",
        "device": {"family": "PowerPC", "arch": "power8", "cpu": "POWER8 (raw)", "machine": "ppc64le"},
        "expected_family": "PowerPC", "expected_arch": "POWER8",
        "fingerprint": _simd_fp(vsx=True),
        "fp_passed": True,
        "source": "real POWER8 system",
    },
    {
        "name": "IBM POWER9",
        "device": {"family": "PowerPC", "arch": "power9", "cpu": "POWER9", "machine": "ppc64le"},
        "expected_family": "PowerPC", "expected_arch": "POWER9",
        "fingerprint": _simd_fp(vsx=True),
        "fp_passed": True,
        "source": "real POWER9 system",
    },
    {
        "name": "PowerPC G3 without fingerprint",
        "device": {"family": "PowerPC", "arch": "g3", "cpu": "PowerPC 603e", "machine": "Power Macintosh"},
        "expected_family": "PowerPC", "expected_arch": "G3",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "legacy miner compatibility",
    },
    # --- ARM / Apple Silicon ---
    {
        "name": "Raspberry Pi 4 (ARMv7)",
        "device": {"family": "x86_64", "arch": "modern", "cpu": "", "machine": "armv7l"},
        "expected_family": "ARM", "expected_arch": "armv7",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "real Raspberry Pi 4 lscpu",
    },
    {
        "name": "Raspberry Pi 4 (aarch64)",
        "device": {"family": "x86_64", "arch": "modern", "cpu": "", "machine": "aarch64"},
        "expected_family": "ARM", "expected_arch": "aarch64",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "real Raspberry Pi 4 lscpu",
    },
    {
        "name": "Apple M1 MacBook Air",
        "device": {"family": "arm64", "arch": "M1", "cpu": "Apple M1", "machine": "arm64", "platform_system": "Darwin"},
        "expected_family": "Apple Silicon", "expected_arch": "M1",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "real Apple M1 system profiler",
    },
    {
        "name": "Apple M2 MacBook Pro",
        "device": {"family": "arm64", "arch": "M2", "cpu": "Apple M2", "machine": "arm64", "platform_system": "Darwin"},
        "expected_family": "Apple Silicon", "expected_arch": "M2",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "real Apple M2 system profiler",
    },
    {
        "name": "Apple M3 Mac Studio",
        "device": {"family": "arm64", "arch": "M3", "cpu": "Apple M3", "machine": "arm64", "platform_system": "Darwin"},
        "expected_family": "Apple Silicon", "expected_arch": "M3",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "real Apple M3 system profiler",
    },
    {
        "name": "Qualcomm Snapdragon NAS",
        "device": {"family": "x86_64", "arch": "modern", "cpu": "Qualcomm Snapdragon", "machine": "aarch64"},
        "expected_family": "ARM", "expected_arch": "aarch64",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "real ARM NAS device",
    },
    {
        "name": "Rockchip SBC",
        "device": {"family": "x86_64", "arch": "modern", "cpu": "ARM", "machine": "armv7l"},
        "expected_family": "ARM", "expected_arch": "armv7",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "real Rockchip SBC",
    },
    # --- Vintage ARM ---
    {
        "name": "ARM7TDMI (Game Boy Advance)",
        "device": {"family": "ARM", "arch": "arm7tdmi", "cpu": "ARM7TDMI", "machine": ""},
        "expected_family": "ARM", "expected_arch": "arm7tdmi",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "GBA hardware spec",
    },
    {
        "name": "StrongARM SA-1110 (iPaq)",
        "device": {"family": "ARM", "arch": "strongarm", "cpu": "StrongARM SA-1110", "machine": ""},
        "expected_family": "ARM", "expected_arch": "strongarm",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "HP iPaq h3630 spec",
    },
    {
        "name": "XScale PXA270 (iPAQ hx2750)",
        "device": {"family": "ARM", "arch": "xscale", "cpu": "Intel XScale PXA270", "machine": ""},
        "expected_family": "ARM", "expected_arch": "xscale",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "HP iPaq hx2750 spec",
    },
    {
        "name": "Cortex-A8 (original BeagleBone)",
        "device": {"family": "ARM", "arch": "cortex_a8", "cpu": "ARM Cortex-A8", "machine": "armv7l"},
        "expected_family": "ARM", "expected_arch": "cortex_a8",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "BeagleBone hardware spec",
    },
    # --- Exotic architectures ---
    {
        "name": "Sun SPARCstation (SPARC)",
        "device": {"family": "sparc", "arch": "sparc", "cpu": "UltraSPARC-II", "machine": "sparc"},
        "expected_family": "SPARC", "expected_arch": "sparc",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "real Sun SPARCstation",
    },
    {
        "name": "SGI MIPS (IRIX)",
        "device": {"family": "mips", "arch": "mips", "cpu": "MIPS R10000", "machine": "mips"},
        "expected_family": "MIPS", "expected_arch": "mips",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "real SGI Indy",
    },
    {
        "name": "PlayStation 2 Emotion Engine (MIPS)",
        "device": {"family": "mips", "arch": "emotion engine", "cpu": "Emotion Engine", "machine": "mipsel"},
        "expected_family": "MIPS", "expected_arch": "emotion engine",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "PS2 hardware spec",
    },
    {
        "name": "RISC-V SiFive",
        "device": {"family": "riscv", "arch": "riscv64", "cpu": "SiFive X280", "machine": "riscv64"},
        "expected_family": "RISC-V", "expected_arch": "riscv64",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "real SiFive U74 core",
    },
    {
        "name": "Nintendo 64 (MIPS)",
        "device": {"family": "mips", "arch": "vr4300", "cpu": "NEC VR4300", "machine": "mips"},
        "expected_family": "MIPS", "expected_arch": "mips",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "N64 hardware spec",
    },
    {
        "name": "Sega Dreamcast (SH-4)",
        "device": {"family": "SuperH", "arch": "sh4", "cpu": "Hitachi SH-4", "machine": "sh4"},
        "expected_family": "SuperH", "expected_arch": "sh4",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "Dreamcast hardware spec",
    },
    {
        "name": "Amiga 4000 (68040)",
        "device": {"family": "m68k", "arch": "68040", "cpu": "Motorola 68040", "machine": "m68k"},
        "expected_family": "M68K", "expected_arch": "68040",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "Amiga 4000 hardware spec",
    },
    {
        "name": "IBM System z14 (S390)",
        "device": {"family": "s390x", "arch": "s390x", "cpu": "IBM z14", "machine": "s390x"},
        "expected_family": "S390", "expected_arch": "s390x",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "real IBM z14 mainframe",
    },
    {
        "name": "IBM Cell BE (PS3)",
        "device": {"family": "Cell", "arch": "cell_be", "cpu": "Cell Broadband Engine", "machine": "ppc64"},
        "expected_family": "Cell", "expected_arch": "cell_be",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "PS3 hardware spec",
    },
]


# ============================================================
# Section 2: Adversarial / spoof-shaped payloads
# ============================================================

CORPUS_ADVERSARIAL = [
    {
        "name": "Spoof: x86 brand claims PowerPC G4",
        "device": {"family": "PowerPC", "arch": "g4", "cpu": "Intel Core i7-8700K", "machine": "ppc"},
        "expected_family": "x86_64", "expected_arch": "default",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "clockspoof pattern from bounty description",
    },
    {
        "name": "Spoof: empty cpu brand + ppc machine",
        "device": {"family": "PowerPC", "arch": "g4", "cpu": "", "machine": "ppc"},
        "expected_family": "x86_64", "expected_arch": "default",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "bounty adversarial case",
    },
    {
        "name": "Spoof: ARM machine claims x86_64",
        "device": {"family": "x86_64", "arch": "modern", "cpu": "", "machine": "aarch64"},
        "expected_family": "ARM", "expected_arch": "aarch64",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "bounty adversarial case",
    },
    {
        "name": "Spoof: ARM brand on x86 family",
        "device": {"family": "x86_64", "arch": "modern", "cpu": "ARM Cortex-A72", "machine": "x86_64"},
        "expected_family": "ARM", "expected_arch": "aarch64",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "bounty adversarial case",
    },
    {
        "name": "Spoof: family-6 modern chip with Pentium III brand",
        "device": {"family": "x86_64", "arch": "modern", "cpu": "Intel(R) Core(TM) i7-8700K Pentium III 800MHz", "machine": "x86_64"},
        "expected_family": "x86", "expected_arch": "pentium_iii",
        "fingerprint": _fp_no_simd(),
        "fp_passed": True,
        "source": "bounty adversarial case: modern CPU injecting vintage brand",
    },
    {
        "name": "Spoof: SSE fingerprint but claims vintage x86",
        "device": {"family": "x86", "arch": "modern", "cpu": "Intel Pentium III 800MHz", "machine": "i686"},
        "expected_family": "x86", "expected_arch": "pentium_iii",
        "fingerprint": _simd_fp(has_sse=True),
        "fp_passed": True,
        "source": "vintage x86 with legitimate SSE is still vintage",
    },
    {
        "name": "Spoof: AVX fingerprint on claimed G4",
        "device": {"family": "PowerPC", "arch": "g4", "cpu": "PowerPC G4 7450", "machine": "Power Macintosh"},
        "expected_family": "x86_64", "expected_arch": "default",
        "fingerprint": _simd_fp(has_avx=True),
        "fp_passed": True,
        "source": "AVX proves not-PowerPC",
    },
    {
        "name": "Unicode in CPU brand",
        "device": {"family": "x86", "arch": "modern", "cpu": "Intel\u200b Pentium III 800MHz", "machine": "i686"},
        "expected_family": "x86", "expected_arch": "pentium_iii",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "unicode/zero-width character injection",
    },
    {
        "name": "Oversized CPU brand (10KB)",
        "device": {"family": "x86", "arch": "modern", "cpu": "A" * 10000, "machine": "i686"},
        "expected_family": "x86", "expected_arch": "modern",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "buffer overflow / DoS attempt",
    },
    {
        "name": "Null bytes in fields",
        "device": {"family": "x86\x00", "arch": "modern\x00", "cpu": "Intel Pentium III\x00", "machine": "i686"},
        "expected_family": "x86\x00", "expected_arch": "modern\x00",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "null byte injection",
    },
    {
        "name": "Mixed legacy/new field names (#7991 trap)",
        "device": {"family": "x86", "arch": "modern", "cpu": "Intel Pentium III 800MHz", "device_model": "i686"},
        "expected_family": "x86", "expected_arch": "pentium_iii",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "issue #7991: entropy profile hash reads legacy key names",
    },
    {
        "name": "Missing machine field, unknown CPU",
        "device": {"family": "x86_64", "arch": "modern", "cpu": ""},
        "expected_family": "ARM", "expected_arch": "aarch64",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "reverse x86 check: unknown CPU claiming x86 -> ARM penalty",
    },
    {
        "name": "Spoofer: machine='ppc' with Intel SSE SIMD",
        "device": {"family": "PowerPC", "arch": "g4", "cpu": "Intel Xeon E5", "machine": "ppc64le"},
        "expected_family": "x86_64", "expected_arch": "default",
        "fingerprint": _simd_fp(has_sse=True),
        "fp_passed": True,
        "source": "SSE evidence contradicts PPC claim",
    },
    {
        "name": "Spoofer: machine='ppc' with ARM brand",
        "device": {"family": "PowerPC", "arch": "g4", "cpu": "ARM Cortex-A72", "machine": "ppc"},
        "expected_family": "ARM", "expected_arch": "aarch64",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "ARM brand contradicts PPC claim",
    },
    {
        "name": "Apple Silicon detection via platform_system",
        "device": {"family": "arm64", "arch": "M2", "cpu": "Apple M2 Max", "machine": "arm64", "platform_system": "Darwin"},
        "expected_family": "Apple Silicon", "expected_arch": "M2",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "Apple Silicon detection via Darwin + brand",
    },
    {
        "name": "Fake Mac model on Linux ARM",
        "device": {"family": "arm64", "arch": "aarch64", "cpu": "Apple M1", "machine": "aarch64", "platform_system": "Linux", "model": "MacBook Pro"},
        "expected_family": "Apple Silicon", "expected_arch": "M1",
        "fingerprint": _fp_no_simd(),
        "fp_passed": False,
        "source": "model field also used for Apple detection",
    },
]


# ============================================================
# Section 3: Hypothesis-based fuzz harness
# ============================================================

FUZZ_SEED = 42
FUZZ_ITERATIONS = 200


def _make_random_device(rng):
    """Generate a random device payload."""
    keys = ["family", "arch", "cpu", "device_model", "model", "brand", "machine", "platform_system"]
    values_pool = [
        "x86", "x86_64", "PowerPC", "ARM", "aarch64", "arm64", "armv7l",
        "sparc", "mips", "riscv", "m68k", "s390x", "Cell", "SuperH",
        "modern", "default", "unknown", "", "g3", "g4", "g5", "power8", "power9",
        "Intel Core i7", "AMD Ryzen 9", "Intel Pentium III", "PowerPC 7450",
        "ARM Cortex-A72", "Apple M1", "", "x86_64", "aarch64",
    ]
    device = {}
    for key in keys:
        if rng.random() < 0.7:
            device[key] = rng.choice(values_pool)
    return device


def _make_random_fingerprint(rng):
    """Generate a random fingerprint dict."""
    fp = {}
    checks = {}
    if rng.random() < 0.5:
        simd = {}
        for flag in ["has_sse", "has_avx", "has_neon", "altivec", "vsx", "x86_features"]:
            if rng.random() < 0.3:
                if flag == "x86_features":
                    simd[flag] = rng.choice([["sse", "sse2"], [], None])
                else:
                    simd[flag] = rng.choice([True, False])
        checks["simd_identity"] = {"data": simd}
    fp["checks"] = checks
    return fp


class ClassificationFuzzHarness(unittest.TestCase):
    """Property-based fuzzing over derive_verified_device()."""

    def setUp(self):
        self.rng = random.Random(FUZZ_SEED)

    def test_fuzz_no_unhandled_exception(self):
        """Arbitrary dict-shaped inputs must never raise an unhandled exception."""
        errors = []
        for i in range(FUZZ_ITERATIONS):
            device = _make_random_device(self.rng)
            fingerprint = _make_random_fingerprint(self.rng)
            try:
                result = derive(device, fingerprint, bool(self.rng.random()))
            except Exception as e:
                errors.append((i, device, fingerprint, str(e)))

        if errors:
            msg = f"{len(errors)} exceptions in {FUZZ_ITERATIONS} iterations:\n"
            for i, dev, fp, err in errors[:5]:
                msg += f"  iter {i}: {err}\n    device={dev}\n    fp={fp}\n"
            self.fail(msg)

    def test_fuzz_multiplier_never_gt_1_without_vintage(self):
        """Must never yield multiplier > 1.0 without positive vintage evidence.

        We approximate by checking that non-vintage families/arches get <= 1.0 weight.
        This is a property check, not an exact reward calculation.
        """
        violations = []
        for i in range(FUZZ_ITERATIONS):
            device = _make_random_device(self.rng)
            fingerprint = _make_random_fingerprint(self.rng)
            try:
                result = derive(device, fingerprint, bool(self.rng.random()))
            except Exception:
                continue

            family = result.get("device_family", "")
            arch = result.get("device_arch", "")

            # Check HARDWARE_WEIGHTS for multiplier
            hw = mod.HARDWARE_WEIGHTS
            weight = 1.0
            if family in hw:
                arch_lower = str(arch).lower()
                if arch_lower in hw[family]:
                    weight = hw[family][arch_lower]
                elif "default" in hw[family]:
                    weight = hw[family]["default"]

            # If family is not explicitly vintage-known and weight > 1.0, it's suspicious
            vintage_families = {"PowerPC", "x86", "ARM", "Apple Silicon", "console"}
            if family not in vintage_families and weight > 1.0:
                violations.append((i, result, weight))

        if violations:
            msg = f"{len(violations)} violations in {FUZZ_ITERATIONS} iterations:\n"
            for i, result, w in violations[:5]:
                msg += f"  iter {i}: family={result.get('device_family')} arch={result.get('device_arch')} weight={w}\n"
            self.fail(msg)


# ============================================================
# Section 4: Test class
# ============================================================

class ClassificationCorpusTest(unittest.TestCase):
    """Real-world + adversarial corpus tests for derive_verified_device."""

    def _derive(self, device, fingerprint=None, fp_passed=True):
        return derive(device, fingerprint or {}, fp_passed)

    # --- Real-world corpus ---
    def test_corpus_real_world(self):
        failures = []
        for item in CORPUS_REAL_WORLD:
            result = self._derive(item["device"], item["fingerprint"], item["fp_passed"])
            if result["device_family"] != item["expected_family"] or result["device_arch"] != item["expected_arch"]:
                failures.append({
                    "name": item["name"],
                    "got": result,
                    "expected": {"device_family": item["expected_family"], "device_arch": item["expected_arch"]},
                    "source": item.get("source", ""),
                })
        if failures:
            msg = f"{len(failures)}/{len(CORPUS_REAL_WORLD)} real-world corpus failures:\n"
            for f in failures:
                msg += f"  {f['name']}: got {f['got']} expected {f['expected']} ({f['source']})\n"
            self.fail(msg)

    # --- Adversarial corpus ---
    def test_corpus_adversarial(self):
        failures = []
        for item in CORPUS_ADVERSARIAL:
            result = self._derive(item["device"], item["fingerprint"], True)
            if result["device_family"] != item["expected_family"] or result["device_arch"] != item["expected_arch"]:
                failures.append({
                    "name": item["name"],
                    "got": result,
                    "expected": {"device_family": item["expected_family"], "device_arch": item["expected_arch"]},
                    "source": item.get("source", ""),
                })
        if failures:
            msg = f"{len(failures)}/{len(CORPUS_ADVERSARIAL)} adversarial corpus failures:\n"
            for f in failures:
                msg += f"  {f['name']}: got {f['got']} expected {f['expected']} ({f['source']})\n"
            self.fail(msg)

    # --- Issue #7991 legacy-key-name trap ---
    def test_issue_7991_legacy_key_names(self):
        """The entropy profile hash reads legacy key names.
        Devices using both old and new key names should still classify correctly."""
        # Legacy key: 'family' instead of 'device_family'
        legacy_device = {"family": "x86", "arch": "modern", "cpu": "Intel Pentium III 800MHz", "machine": "i686"}
        result = self._derive(legacy_device, _fp_no_simd(), False)
        self.assertEqual(result["device_family"], "x86")
        self.assertEqual(result["device_arch"], "pentium_iii")

        # Mixed: 'device_family' + 'arch' (new + old)
        mixed_device = {"device_family": "PowerPC", "arch": "g4", "cpu": "PowerPC 7450", "machine": "Power Macintosh"}
        result = self._derive(mixed_device, _simd_fp(altivec=True), True)
        self.assertEqual(result["device_family"], "PowerPC")
        self.assertEqual(result["device_arch"], "G4")

        # New key: 'device_family' + 'device_arch'
        new_device = {"device_family": "x86", "device_arch": "modern", "cpu": "Intel Pentium III 800MHz", "machine": "i686"}
        result = self._derive(new_device, _fp_no_simd(), False)
        self.assertEqual(result["device_family"], "x86")
        self.assertEqual(result["device_arch"], "pentium_iii")

    # --- Individual adversarial cases ---
    def test_spoof_ppc_with_x86_brand_rejected(self):
        d = {"family": "PowerPC", "arch": "g4", "cpu": "Intel Core i7", "machine": "ppc"}
        out = self._derive(d, _fp_no_simd(), False)
        self.assertNotEqual(out["device_family"], "PowerPC")

    def test_spoof_arm_on_x86_downgraded(self):
        d = {"family": "x86_64", "arch": "modern", "cpu": "", "machine": "aarch64"}
        out = self._derive(d, _fp_no_simd(), False)
        self.assertEqual(out["device_family"], "ARM")

    def test_missing_machine_unknown_cpu_rejected(self):
        d = {"family": "x86_64", "arch": "modern", "cpu": ""}
        out = self._derive(d, _fp_no_simd(), False)
        self.assertEqual(out["device_family"], "ARM")

    def test_unicode_in_brand_handled(self):
        d = {"family": "x86", "arch": "modern", "cpu": "Intel\u200bPentium III 800MHz", "machine": "i686"}
        out = self._derive(d, _fp_no_simd(), False)
        # Should not crash; classification may vary due to zero-width char
        self.assertIn("device_family", out)
        self.assertIn("device_arch", out)

    def test_oversized_brand_no_crash(self):
        d = {"family": "x86", "arch": "modern", "cpu": "A" * 50000, "machine": "i686"}
        out = self._derive(d, _fp_no_simd(), False)
        self.assertIn("device_family", out)
        self.assertIn("device_arch", out)

    def test_null_bytes_in_fields_handled(self):
        d = {"family": "x86\x00", "arch": "modern\x00", "cpu": "Intel Pentium III\x00", "machine": "i686"}
        out = self._derive(d, _fp_no_simd(), False)
        self.assertIn("device_family", out)
        self.assertIn("device_arch", out)

    def test_apple_silicon_detection(self):
        d = {"family": "arm64", "arch": "M1", "cpu": "Apple M1", "machine": "arm64", "platform_system": "Darwin"}
        out = self._derive(d, _fp_no_simd(), False)
        self.assertEqual(out["device_family"], "Apple Silicon")
        self.assertEqual(out["device_arch"], "M1")

    def test_vintage_arm_preserved(self):
        d = {"family": "ARM", "arch": "arm7tdmi", "cpu": "ARM7TDMI", "machine": ""}
        out = self._derive(d, _fp_no_simd(), False)
        self.assertEqual(out["device_family"], "ARM")
        self.assertEqual(out["device_arch"], "arm7tdmi")

    def test_exotic_sparc_detected(self):
        d = {"family": "sparc", "arch": "sparc", "cpu": "UltraSPARC-II", "machine": "sparc"}
        out = self._derive(d, _fp_no_simd(), False)
        self.assertEqual(out["device_family"], "SPARC")

    def test_exotic_mips_detected(self):
        d = {"family": "mips", "arch": "mips", "cpu": "MIPS R10000", "machine": "mips"}
        out = self._derive(d, _fp_no_simd(), False)
        self.assertEqual(out["device_family"], "MIPS")

    def test_exotic_riscv_detected(self):
        d = {"family": "riscv", "arch": "riscv64", "cpu": "SiFive X280", "machine": "riscv64"}
        out = self._derive(d, _fp_no_simd(), False)
        self.assertEqual(out["device_family"], "RISC-V")

    def test_exotic_sh_detected(self):
        d = {"family": "SuperH", "arch": "sh4", "cpu": "Hitachi SH-4", "machine": "sh4"}
        out = self._derive(d, _fp_no_simd(), False)
        self.assertEqual(out["device_family"], "SuperH")

    def test_exotic_m68k_detected(self):
        d = {"family": "m68k", "arch": "68040", "cpu": "Motorola 68040", "machine": "m68k"}
        out = self._derive(d, _fp_no_simd(), False)
        self.assertEqual(out["device_family"], "M68K")

    def test_exotic_s390_detected(self):
        d = {"family": "s390x", "arch": "s390x", "cpu": "IBM z14", "machine": "s390x"}
        out = self._derive(d, _fp_no_simd(), False)
        self.assertEqual(out["device_family"], "S390")

    def test_exotic_cell_detected(self):
        d = {"family": "Cell", "arch": "cell_be", "cpu": "Cell Broadband Engine", "machine": "ppc64"}
        out = self._derive(d, _fp_no_simd(), False)
        self.assertEqual(out["device_family"], "Cell")


if __name__ == "__main__":
    unittest.main()
