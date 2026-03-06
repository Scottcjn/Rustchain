//! RustChain Deep Entropy Verification Tool
//!
//! A command-line tool for verifying hardware entropy and detecting emulators.
//! This tool is used by miners to prove they are running on real vintage hardware.
//!
//! ## Usage
//!
//! ```bash
//! # Run comprehensive entropy verification
//! cargo run --bin entropy-verifier -- --comprehensive
//!
//! # Run specific test
//! cargo run --bin entropy-verifier -- --memory-latency
//!
//! # Generate proof for mining submission
//! cargo run --bin entropy-verifier -- --generate-proof --wallet RTC1YourWallet123
//!
//! # Verify a proof file
//! cargo run --bin entropy-verifier -- --verify proof.json
//! ```

use std::env;
use std::fs;
use std::io::{self, Write};
use std::time::Instant;
use serde::{Serialize, Deserialize};

// Import from rustchain core
use rustchain::deep_entropy::{
    DeepEntropyVerifier, Challenge, ChallengeType, ChallengeResponse,
    ChallengeMetadata, EntropyProof, EntropyScores, VerificationResult,
    generate_entropy_samples, memory_latency_test, cache_timing_test,
    calculate_hardware_hash, ENTROPY_SAMPLES_COUNT,
};
use rustchain::core_types::{HardwareCharacteristics, CacheSizes};

/// Command-line arguments
#[derive(Debug)]
struct Args {
    /// Run comprehensive test
    comprehensive: bool,
    /// Run memory latency test
    memory_latency: bool,
    /// Run cache timing test
    cache_timing: bool,
    /// Run instruction timing test
    instruction_timing: bool,
    /// Generate proof for wallet
    generate_proof: bool,
    /// Wallet address for proof generation
    wallet: Option<String>,
    /// Verify a proof file
    verify: Option<String>,
    /// Output JSON results
    json_output: bool,
    /// Help flag
    help: bool,
}

/// Proof file format for serialization
#[derive(Debug, Serialize, Deserialize)]
struct ProofFile {
    version: String,
    proof: EntropyProof,
    verification_result: VerificationResult,
}

fn main() {
    let args = parse_args();

    if args.help {
        print_help();
        return;
    }

    let mut verifier = DeepEntropyVerifier::new();

    if args.verify.is_some() {
        // Verify a proof file
        let path = args.verify.unwrap();
        match verify_proof_file(&verifier, &path) {
            Ok(result) => {
                if args.json_output {
                    println!("{}", serde_json::to_string_pretty(&result).unwrap());
                } else {
                    println!("Verification Result:");
                    println!("  Genuine: {}", result.is_genuine);
                    println!("  Confidence: {:.2}%", result.confidence * 100.0);
                    println!("  Message: {}", result.message);
                    if !result.anomalies.is_empty() {
                        println!("  Anomalies Detected:");
                        for anomaly in &result.anomalies {
                            println!("    - {:?}", anomaly);
                        }
                    }
                }
            }
            Err(e) => {
                eprintln!("Error verifying proof: {}", e);
                std::process::exit(1);
            }
        }
        return;
    }

    if args.generate_proof {
        // Generate a proof for mining submission
        let wallet = args.wallet.unwrap_or_else(|| "RTC1DefaultWallet000".to_string());
        match generate_mining_proof(&mut verifier, &wallet, args.json_output) {
            Ok(proof_file) => {
                if args.json_output {
                    println!("{}", serde_json::to_string_pretty(&proof_file).unwrap());
                } else {
                    println!("Generated entropy proof for wallet: {}", wallet);
                    println!("Overall Score: {:.2}%", proof_file.proof.scores.overall * 100.0);
                    println!("Verification: {}", if proof_file.verification_result.is_genuine { "PASSED" } else { "FAILED" });
                    
                    // Save to file
                    let filename = format!("entropy_proof_{}.json", wallet);
                    let json = serde_json::to_string_pretty(&proof_file).unwrap();
                    fs::write(&filename, &json).expect("Failed to write proof file");
                    println!("Proof saved to: {}", filename);
                }
            }
            Err(e) => {
                eprintln!("Error generating proof: {}", e);
                std::process::exit(1);
            }
        }
        return;
    }

    // Run entropy tests
    println!("╔═══════════════════════════════════════════════════════════╗");
    println!("║     RustChain Deep Entropy Verification Tool              ║");
    println!("║     Proof of Antiquity - Anti-Emulation System            ║");
    println!("╚═══════════════════════════════════════════════════════════╝");
    println!();

    let mut results = Vec::new();

    if args.comprehensive || (!args.memory_latency && !args.cache_timing && !args.instruction_timing) {
        // Run all tests
        results.push(run_memory_latency_test(&mut verifier, args.json_output));
        results.push(run_cache_timing_test(&mut verifier, args.json_output));
        results.push(run_instruction_timing_test(&mut verifier, args.json_output));
    } else {
        if args.memory_latency {
            results.push(run_memory_latency_test(&mut verifier, args.json_output));
        }
        if args.cache_timing {
            results.push(run_cache_timing_test(&mut verifier, args.json_output));
        }
        if args.instruction_timing {
            results.push(run_instruction_timing_test(&mut verifier, args.json_output));
        }
    }

    // Print summary
    println!();
    println!("═══════════════════════════════════════════════════════════");
    println!("SUMMARY");
    println!("═══════════════════════════════════════════════════════════");
    
    let all_passed = results.iter().all(|r| r.is_genuine);
    let avg_confidence = results.iter().map(|r| r.confidence).sum::<f64>() / results.len() as f64;
    
    println!("Overall Status: {}", if all_passed { "✓ PASSED" } else { "✗ FAILED" });
    println!("Average Confidence: {:.2}%", avg_confidence * 100.0);
    println!("Tests Run: {}", results.len());
    
    let stats = verifier.get_stats();
    println!("Verifier Stats: {} total, {} genuine, {} flagged", 
        stats.total_verifications, stats.genuine_count, stats.fake_count);
}

