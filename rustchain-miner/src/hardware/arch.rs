// SPDX-License-Identifier: Apache-2.0
/// Classify CPU brand string into (device_family, device_arch).
///
/// Returns (&str, &str) — the family (e.g. "PowerPC", "x86_64", "ARM")
/// and the architecture tier (e.g. "g4", "modern").
pub fn classify(brand: &str) -> (&'static str, &'static str) {
    let lower = brand.to_lowercase();

    // PowerPC detection
    if lower.contains("7450") || lower.contains("7447") || lower.contains("7455") {
        return ("PowerPC", "g4");
    }
    if lower.contains("970") && lower.contains("power") {
        return ("PowerPC", "g5");
    }
    if lower.contains("750") && lower.contains("power") {
        return ("PowerPC", "g3");
    }
    // Generic PowerPC fallback
    if lower.contains("powerpc") || lower.contains("power") && lower.contains("pc") {
        if lower.contains("g4") {
            return ("PowerPC", "g4");
        }
        if lower.contains("g5") {
            return ("PowerPC", "g5");
        }
        if lower.contains("g3") {
            return ("PowerPC", "g3");
        }
        return ("PowerPC", "modern");
    }

    // Apple Silicon
    if lower.contains("apple m1") || lower.contains("apple m2") || lower.contains("apple m3") || lower.contains("apple m4") {
        return ("ARM", "apple_silicon");
    }

    // Core 2 Duo
    if lower.contains("core 2") || lower.contains("core2") || lower.contains("core(tm) 2") {
        return ("x86_64", "core2duo");
    }

    // ARM detection
    if lower.contains("aarch64") || lower.contains("arm") || lower.contains("cortex") {
        return ("ARM", "modern");
    }

    // RISC-V detection — StarFive VisionFive 2 (JH7110)
    if lower.contains("starfive") || lower.contains("jh7110") || lower.contains("visionfive") {
        return ("RISC-V", "starfive_jh7110");
    }

    // RISC-V detection — SiFive Unmatched
    if lower.contains("sifive") || lower.contains("fu740") || lower.contains("hifive") {
        return ("RISC-V", "sifive_unmatched");
    }

    // RISC-V detection — Milk-V Pioneer (SG2380)
    if lower.contains("milk-v") || lower.contains("sg2380") || lower.contains("pioneer") {
        return ("RISC-V", "milkv_pioneer");
    }

    // Generic RISC-V detection
    if lower.contains("riscv") || lower.contains("rv64") || lower.contains("rv32") {
        return ("RISC-V", "riscv_modern");
    }

    // Default: modern x86_64
    ("x86_64", "modern")
}

/// Get the antiquity multiplier for a given device_arch.
#[allow(dead_code)]
pub fn get_multiplier(device_arch: &str) -> f64 {
    match device_arch {
        "g4" => 2.5,
        "g5" => 2.0,
        "g3" => 1.8,
        "apple_silicon" => 1.2,
        "core2duo" => 1.3,
        // RISC-V tiers — slower than x86_64, higher reward for vintage hardware
        "starfive_jh7110" => 1.1,
        "sifive_unmatched" => 1.0,
        "milkv_pioneer" => 0.9,
        "riscv_modern" => 0.95,
        _ => 1.0,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_classify_g4() {
        let (family, arch) = classify("PowerPC G4 (7450)");
        assert_eq!(family, "PowerPC");
        assert_eq!(arch, "g4");
        assert!((get_multiplier(arch) - 2.5).abs() < f64::EPSILON);
    }

    #[test]
    fn test_classify_g5() {
        let (family, arch) = classify("PowerPC 970FX");
        assert_eq!(family, "PowerPC");
        assert_eq!(arch, "g5");
    }

    #[test]
    fn test_classify_apple_silicon() {
        let (family, arch) = classify("Apple M2 Pro");
        assert_eq!(family, "ARM");
        assert_eq!(arch, "apple_silicon");
    }

    #[test]
    fn test_classify_core2() {
        let (family, arch) = classify("Intel(R) Core(TM) 2 Duo E8400");
        assert_eq!(family, "x86_64");
        assert_eq!(arch, "core2duo");
    }

    #[test]
    fn test_classify_modern_amd() {
        let (family, arch) = classify("AMD Ryzen 5 8645HS");
        assert_eq!(family, "x86_64");
        assert_eq!(arch, "modern");
    }

    #[test]
    fn test_classify_modern_intel() {
        let (family, arch) = classify("13th Gen Intel(R) Core(TM) i7-13700H");
        assert_eq!(family, "x86_64");
        assert_eq!(arch, "modern");
    }

    #[test]
    fn test_classify_riscv_starfive() {
        let (family, arch) = classify("StarFive JH7110 RISC-V");
        assert_eq!(family, "RISC-V");
        assert_eq!(arch, "starfive_jh7110");
        assert!((get_multiplier(arch) - 1.1).abs() < f64::EPSILON);
    }

    #[test]
    fn test_classify_riscv_sifive() {
        let (family, arch) = classify("SiFive Freedom U740 RISC-V");
        assert_eq!(family, "RISC-V");
        assert_eq!(arch, "sifive_unmatched");
    }

    #[test]
    fn test_classify_riscv_milkv() {
        let (family, arch) = classify("Milk-V Pioneer SG2380");
        assert_eq!(family, "RISC-V");
        assert_eq!(arch, "milkv_pioneer");
    }

    #[test]
    fn test_classify_riscv_generic() {
        let (family, arch) = classify("RISC-V Processor");
        assert_eq!(family, "RISC-V");
        assert_eq!(arch, "riscv_modern");
    }
}
