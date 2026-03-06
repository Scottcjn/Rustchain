# RustChain Java SDK

[![Java](https://img.shields.io/badge/Java-11+-blue.svg)](https://openjdk.java.net/)
[![Maven](https://img.shields.io/badge/Maven-3.8+-red.svg)](https://maven.apache.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](../LICENSE)

**Official Java SDK and tools for RustChain Proof-of-Antiquity validation**

## Overview

The RustChain Java SDK provides a complete toolkit for participating in the RustChain network using Java. It includes:

- **Hardware Detection** - Automatic detection of CPU, memory, storage, BIOS, and OS information
- **Entropy Generation** - CPU-intensive proof generation with configurable iterations
- **Validator Core** - Complete proof-of-antiquity generation and validation
- **CLI Tools** - Command-line interface for all validator operations
- **Node Health Monitor** - System resource and node status monitoring

## Quick Start

### Prerequisites

- Java 11 or higher
- Maven 3.8+

### Build

```bash
cd java
mvn clean package
```

### Run Validation

```bash
# Generate a new proof
java -jar target/rustchain-java-sdk-1.0.0.jar validate

# Specify output file and iterations
java -jar target/rustchain-java-sdk-1.0.0.jar validate -o my_proof.json -i 5000000

# Verify a proof file
java -jar target/rustchain-java-sdk-1.0.0.jar verify proof_of_antiquity.json

# Display proof information
java -jar target/rustchain-java-sdk-1.0.0.jar info proof_of_antiquity.json

# Show score breakdown
java -jar target/rustchain-java-sdk-1.0.0.jar score proof_of_antiquity.json
```

## CLI Commands

### `validate` - Generate Proof

Generate a new Proof of Antiquity.

```bash
java -jar rustchain.jar validate [options]

Options:
  -o, --output <file>      Output file path (default: proof_of_antiquity.json)
  -i, --iterations <num>   Entropy iterations (default: 1000000)
  -v, --validator-id <id>  Custom validator ID
  -h, --help               Show help
```

**Example Output:**
```
RustChain Validator - Generating Proof of Antiquity
============================================================
Validator ID: validator-a1b2c3d4
Entropy iterations: 1000000

Detecting hardware...
Generating entropy proof...
Saving proof to: proof_of_antiquity.json

Validation Complete!
  Total Score: 450
  Rank: Uncommon
  Vintage Bonus: 250
  Entropy Bonus: 150

Proof saved to: /home/user/proof_of_antiquity.json
```

### `verify` - Verify Proof

Verify the validity of a proof file.

```bash
java -jar rustchain.jar verify <proof-file>
```

### `info` - Display Proof Details

Show detailed information about a proof.

```bash
java -jar rustchain.jar info <proof-file> [-j|--json]
```

### `score` - Score Analysis

Display detailed score breakdown and analysis.

```bash
java -jar rustchain.jar score <proof-file>
```

**Example Output:**
```
RustChain Score Analysis
============================================================

Score Components:
  Base Score:         40
  Vintage Bonus:     250
  Entropy Bonus:     150
  Uptime Bonus:       50
  ──────────────────────────
  Subtotal:          490
  Multiplier:        1.00x
  ══════════════════════════
  TOTAL SCORE:       490

Rank: Uncommon

🥉 UNCOMMON - Solid contributor!
```

### Node Health Monitor

Monitor node health and system resources.

```bash
java -cp rustchain.jar com.rustchain.cli.NodeHealthMonitor [options]

Options:
  --name <name>    Node name (default: default-node)
  --rpc <url>      Node RPC URL for health checks
  --help           Show help
```

## Library Usage

### Basic Validation

```java
import com.rustchain.validator.ValidatorCore;
import com.rustchain.model.ProofOfAntiquity;

public class Example {
    public static void main(String[] args) throws Exception {
        ValidatorCore validator = new ValidatorCore();
        
        // Generate proof
        ProofOfAntiquity proof = validator.validate();
        
        // Save to file
        validator.saveProof(proof, "proof_of_antiquity.json");
        
        System.out.println("Score: " + proof.getScore().getTotalScore());
        System.out.println("Rank: " + proof.getScore().getRank());
    }
}
```

### Hardware Detection

```java
import com.rustchain.util.HardwareDetector;
import com.rustchain.model.HardwareFingerprint;

HardwareDetector detector = new HardwareDetector();
HardwareFingerprint fingerprint = detector.detect();

System.out.println("CPU: " + fingerprint.getCpu().getVendor() + " " + 
                   fingerprint.getCpu().getModel());
System.out.println("Era: " + fingerprint.getCpu().getEra());
System.out.println("Vintage Score: " + fingerprint.getCpu().getVintageScore());
```

### Entropy Generation

```java
import com.rustchain.util.EntropyGenerator;
import com.rustchain.model.EntropyProof;

EntropyGenerator generator = new EntropyGenerator();

// Generate proof with custom iterations
EntropyProof proof = generator.generateProof(5_000_000);

System.out.println("Hash: " + proof.getHash());
System.out.println("Duration: " + proof.getDurationMs() + "ms");
System.out.println("Bonus: " + generator.calculateEntropyBonus(proof));
```

### Proof Verification

```java
import com.rustchain.validator.ValidatorCore;

ValidatorCore validator = new ValidatorCore();
ValidatorCore.ValidationResult result = validator.validateProofFile("proof.json");

if (result.isValid()) {
    System.out.println("✓ Proof is valid");
    System.out.println("Score: " + result.getProof().getScore().getTotalScore());
} else {
    System.out.println("✗ Proof is invalid");
    for (String error : result.getErrors()) {
        System.out.println("  - " + error);
    }
}
```

## Project Structure

```
java/
├── pom.xml                          # Maven build configuration
├── src/main/java/com/rustchain/
│   ├── cli/
│   │   ├── RustChainCLI.java       # Main CLI entry point
│   │   └── NodeHealthMonitor.java  # Node health monitoring
│   ├── model/
│   │   ├── ProofOfAntiquity.java   # Main proof model
│   │   ├── HardwareFingerprint.java# Hardware data models
│   │   ├── EntropyProof.java       # Entropy proof model
│   │   ├── Attestation.java        # Attestation model
│   │   ├── Score.java              # Score model
│   │   └── Metadata.java           # Metadata model
│   ├── util/
│   │   ├── HardwareDetector.java   # Hardware detection logic
│   │   └── EntropyGenerator.java   # Entropy generation logic
│   └── validator/
│       └── ValidatorCore.java      # Core validator logic
├── src/test/java/com/rustchain/
│   └── RustChainSDKTest.java       # JUnit tests
└── resources/                       # Configuration resources
```

## Scoring System

The RustChain scoring system rewards vintage hardware and computational work:

### Score Components

| Component | Description | Range |
|-----------|-------------|-------|
| Base Score | CPU cores × 10 | 10-500 |
| Vintage Bonus | CPU/BIOS/OS age bonus | 0-1000 |
| Entropy Bonus | Proof-of-work quality | 0-500 |
| Uptime Bonus | Node uptime | 0-200 |
| Multiplier | Era-based multiplier | 1.0-2.0x |

### Vintage Eras

| Era | Example CPUs | Base Vintage Score |
|-----|--------------|-------------------|
| Classic (1990s) | Pentium, 486, 386 | 500 |
| Athlon Era (1999-2005) | Athlon, Duron | 400 |
| Core 2 Era (2006-2008) | Core 2 Duo/Quad | 350 |
| Early Core i (2008-2012) | 1st-3rd Gen Core i | 250 |
| Mid Core i (2012-2017) | 4th-7th Gen Core i | 150 |
| Modern (2017+) | Ryzen, 8th+ Gen Core i | 100 |

### Ranks

| Rank | Total Score | Badge |
|------|-------------|-------|
| Legendary | 1000+ | 🏆 |
| Epic | 750-999 | 🥇 |
| Rare | 500-749 | 🥈 |
| Uncommon | 250-499 | 🥉 |
| Common | <250 | ⭐ |

## Configuration

### Maven Dependencies

The SDK uses the following dependencies (managed in `pom.xml`):

- **Jackson** - JSON serialization/deserialization
- **picocli** - Command-line argument parsing
- **SLF4J** - Logging facade
- **JUnit 5** - Testing framework

### System Properties

```bash
# Set custom config directory
java -Drustchain.config=/path/to/config -jar rustchain.jar validate

# Enable debug logging
java -Dorg.slf4j.simpleLogger.logFile=System.out \
     -Dorg.slf4j.simpleLogger.defaultLogLevel=debug \
     -jar rustchain.jar validate
```

## Testing

Run all tests:

```bash
mvn test
```

Run specific test:

```bash
mvn test -Dtest=RustChainSDKTest#testEntropyGenerator
```

Generate test coverage report:

```bash
mvn clean test jacoco:report
```

## Building Distribution

### Fat JAR (all dependencies included)

```bash
mvn clean package
```

Output: `target/rustchain-java-sdk-1.0.0.jar`

### JAR with Sources and Javadoc

```bash
mvn clean package source:jar javadoc:jar
```

## Integration Examples

### Spring Boot Service

```java
@Service
public class RustChainValidatorService {
    
    @Autowired
    private ValidatorCore validator;
    
    @Scheduled(fixedRate = 3600000) // Every hour
    public void generateProof() {
        ProofOfAntiquity proof = validator.validate();
        validator.saveProof(proof, "proofs/proof_" + 
            System.currentTimeMillis() + ".json");
    }
}
```

### REST API Endpoint

```java
@RestController
@RequestMapping("/api/validator")
public class ValidatorController {
    
    @PostMapping("/validate")
    public ResponseEntity<ProofOfAntiquity> validate() {
        ValidatorCore validator = new ValidatorCore();
        ProofOfAntiquity proof = validator.validate();
        return ResponseEntity.ok(proof);
    }
    
    @GetMapping("/proof/{id}")
    public ResponseEntity<ProofOfAntiquity> getProof(@PathVariable String id) {
        // Load and return proof
    }
}
```

## Troubleshooting

### Common Issues

**"SHA-256 not available" error**
- Ensure Java Cryptography Extension (JCE) is installed
- Use Oracle JDK or OpenJDK with full crypto support

**Hardware detection returns "Unknown"**
- Some platforms require elevated privileges
- Try running with `sudo` on Linux for full hardware info
- BIOS detection may need root access

**Low entropy bonus**
- Increase iteration count: `-i 5000000`
- Ensure system is not under heavy load during validation

### Performance Tips

- Use more iterations for higher entropy bonus (but slower)
- Run during low system activity for consistent results
- Vintage hardware gets significant score multipliers

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `mvn test`
5. Submit a pull request

## License

MIT License - see [LICENSE](../LICENSE) for details.

## Links

- [RustChain Main Repository](https://github.com/Scottcjn/Rustchain)
- [Proof of Antiquity Specification](../rips/docs/RIP-0001-proof-of-antiquity.md)
- [Contributing Guide](../CONTRIBUTING.md)
- [Bounty Program](../bounties/dev_bounties.json)

---

**RustChain Java SDK v1.0.0** - Validating the past, securing the future.
