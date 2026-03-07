package com.rustchain.cli;

import com.rustchain.model.ProofOfAntiquity;
import com.rustchain.model.Score;
import com.rustchain.validator.ValidatorCore;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import picocli.CommandLine;
import picocli.CommandLine.*;

import java.io.File;
import java.util.concurrent.Callable;

/**
 * RustChain Command Line Interface.
 * Provides commands for validation, proof management, and node operations.
 */
@Command(
        name = "rustchain",
        mixinStandardHelpOptions = true,
        version = "RustChain Java SDK 1.0.0",
        description = "RustChain Proof-of-Antiquity Validator CLI",
        subcommands = {
                ValidateCommand.class,
                VerifyCommand.class,
                InfoCommand.class,
                ScoreCommand.class
        }
)
public class RustChainCLI implements Callable<Integer> {

    private static final Logger logger = LoggerFactory.getLogger(RustChainCLI.class);

    @Spec
    private CommandSpec spec;

    @Override
    public Integer call() {
        System.out.println("RustChain Java SDK v1.0.0");
        System.out.println("Use 'rustchain --help' to see available commands");
        System.out.println();
        System.out.println("Quick start:");
        System.out.println("  rustchain validate              Generate a new proof");
        System.out.println("  rustchain verify <file>         Verify a proof file");
        System.out.println("  rustchain score <file>          Display score details");
        return 0;
    }

    /**
     * Validate command - generates a new proof of antiquity.
     */
    @Command(
            name = "validate",
            description = "Generate a new Proof of Antiquity"
    )
    static class ValidateCommand implements Callable<Integer> {

        @Option(names = {"-o", "--output"}, 
                description = "Output file path", 
                defaultValue = "proof_of_antiquity.json")
        private String outputFile;

        @Option(names = {"-i", "--iterations"}, 
                description = "Entropy iterations", 
                defaultValue = "1000000")
        private long iterations;

        @Option(names = {"-v", "--validator-id"}, 
                description = "Custom validator ID")
        private String validatorId;

        @Override
        public Integer call() {
            try {
                System.out.println("RustChain Validator - Generating Proof of Antiquity");
                System.out.println("=".repeat(60));

                ValidatorCore validator = new ValidatorCore();
                
                if (validatorId != null) {
                    validator.setValidatorId(validatorId);
                }

                System.out.println("Validator ID: " + validator.getValidatorId());
                System.out.println("Entropy iterations: " + iterations);
                System.out.println();

                // Run validation
                System.out.println("Detecting hardware...");
                ProofOfAntiquity proof = validator.validate(iterations);

                // Save proof
                System.out.println();
                System.out.println("Saving proof to: " + outputFile);
                validator.saveProof(proof, outputFile);

                // Display summary
                Score score = proof.getScore();
                System.out.println();
                System.out.println("Validation Complete!");
                System.out.println("  Total Score: " + score.getTotalScore());
                System.out.println("  Rank: " + score.getRank());
                System.out.println("  Vintage Bonus: " + score.getVintageBonus());
                System.out.println("  Entropy Bonus: " + score.getEntropyBonus());
                System.out.println();
                System.out.println("Proof saved to: " + new File(outputFile).getAbsolutePath());

                return 0;
            } catch (Exception e) {
                System.err.println("Validation failed: " + e.getMessage());
                e.printStackTrace();
                return 1;
            }
        }
    }

    /**
     * Verify command - verifies a proof file.
     */
    @Command(
            name = "verify",
            description = "Verify a Proof of Antiquity file"
    )
    static class VerifyCommand implements Callable<Integer> {

        @Parameters(index = "0", description = "Path to proof file")
        private String proofFile;

        @Override
        public Integer call() {
            System.out.println("RustChain Validator - Verifying Proof");
            System.out.println("=".repeat(60));
            System.out.println("Proof file: " + proofFile);
            System.out.println();

            ValidatorCore validator = new ValidatorCore();
            ValidatorCore.ValidationResult result = validator.validateProofFile(proofFile);

            if (result.isValid()) {
                System.out.println("✓ Proof is VALID");
                System.out.println();
                ProofOfAntiquity proof = result.getProof();
                System.out.println("Validator ID: " + proof.getValidatorId());
                System.out.println("Timestamp: " + proof.getTimestamp());
                if (proof.getScore() != null) {
                    System.out.println("Total Score: " + proof.getScore().getTotalScore());
                    System.out.println("Rank: " + proof.getScore().getRank());
                }
                return 0;
            } else {
                System.out.println("✗ Proof is INVALID");
                System.out.println();
                System.out.println("Errors:");
                for (String error : result.getErrors()) {
                    System.out.println("  - " + error);
                }
                return 1;
            }
        }
    }

    /**
     * Info command - displays information about a proof.
     */
    @Command(
            name = "info",
            description = "Display detailed information about a proof"
    )
    static class InfoCommand implements Callable<Integer> {

        @Parameters(index = "0", description = "Path to proof file")
        private String proofFile;

        @Option(names = {"-j", "--json"}, description = "Output as JSON")
        private boolean jsonOutput;

