// RIP-PoA Fingerprint CLI
// ========================
// Command-line interface for hardware fingerprint validation
// Usage: rustchain-fingerprint [OPTIONS]

use clap::{Parser, Subcommand};
use rustchain_fingerprint::{run_all_checks, validate_against_profile, FingerprintReport};
use std::fs;
use std::path::PathBuf;

#[derive(Parser)]
#[command(name = "rustchain-fingerprint")]
#[command(author = "Flamekeeper Scott <scott@rustchain.net>")]
#[command(version = "0.1.0")]
#[command(about = "RIP-PoA Hardware Fingerprint Suite for bounty #734", long_about = None)]
struct Cli {
    /// Output format (text, json)
    #[arg(short, long, default_value = "text")]
    format: String,

    /// Write JSON report to file
    #[arg(long, value_name = "FILE")]
    json_out: Option<PathBuf>,

    /// Compare against reference profile
    #[arg(long, value_name = "PROFILE")]
    compare: Option<String>,

    /// Redact host identifiers in output
    #[arg(long)]
    redact: bool,

    /// List available reference profiles
    #[arg(long)]
    list_profiles: bool,

    /// Skip specific checks (comma-separated)
    #[arg(long, value_name = "CHECKS")]
    skip: Option<String>,

    /// Verbose output
    #[arg(short, long)]
    verbose: bool,
}

#[derive(Subcommand)]
enum Commands {
    /// Run all fingerprint checks
    Run,
    /// List available reference profiles
    Profiles,
    /// Validate a JSON report file
    Validate {
        /// Path to JSON report file
        file: PathBuf,
    },
}

fn main() {
    let cli = Cli::parse();

    if cli.list_profiles {
        list_profiles();
        return;
    }

    // Run fingerprint checks
    let report = run_all_checks();

    // Validate against profile if specified
    if let Some(profile) = &cli.compare {
        let valid = validate_against_profile(&report, profile);
        if !cli.verbose {
            println!("{}", if valid { "PASS" } else { "FAIL" });
            std::process::exit(if valid { 0 } else { 2 });
        }
    }

    // Output results
    match cli.format.as_str() {
        "json" => {
            let output = if cli.redact {
                redact_report(&report)
            } else {
                report.clone()
            };
            
            let json = serde_json::to_string_pretty(&output).unwrap();
            
            // Write to file if specified
            if let Some(path) = &cli.json_out {
                fs::write(path, &json).expect("Failed to write JSON file");
                eprintln!("Report written to: {}", path.display());
            } else {
                println!("{}", json);
            }
        }
        _ => {
            print_text_report(&report, cli.verbose);
        }
    }

    // Exit with appropriate code
    std::process::exit(if report.all_passed { 0 } else { 2 });
}

/// Print human-readable text report
fn print_text_report(report: &FingerprintReport, verbose: bool) {
    println!("================================================================================");
    println!("RIP-PoA Hardware Fingerprint Report");
    println!("================================================================================");
    println!();
    println!("Platform: {} / {}", report.platform.os, report.platform.architecture);
    if let Some(ref cpu) = report.platform.cpu_model {
        println!("CPU: {}", cpu);
    }
    println!();
    println!("Results: {}/{} checks passed", report.checks_passed, report.checks_total);
    println!("Status: {}", if report.all_passed { "✅ ALL PASSED" } else { "❌ SOME FAILED" });
    println!();
    println!("--------------------------------------------------------------------------------");
    println!("Individual Checks:");
    println!("--------------------------------------------------------------------------------");

    for (i, result) in report.results.iter().enumerate() {
        let status = if result.passed { "✅ PASS" } else { "❌ FAIL" };
        println!("[{}/{}] {} {}", i + 1, report.results.len(), result.name, status);
        
        if verbose {
            println!("    Data: {}", result.data);
            if let Some(ref reason) = result.fail_reason {
                println!("    Reason: {}", reason);
            }
        }
    }

    println!();
    println!("--------------------------------------------------------------------------------");
    println!("Timestamp: {}", report.timestamp);
    println!("================================================================================");
}

/// List available reference profiles
fn list_profiles() {
    println!("Available Reference Profiles:");
    println!();
    println!("  modern_x86  - Modern x86_64 systems (expects SSE/AVX)");
    println!("  vintage_ppc - Vintage PowerPC systems (expects AltiVec)");
    println!("  arm64       - ARM64 systems (expects NEON)");
    println!();
    println!("Use --compare <profile> to validate against a profile.");
}

/// Redact sensitive information from report
fn redact_report(report: &FingerprintReport) -> FingerprintReport {
    let mut redacted = report.clone();
    
    // Redact CPU model
    if let Some(ref mut cpu) = redacted.platform.cpu_model {
        *cpu = "[REDACTED]".to_string();
    }

    // Redact specific fields in results
    for result in &mut redacted.results {
        if result.name == "device_age_oracle" {
            if let Some(obj) = result.data.as_object_mut() {
                if let Some(cpu) = obj.get_mut("cpu_model") {
                    *cpu = serde_json::json!("[REDACTED]");
                }
            }
        }
    }

    redacted
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_redact_report() {
        let report = run_all_checks();
        let redacted = redact_report(&report);
        // CPU model may be None on some systems, so check if it was Some before
        if report.platform.cpu_model.is_some() {
            assert_eq!(redacted.platform.cpu_model, Some("[REDACTED]".to_string()));
        }
    }
}