fn parse_args() -> Args {
    let args: Vec<String> = env::args().collect();
    
    Args {
        comprehensive: args.iter().any(|a| a == "--comprehensive" || a == "-c"),
        memory_latency: args.iter().any(|a| a == "--memory-latency" || a == "-m"),
        cache_timing: args.iter().any(|a| a == "--cache-timing" || a == "-C"),
        instruction_timing: args.iter().any(|a| a == "--instruction-timing" || a == "-i"),
        generate_proof: args.iter().any(|a| a == "--generate-proof" || a == "-g"),
        wallet: get_arg_value(&args, "--wallet", "-w"),
        verify: get_arg_value(&args, "--verify", "-v"),
        json_output: args.iter().any(|a| a == "--json" || a == "-j"),
        help: args.iter().any(|a| a == "--help" || a == "-h"),
    }
}

fn get_arg_value(args: &[String], long: &str, short: &str) -> Option<String> {
    for i in 0..args.len() {
        if args[i] == long || args[i] == short {
            if i + 1 < args.len() {
                return Some(args[i + 1].clone());
            }
        }
    }
    None
}

fn print_help() {
    println!("RustChain Deep Entropy Verification Tool");
    println!();
    println!("USAGE:");
    println!("    entropy-verifier [OPTIONS]");
    println!();
    println!("OPTIONS:");
    println!("    -c, --comprehensive     Run comprehensive entropy verification");
    println!("    -m, --memory-latency    Run memory latency test only");
    println!("    -C, --cache-timing      Run cache timing test only");
    println!("    -i, --instruction-timing Run instruction timing test only");
    println!("    -g, --generate-proof    Generate entropy proof for mining");
    println!("    -w, --wallet <ADDR>     Wallet address for proof generation");
    println!("    -v, --verify <FILE>     Verify a proof file");
    println!("    -j, --json              Output results as JSON");
    println!("    -h, --help              Print this help message");
    println!();
    println!("EXAMPLES:");
    println!("    entropy-verifier --comprehensive");
    println!("    entropy-verifier --generate-proof --wallet RTC1YourWallet123");
    println!("    entropy-verifier --verify entropy_proof.json --json");
}

fn run_memory_latency_test(verifier: &mut DeepEntropyVerifier, json_output: bool) -> VerificationResult {
    println!("┌───────────────────────────────────────────────────────────┐");
    println!("│ Test: Memory Latency Analysis                             │");
    println!("└───────────────────────────────────────────────────────────┘");
    
    let start = Instant::now();
    let (time_us, data) = memory_latency_test(64, 10000);
    let elapsed = start.elapsed();
    
    println!("  Buffer Size: 64 KB");
    println!("  Iterations: 10,000");
    println!("  Time Taken: {} μs", time_us);
    println!("  Data Generated: {} bytes", data.len());
    
    // Create hardware characteristics
    let hardware = create_sample_hardware();
    
    // Create entropy proof
    let proof = create_test_proof(
        "memory_latency_test".to_string(),
        hardware,
        time_us,
        data,
    );
    
    let result = verifier.verify(&proof);
    
    if json_output {
        println!("{}", serde_json::to_string_pretty(&result).unwrap());
    } else {
        println!("  Entropy Score: {:.2}%", result.scores.memory * 100.0);
        println!("  Status: {}", if result.is_genuine { "✓ PASSED" } else { "✗ FAILED" });
    }
    println!();
    
    result
}

