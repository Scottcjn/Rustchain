// Integration tests for RustChain Rust miner components
// Tests real API endpoints and hardware detection

use rustchain::{HardwareInfo, HardwareTier};
use rustchain::miner_client::{MinerClient, FingerprintAttestation, DEFAULT_NODE_URL};
use rustchain::deep_entropy::{DeepEntropyVerifier, ChallengeType};

/// Test hardware fingerprint generation on real hardware
#[test]
fn test_fingerprint_generation_real_hardware() {
    let fp = FingerprintAttestation::generate()
        .expect("Failed to generate fingerprint");
    
    // Verify cache latencies are reasonable
    assert!(fp.cache_latencies.l1_ns > 0.0, "L1 cache latency should be > 0");
    assert!(fp.cache_latencies.l1_ns < 100.0, "L1 cache latency should be < 100ns");
    
    assert!(fp.cache_latencies.l2_ns > fp.cache_latencies.l1_ns, 
            "L2 should be slower than L1");
    assert!(fp.cache_latencies.l3_ns > fp.cache_latencies.l2_ns, 
            "L3 should be slower than L2");
    
    // Verify CPU flags detected
    assert!(!fp.cpu_flags.is_empty(), "Should detect CPU flags");
    
    // Verify SIMD capabilities detected
    assert!(
        fp.simd_caps.has_altivec || 
        fp.simd_caps.has_sse || 
        fp.simd_caps.has_neon ||
        fp.simd_caps.has_avx,
        "Should detect at least one SIMD capability"
    );
    
    println!("Fingerprint generated successfully:");
    println!("  L1: {:.2}ns, L2: {:.2}ns, L3: {:.2}ns", 
             fp.cache_latencies.l1_ns, 
             fp.cache_latencies.l2_ns, 
             fp.cache_latencies.l3_ns);
    println!("  CPU flags: {:?}", fp.cpu_flags);
}

/// Test fingerprint validation
#[test]
fn test_fingerprint_validation() {
    let fp = FingerprintAttestation::generate().unwrap();
    
    // Validate against different tiers
    let result_vintage = fp.validate(HardwareTier::Vintage).unwrap();
    let result_modern = fp.validate(HardwareTier::Modern).unwrap();
    
    // At least one validation should pass (unless running in emulator)
    assert!(
        result_vintage.cache_valid || result_modern.cache_valid,
        "Cache validation should pass for at least one tier"
    );
    
    // Emulation should not be detected on real hardware
    assert!(
        !result_vintage.emulation_detected,
        "Should not detect emulation on real hardware"
    );
    
    println!("Validation result: {:?}", result_vintage);
}

/// Test entropy measurement
#[test]
fn test_entropy_measurement() {
    let proof = DeepEntropyVerifier::measure_cache_timing(100);
    
    assert!(!proof.measurements.is_empty(), "Should have measurements");
    assert!(proof.stats.mean > 0.0, "Mean should be positive");
    assert!(proof.stats.std_dev > 0.0, "Should have variance");
    assert!(proof.stats.entropy_bits > 0.0, "Should have entropy");
    
    println!("Entropy measurement:");
    println!("  Mean: {:.2}ns, StdDev: {:.2}ns", proof.stats.mean, proof.stats.std_dev);
    println!("  Entropy: {:.2} bits", proof.stats.entropy_bits);
}

/// Test entropy verification
#[test]
fn test_entropy_verification() {
    let verifier = DeepEntropyVerifier::new();
    let proof = DeepEntropyVerifier::measure_cache_timing(200);
    
    // Verify against modern hardware baseline
    let result = verifier.verify(&proof, "Modern");
    
    println!("Verification result: {:?}", result);
    
    // On real hardware, should have reasonable confidence
    assert!(
        result.confidence > 0.0,
        "Should have some confidence in verification"
    );
}

/// Test hardware info creation
#[test]
fn test_hardware_info_creation() {
    let hw = HardwareInfo::new(
        "PowerPC G4".to_string(),
        "G4".to_string(),
        22
    );
    
    assert_eq!(hw.model, "PowerPC G4");
    assert_eq!(hw.generation, "G4");
    assert_eq!(hw.age_years, 22);
    assert_eq!(hw.tier, HardwareTier::Vintage);
    assert!((hw.multiplier - 2.5).abs() < 0.01);
}

/// Test hardware tier calculation
#[test]
fn test_hardware_tier_calculation() {
    let test_cases = vec![
        (35, HardwareTier::Ancient, 3.5),
        (27, HardwareTier::Sacred, 3.0),
        (22, HardwareTier::Vintage, 2.5),
        (17, HardwareTier::Classic, 2.0),
        (12, HardwareTier::Retro, 1.5),
        (7, HardwareTier::Modern, 1.0),
        (2, HardwareTier::Recent, 0.5),
    ];
    
    for (age, expected_tier, expected_mult) in test_cases {
        let tier = HardwareTier::from_age(age);
        assert_eq!(tier, expected_tier, "Age {} should be {:?}", age, expected_tier);
        assert!((tier.multiplier() - expected_mult).abs() < 0.01,
                "Multiplier should be {}", expected_mult);
    }
}