        @Override
        public Integer call() {
            try {
                ValidatorCore validator = new ValidatorCore();
                ProofOfAntiquity proof = validator.loadProof(proofFile);

                if (jsonOutput) {
                    System.out.println(new com.fasterxml.jackson.databind.ObjectMapper()
                            .writerWithDefaultPrettyPrinter()
                            .writeValueAsString(proof));
                } else {
                    System.out.println("RustChain Proof Information");
                    System.out.println("=".repeat(60));
                    System.out.println("Validator ID: " + proof.getValidatorId());
                    System.out.println("Timestamp: " + proof.getTimestamp());
                    System.out.println();

                    if (proof.getHardwareFingerprint() != null) {
                        var hw = proof.getHardwareFingerprint();
                        System.out.println("Hardware:");
                        if (hw.getCpu() != null) {
                            System.out.println("  CPU: " + hw.getCpu().getVendor() + " " + hw.getCpu().getModel());
                            System.out.println("  Era: " + hw.getCpu().getEra());
                            System.out.println("  Cores: " + hw.getCpu().getCores());
                        }
                        if (hw.getOs() != null) {
                            System.out.println("  OS: " + hw.getOs().getName() + " " + hw.getOs().getVersion());
                        }
                        System.out.println();
                    }

                    if (proof.getEntropyProof() != null) {
                        var entropy = proof.getEntropyProof();
                        System.out.println("Entropy Proof:");
                        System.out.println("  Method: " + entropy.getMethod());
                        System.out.println("  Iterations: " + entropy.getIterations());
                        System.out.println("  Duration: " + entropy.getDurationMs() + "ms");
                        System.out.println();
                    }

                    if (proof.getScore() != null) {
                        var score = proof.getScore();
                        System.out.println("Score Breakdown:");
                        System.out.println("  Base Score: " + score.getBaseScore());
                        System.out.println("  Vintage Bonus: " + score.getVintageBonus());
                        System.out.println("  Entropy Bonus: " + score.getEntropyBonus());
                        System.out.println("  Uptime Bonus: " + score.getUptimeBonus());
                        System.out.println("  Multiplier: " + score.getMultiplier() + "x");
                        System.out.println("  Total Score: " + score.getTotalScore());
                        System.out.println("  Rank: " + score.getRank());
                    }

                }
                return 0;
            } catch (Exception e) {
                System.err.println("Error reading proof: " + e.getMessage());
                return 1;
            }
        }
    }

    /**
     * Score command - calculates and displays score.
     */
    @Command(
            name = "score",
            description = "Calculate and display score details"
    )
    static class ScoreCommand implements Callable<Integer> {

        @Parameters(index = "0", description = "Path to proof file")
        private String proofFile;

        @Override
        public Integer call() {
            try {
                ValidatorCore validator = new ValidatorCore();
                ProofOfAntiquity proof = validator.loadProof(proofFile);

                if (proof.getScore() == null) {
                    System.err.println("Proof does not contain score information");
                    return 1;
                }

                Score score = proof.getScore();

                System.out.println("RustChain Score Analysis");
                System.out.println("=".repeat(60));
                System.out.println();
                System.out.println("Score Components:");
                System.out.println("  Base Score:      " + String.format("%6d", score.getBaseScore()));
                System.out.println("  Vintage Bonus:   " + String.format("%6d", score.getVintageBonus()));
                System.out.println("  Entropy Bonus:   " + String.format("%6d", score.getEntropyBonus()));
                System.out.println("  Uptime Bonus:    " + String.format("%6d", score.getUptimeBonus()));
                System.out.println("  ──────────────────────────");
                System.out.println("  Subtotal:        " + String.format("%6d", 
                        score.getBaseScore() + score.getVintageBonus() + 
                        score.getEntropyBonus() + score.getUptimeBonus()));
                System.out.println("  Multiplier:      " + String.format("%6.2fx", score.getMultiplier()));
                System.out.println("  ══════════════════════════");
                System.out.println("  TOTAL SCORE:     " + String.format("%6d", score.getTotalScore()));
                System.out.println();
                System.out.println("Rank: " + score.getRank());
                System.out.println();

                // Provide context
                int total = score.getTotalScore();
                if (total >= 1000) {
                    System.out.println("🏆 LEGENDARY - Exceptional vintage hardware!");
                } else if (total >= 750) {
                    System.out.println("🥇 EPIC - Outstanding contribution!");
                } else if (total >= 500) {
                    System.out.println("🥈 RARE - Valuable vintage system!");
                } else if (total >= 250) {
                    System.out.println("🥉 UNCOMMON - Solid contributor!");
                } else {
                    System.out.println("⭐ COMMON - Welcome to RustChain!");
                }

                return 0;
            } catch (Exception e) {
                System.err.println("Error: " + e.getMessage());
                return 1;
            }
        }
    }

    /**
     * Main entry point.
     */
    public static void main(String[] args) {
        int exitCode = new CommandLine(new RustChainCLI()).execute(args);
        System.exit(exitCode);
    }
}