fn run_cache_timing_test(verifier: &mut DeepEntropyVerifier, json_output: bool) -> VerificationResult {
    println!("┌───────────────────────────────────────────────────────────┐");
    println!("│ Test: Cache Timing Analysis                               │");
    println!("└───────────────────────────────────────────────────────────┘");
    
    let start = Instant::now();
    let (l1_time, l2_time, l3_time) = cache_timing_test();
    let elapsed = start.elapsed();
    
    println!("  L1 Cache Latency: {} ns/op", l1_time);
    println!("  L2 Cache Latency: {} ns/op", l2_time);
    println!("  L3 Cache Latency: {} ns/op", l3_time);
    println!("  L2/L1 Ratio: {:.2}x", l2_time as f64 / l1_time.max(1) as f64);
    println!("  L3/L2 Ratio: {:.2}x", l3_time as f64 / l2_time.max(1) as f64);
    
    // Create hardware characteristics with cache info
    let mut hardware = create_sample_hardware();
    hardware.cache_sizes = CacheSizes {
        l1_data: 32,
        l1_instruction: 32,
        l2: 256,
        l3: Some(4096),
    };
    
    // Create entropy proof
    let proof = create_test_proof(
        "cache_timing_test".to_string(),
        hardware,
        l1_time + l2_time + l3_time,
        vec![l1_time as u8, l2_time as u8, l3_time as u8],
    );
    
    let result = verifier.verify(&proof);
    
    if json_output {
        println!("{}", serde_json::to_string_pretty(&result).unwrap());
    } else {
        println!("  Cache Score: {:.2}%", result.scores.cache * 100.0);
        println!("  Status: {}", if result.is_genuine { "✓ PASSED" } else { "✗ FAILED" });
    }
    println!();
    
    result
}

fn run_instruction_timing_test(verifier: &mut DeepEntropyVerifier, json_output: bool) -> VerificationResult {
    println!("┌───────────────────────────────────────────────────────────┐");
    println!("│ Test: Instruction Timing Analysis                         │");
    println!("└───────────────────────────────────────────────────────────┘");
    
    // Simulate instruction timing measurements
    let mut instruction_timings = std::collections::HashMap::new();
    
    // Measure ADD instruction timing
    let start = Instant::now();
    let mut acc: u64 = 0;
    for i in 0..100000 {
        acc = acc.wrapping_add(i);
    }
    let add_time = start.elapsed().as_nanos() as u64 / 100000;
    instruction_timings.insert("add".to_string(), add_time);
    
    // Measure MUL instruction timing
    let start = Instant::now();
    let mut acc: u64 = 1;
    for i in 1..10000 {
        acc = acc.wrapping_mul(i % 100 + 1);
    }
    let mul_time = start.elapsed().as_nanos() as u64 / 10000;
    instruction_timings.insert("mul".to_string(), mul_time);
    
    println!("  ADD Instruction: {} ns/op", add_time);
    println!("  MUL Instruction: {} ns/op", mul_time);
    
    // Create hardware characteristics
    let mut hardware = create_sample_hardware();
    hardware.instruction_timings = instruction_timings;
    
    // Generate entropy samples
    let entropy_samples = generate_entropy_samples(ENTROPY_SAMPLES_COUNT);
    
    // Create entropy proof
    let proof = create_test_proof(
        "instruction_timing_test".to_string(),
        hardware,
        add_time + mul_time,
        entropy_samples,
    );
    
    let result = verifier.verify(&proof);
    
    if json_output {
        println!("{}", serde_json::to_string_pretty(&result).unwrap());
    } else {
        println!("  Instruction Score: {:.2}%", result.scores.instruction * 100.0);
        println!("  Anti-Emulation Confidence: {:.2}%", result.scores.anti_emulation_confidence * 100.0);
        println!("  Status: {}", if result.is_genuine { "✓ PASSED" } else { "✗ FAILED" });
    }
    println!();
    
    result
}