/// Test miner client creation
#[test]
fn test_miner_client_creation() {
    let hw = HardwareInfo::new("Test CPU".to_string(), "Test".to_string(), 10);
    
    let client = MinerClient::with_default_node("test-wallet", hw);
    assert!(client.is_ok(), "Should create miner client");
}

/// Test node health check (requires network)
#[tokio::test]
async fn test_node_health() {
    let hw = HardwareInfo::new("Test".to_string(), "Test".to_string(), 10);
    let client = MinerClient::with_default_node("test", hw).unwrap();
    
    // This test may fail if node is offline
    match client.check_health().await {
        Ok(health) => {
            println!("Node health: {:?}", health);
            assert!(health.ok, "Node should be healthy");
        }
        Err(e) => {
            println!("Node health check skipped (node may be offline): {}", e);
            // Don't fail test - node may be offline during CI
        }
    }
}

/// Test epoch info retrieval (requires network)
#[tokio::test]
async fn test_epoch_info() {
    let hw = HardwareInfo::new("Test".to_string(), "Test".to_string(), 10);
    let client = MinerClient::with_default_node("test", hw).unwrap();
    
    match client.get_epoch_info().await {
        Ok(epoch) => {
            println!("Epoch info: {:?}", epoch);
            assert!(epoch.epoch > 0, "Epoch should be positive");
            assert!(epoch.blocks_per_epoch > 0, "Blocks per epoch should be positive");
        }
        Err(e) => {
            println!("Epoch info skipped (node may be offline): {}", e);
        }
    }
}

/// Test fingerprint attestation freshness
#[test]
fn test_attestation_freshness() {
    let mut fp = FingerprintAttestation::generate().unwrap();
    
    // Should be fresh initially
    let validation = fp.validate(HardwareTier::Modern).unwrap();
    assert!(validation.is_fresh, "Attestation should be fresh");
    
    // Simulate old attestation
    fp.attested_at -= 7200; // 2 hours ago
    
    let validation = fp.validate(HardwareTier::Modern).unwrap();
    assert!(!validation.is_fresh, "Attestation should be stale");
}

/// Test SIMD detection across platforms
#[test]
fn test_simd_detection() {
    let simd = FingerprintAttestation::detect_simd_capabilities();
    
    // At least one SIMD capability should be present
    let has_simd = simd.has_altivec || 
                   simd.has_sse || 
                   simd.has_sse2 ||
                   simd.has_neon ||
                   simd.has_avx ||
                   simd.has_avx2;
    
    assert!(has_simd, "Should detect at least one SIMD capability");
    
    println!("SIMD capabilities:");
    println!("  AltiVec: {}", simd.has_altivec);
    println!("  SSE: {} {} {} {} {}", 
             simd.has_sse, simd.has_sse2, simd.has_sse3, 
             simd.has_sse41, simd.has_sse42);
    println!("  AVX: {} {}", simd.has_avx, simd.has_avx2);
    println!("  NEON: {}", simd.has_neon);
}

/// Test cache latency ratios
#[test]
fn test_cache_latency_ratios() {
    let fp = FingerprintAttestation::generate().unwrap();
    
    // L2 should be slower than L1
    assert!(fp.cache_latencies.l2_ns > fp.cache_latencies.l1_ns,
            "L2 cache should be slower than L1");
    
    // L3 should be slower than L2
    assert!(fp.cache_latencies.l3_ns > fp.cache_latencies.l2_ns,
            "L3 cache should be slower than L2");
    
    // Typical ratios: L2 ~10x L1, L3 ~5x L2
    let l2_l1_ratio = fp.cache_latencies.l2_ns / fp.cache_latencies.l1_ns;
    let l3_l2_ratio = fp.cache_latencies.l3_ns / fp.cache_latencies.l2_ns;
    
    println!("Cache ratios: L2/L1={:.2}, L3/L2={:.2}", l2_l1_ratio, l3_l2_ratio);
    
    // Ratios should be reasonable (not emulation)
    assert!(l2_l1_ratio > 1.5, "L2/L1 ratio too low - possible emulation");
    assert!(l3_l2_ratio > 1.5, "L3/L2 ratio too low - possible emulation");
}

/// Test hardware serial detection
#[test]
fn test_hardware_serial_detection() {
    let fp = FingerprintAttestation::generate().unwrap();
    
    // Serial may or may not be available depending on platform
    if let Some(ref serial) = fp.hardware_serial {
        println!("Hardware serial detected: {}", serial);
        assert!(!serial.is_empty(), "Serial should not be empty");
        assert!(serial.len() >= 8, "Serial should be at least 8 chars");
    } else {
        println!("No hardware serial detected (normal on some platforms)");
    }
}
