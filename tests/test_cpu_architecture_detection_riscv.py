# SPDX-License-Identifier: MIT

import sys

sys.path.insert(0, ".")
import cpu_architecture_detection as cpu_detect


def _misa(*letters):
    value = 0
    for letter in letters:
        value |= 1 << (ord(letter.lower()) - ord("a"))
    return value


def test_detects_sifive_u74_profile():
    assert cpu_detect.detect_cpu_architecture("SiFive Freedom U740 RV64GC") == (
        "riscv",
        "sifive_u74",
        2020,
        False,
    )


def test_detects_starfive_jh7110_profile():
    assert cpu_detect.detect_cpu_architecture("StarFive JH7110 riscv64 board") == (
        "riscv",
        "starfive_jh7110",
        2022,
        False,
    )


def test_detects_allwinner_d1_c906_profile():
    assert cpu_detect.detect_cpu_architecture("Allwinner D1 Xuantie C906 RV64IMAFDC") == (
        "riscv",
        "allwinner_d1_c906",
        2021,
        False,
    )


def test_decodes_misa_extensions_for_rv64gc():
    misa = _misa("i", "m", "a", "f", "d", "c")

    assert cpu_detect.detect_cpu_architecture(f"RISC-V board xlen=64 misa=0x{misa:x}") == (
        "riscv",
        "rv64gc",
        2015,
        False,
    )


def test_vector_extension_is_modern_marker():
    misa = _misa("i", "m", "a", "f", "d", "c", "v")

    assert cpu_detect.detect_cpu_architecture(f"RISC-V board xlen=64 misa=0x{misa:x}") == (
        "riscv",
        "rvv_modern",
        2021,
        False,
    )


def test_detects_linux_isa_suffixes():
    assert cpu_detect.detect_cpu_architecture("isa : rv64imafdc_zicsr_zifencei") == (
        "riscv",
        "rv64gc",
        2015,
        False,
    )
    assert cpu_detect.detect_cpu_architecture("isa : rv64gcv_zicsr_zifencei") == (
        "riscv",
        "rvv_modern",
        2021,
        False,
    )
    assert cpu_detect.detect_cpu_architecture("isa : rv32imac_zicsr_zifencei") == (
        "riscv",
        "rv32im",
        2014,
        False,
    )


def test_riscv_multiplier_uses_profile_weight():
    info = cpu_detect.calculate_antiquity_multiplier(
        "RV32IMAC embedded board",
        custom_year=2024,
    )

    assert info.vendor == "riscv"
    assert info.architecture == "rv32im"
    assert info.generation == "RISC-V RV32I/RV32IM"
    assert info.antiquity_multiplier == 1.5
