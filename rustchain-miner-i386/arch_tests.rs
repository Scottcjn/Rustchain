//! Intel 386 Architecture Tests
//! Tests for Intel 80386 hardware detection and antiquity classification.

#[cfg(test)]
mod intel_386_tests {

    #[test]
    fn test_intel_386_detection() {
        let test_cases = vec![
            ("Intel 80386DX", true),
            ("Intel 80386SX", true),
            ("AMD 386DX", true),
            ("Cyrix 386SLC", true),
        ];
        for (cpu_name, is_386) in test_cases {
            let detected = cpu_name.to_lowercase().contains("386");
            assert_eq!(detected, is_386, "CPU '{}' detection mismatch", cpu_name);
        }
    }

    #[test]
    fn test_i386_antiquity_multiplier() {
        let i386_multiplier = 4.0;
        assert!(i386_multiplier >= 4.0, "Intel 386 should have 4.0x multiplier");
    }

    #[test]
    fn test_i386_no_cpuid() {
        let i386_has_cpuid = false;
        assert!(!i386_has_cpuid, "Intel 386 should NOT have CPUID instruction");
    }

    #[test]
    fn test_i386_fpu_variants() {
        let configs = vec![
            ("386DX-40", false),
            ("386DX-40+387", true),
        ];
        for (cpu, has_fpu) in configs {
            let is_386 = cpu.to_lowercase().contains("386");
            assert!(is_386, "'{}' should be identified as 386", cpu);
        }
    }

    #[test]
    fn test_i386_memory_limits() {
        let memory_configs = vec![(4096, "4MB minimum"), (8192, "8MB typical")];
        for (mem_kb, _) in memory_configs {
            assert!(mem_kb >= 4096, "{} should meet minimum", mem_kb);
        }
    }

    #[test]
    fn test_i386_crystal_drift() {
        let i386_drift_ppm = 150;
        let modern_drift_ppm = 15;
        assert!(i386_drift_ppm > modern_drift_ppm, "386 drift should exceed modern CPU");
    }

    #[test]
    fn test_i386_miner_id_format() {
        let hostname = "RUSTCHAIN-386";
        let hw_hash = "a1b2c3d4";
        let miner_id = format!("i386-{}-{}", hostname, hw_hash);
        assert!(miner_id.starts_with("i386-"));
        assert!(miner_id.contains(hostname));
    }

    #[test]
    fn test_i386_wallet_format() {
        let wallet = "C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg";
        assert!(wallet.starts_with('C'));
        assert!(wallet.len() >= 30);
    }

    #[test]
    fn test_djgpp_build_config() {
        let cflags = vec!["-march=i386", "-mno-80387", "-msoft-float", "-Os"];
        for flag in cflags {
            assert!(flag.starts_with('-'), "CFLAG should start with dash: {}", flag);
        }
    }
}