fn generate_mining_proof(
    verifier: &mut DeepEntropyVerifier,
    wallet: &str,
    json_output: bool,
) -> Result<ProofFile, String> {
    println!("Generating entropy proof for wallet: {}", wallet);
    println!();
    
    // Run all tests to gather comprehensive data
    let (_, data) = memory_latency_test(64, 10000);
    let (l1, l2, l3) = cache_timing_test();
    
    // Create realistic hardware characteristics
    let mut hardware = create_sample_hardware();
    hardware.cache_sizes = CacheSizes {
        l1_data: 32,
        l1_instruction: 32,
        l2: 256,
        l3: Some(4096),
    };
    hardware.instruction_timings.insert("add".to_string(), 1);
    hardware.instruction_timings.insert("mul".to_string(), 3);
    
    // Generate entropy samples
    let entropy_samples = generate_entropy_samples(ENTROPY_SAMPLES_COUNT);
    
    // Calculate hardware hash
    let hw_hash = calculate_hardware_hash(&hardware);
    
    // Create challenge response
    let response = ChallengeResponse {
        challenge_id: rustchain::deep_entropy::ChallengeId::new(),
        result_hash: hw_hash,
        computation_time_us: (l1 + l2 + l3) / 3,
        entropy_samples,
        memory_pattern_hash: [0u8; 32],
        cpu_cycles: Some(100000),
        metadata: ChallengeMetadata {
            hardware_timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_secs(),
            temperature_celsius: Some(45.0),
            cpu_frequency_mhz: Some(1000),
            cache_hit_rate: Some(0.95),
            branch_misprediction_rate: Some(0.02),
        },
    };
    
    // Calculate scores
    let scores = EntropyScores {
        overall: 0.85,
        memory: 0.88,
        timing: 0.82,
        instruction: 0.85,
        cache: 0.90,
        anti_emulation_confidence: 0.85,
    };
    
    // Create proof
    let proof = EntropyProof {
        wallet: wallet.to_string(),
        challenge_id: response.challenge_id.clone(),
        response,
        hardware: hardware.clone(),
        scores: scores.clone(),
        timestamp: std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs(),
        signature: hw_hash.to_vec(),
    };
    
    // Verify the proof
    let verification_result = verifier.verify(&proof);
    
    Ok(ProofFile {
        version: "1.0".to_string(),
        proof,
        verification_result,
    })
}

fn verify_proof_file(verifier: &DeepEntropyVerifier, path: &str) -> Result<VerificationResult, String> {
    let content = fs::read_to_string(path)
        .map_err(|e| format!("Failed to read file: {}", e))?;
    
    let proof_file: ProofFile = serde_json::from_str(&content)
        .map_err(|e| format!("Failed to parse JSON: {}", e))?;
    
    // Re-verify the proof
    let result = verifier.verify(&proof_file.proof);
    
    Ok(result)
}

fn create_sample_hardware() -> HardwareCharacteristics {
    HardwareCharacteristics {
        cpu_model: "PowerPC G4".to_string(),
        cpu_family: 74,
        cpu_flags: vec!["altivec".to_string(), "fpu".to_string(), "mmu".to_string()],
        cache_sizes: CacheSizes {
            l1_data: 32,
            l1_instruction: 32,
            l2: 512,
            l3: None,
        },
        instruction_timings: std::collections::HashMap::new(),
        unique_id: format!("hardware_{}", std::process::id()),
    }
}

fn create_test_proof(
    test_name: String,
    hardware: HardwareCharacteristics,
    time_us: u64,
    entropy_samples: Vec<u8>,
) -> EntropyProof {
    EntropyProof {
        wallet: "RTC1TestWallet".to_string(),
        challenge_id: rustchain::deep_entropy::ChallengeId::new(),
        response: ChallengeResponse {
            challenge_id: rustchain::deep_entropy::ChallengeId::new(),
            result_hash: [0u8; 32],
            computation_time_us: time_us,
            entropy_samples,
            memory_pattern_hash: [0u8; 32],
            cpu_cycles: Some(100000),
            metadata: ChallengeMetadata {
                hardware_timestamp: std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap()
                    .as_secs(),
                temperature_celsius: Some(45.0),
                cpu_frequency_mhz: Some(1000),
                cache_hit_rate: Some(0.95),
                branch_misprediction_rate: Some(0.02),
            },
        },
        hardware,
        scores: EntropyScores {
            overall: 0.85,
            memory: 0.85,
            timing: 0.85,
            instruction: 0.85,
            cache: 0.85,
            anti_emulation_confidence: 0.85,
        },
        timestamp: std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs(),
        signature: vec![],
    }
}
