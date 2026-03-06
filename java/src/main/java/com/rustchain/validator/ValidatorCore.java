package com.rustchain.validator;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.rustchain.model.*;
import com.rustchain.util.EntropyGenerator;
import com.rustchain.util.HardwareDetector;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Instant;
import java.util.UUID;

/**
 * Core validator that generates Proof of Antiquity.
 * This is the main class for RustChain validation.
 */
public class ValidatorCore {

    private static final Logger logger = LoggerFactory.getLogger(ValidatorCore.class);
    private static final String PROTOCOL_VERSION = "1.1.0";
    private static final String VALIDATOR_VERSION = "1.0.0-java";

    private final HardwareDetector hardwareDetector;
    private final EntropyGenerator entropyGenerator;
    private final ObjectMapper objectMapper;
    private String validatorId;

    public ValidatorCore() {
        this.hardwareDetector = new HardwareDetector();
        this.entropyGenerator = new EntropyGenerator();
        this.objectMapper = new ObjectMapper();
        this.objectMapper.enable(SerializationFeature.INDENT_OUTPUT);
        this.validatorId = generateValidatorId();
    }

    /**
     * Generate a unique validator ID.
     */
    private String generateValidatorId() {
        return "validator-" + UUID.randomUUID().toString().substring(0, 8);
    }

    /**
     * Run the full validation process and generate proof.
     *
     * @return ProofOfAntiquity containing the complete proof
     */
    public ProofOfAntiquity validate() {
        return validate(1_000_000); // Default iterations
    }

    /**
     * Run the full validation process with custom entropy iterations.
     *
     * @param entropyIterations Number of iterations for entropy generation
     * @return ProofOfAntiquity containing the complete proof
     */
    public ProofOfAntiquity validate(long entropyIterations) {
        logger.info("Starting RustChain validation for validator: {}", validatorId);

        ProofOfAntiquity proof = new ProofOfAntiquity();

        // Set basic info
        proof.setValidatorId(validatorId);
        proof.setTimestamp(Instant.now().toEpochMilli());

        // Detect hardware
        logger.info("Detecting hardware...");
        HardwareFingerprint fingerprint = hardwareDetector.detect();
        proof.setHardwareFingerprint(fingerprint);

        // Generate entropy proof
        logger.info("Generating entropy proof...");
        EntropyProof entropyProof = entropyGenerator.generateProof(entropyIterations);
        proof.setEntropyProof(entropyProof);

        // Calculate score
        logger.info("Calculating score...");
        Score score = calculateScore(fingerprint, entropyProof);
        proof.setScore(score);

        // Create attestation (placeholder for now)
        Attestation attestation = createAttestation();
        proof.setAttestation(attestation);

        // Add metadata
        Metadata metadata = createMetadata();
        proof.setMetadata(metadata);

        logger.info("Validation complete. Total score: {}", score.getTotalScore());

        return proof;
    }

    /**
     * Calculate the validator score based on hardware and entropy.
     */
    private Score calculateScore(HardwareFingerprint fingerprint, EntropyProof entropyProof) {
        Score score = new Score();

        // Base score from CPU cores
        int cores = fingerprint.getCpu().getCores();
        score.setBaseScore(cores * 10);

        // Vintage bonus from CPU
        int vintageBonus = fingerprint.getCpu().getVintageScore();
        vintageBonus += fingerprint.getBios().getVintageBonus();
        vintageBonus += fingerprint.getOs().getVintageBonus();
        score.setVintageBonus(vintageBonus);

        // Entropy bonus
        int entropyBonus = entropyGenerator.calculateEntropyBonus(entropyProof);
        score.setEntropyBonus(entropyBonus);

        // Uptime bonus (simplified - would use actual uptime in production)
        score.setUptimeBonus(50);

        // Multiplier based on era
        String era = fingerprint.getCpu().getEra();
        double multiplier = 1.0;
        if (era.contains("Classic")) {
            multiplier = 2.0;
        } else if (era.contains("Core 2")) {
            multiplier = 1.5;
        } else if (era.contains("Early Core i")) {
            multiplier = 1.3;
        } else if (era.contains("Athlon")) {
            multiplier = 1.8;
        }
        score.setMultiplier(multiplier);

        // Calculate total
        score.calculateTotal();

        // Determine rank
        int total = score.getTotalScore();
        if (total >= 1000) {
            score.setRank("Legendary");
        } else if (total >= 750) {
            score.setRank("Epic");
        } else if (total >= 500) {
            score.setRank("Rare");
        } else if (total >= 250) {
            score.setRank("Uncommon");
        } else {
            score.setRank("Common");
        }

        return score;
    }

    /**
     * Create attestation data.
     */
    private Attestation createAttestation() {
        Attestation attestation = new Attestation();
        attestation.setAlgorithm("SHA256withRSA");
        attestation.setPublicKey(generatePublicKeyPlaceholder());
        attestation.setSignature(generateSignaturePlaceholder());
        attestation.setVerified(false); // Would be verified by network
        return attestation;
    }

    private String generatePublicKeyPlaceholder() {
        // In production, this would be a real public key
        return "RSA-PUBKEY-" + UUID.randomUUID().toString().substring(0, 8).toUpperCase();
    }

    private String generateSignaturePlaceholder() {
        // In production, this would be a real signature
        return "SIG-" + UUID.randomUUID().toString().replace("-", "").toUpperCase();
    }

    /**
     * Create metadata.
     */
    private Metadata createMetadata() {
        Metadata metadata = new Metadata();
        metadata.setValidatorVersion(VALIDATOR_VERSION);
        metadata.setProtocolVersion(PROTOCOL_VERSION);
        metadata.setNetwork("mainnet");
        metadata.setEpoch(0);
        metadata.setBlockHeight(0);
        return metadata;
    }

    /**
     * Save proof to JSON file.
     *
     * @param proof The proof to save
     * @param filePath Path to save the file
     * @throws IOException If file cannot be written
     */
    public void saveProof(ProofOfAntiquity proof, String filePath) throws IOException {
        Path path = Paths.get(filePath);
        
        // Create parent directories if needed
        if (path.getParent() != null) {
            Files.createDirectories(path.getParent());
        }

        objectMapper.writeValue(path.toFile(), proof);
        logger.info("Proof saved to: {}", filePath);
    }

    /**
     * Load proof from JSON file.
     *
     * @param filePath Path to the proof file
     * @return Loaded ProofOfAntiquity
     * @throws IOException If file cannot be read
     */
    public ProofOfAntiquity loadProof(String filePath) throws IOException {
        ProofOfAntiquity proof = objectMapper.readValue(new File(filePath), ProofOfAntiquity.class);
        logger.info("Proof loaded from: {}", filePath);
        return proof;
    }

    /**
     * Validate and verify a proof file.
     *
     * @param filePath Path to the proof file
     * @return Validation result with status and messages
     */
    public ValidationResult validateProofFile(String filePath) {
        ValidationResult result = new ValidationResult();
        
        try {
            ProofOfAntiquity proof = loadProof(filePath);
            
            // Check required fields
            if (proof.getValidatorId() == null || proof.getValidatorId().isEmpty()) {
                result.addError("Missing validator_id");
            }
            
            if (proof.getTimestamp() <= 0) {
                result.addError("Invalid timestamp");
            }
            
            if (proof.getHardwareFingerprint() == null) {
                result.addError("Missing hardware_fingerprint");
            }
            
            if (proof.getEntropyProof() == null) {
                result.addError("Missing entropy_proof");
            } else {
                // Verify entropy proof
                if (!entropyGenerator.verifyProof(proof.getEntropyProof())) {
                    result.addError("Invalid entropy proof");
                }
            }
            
            if (proof.getScore() == null) {
                result.addError("Missing score");
            }
            
            result.setValid(result.getErrors().isEmpty());
            result.setProof(proof);
            
        } catch (IOException e) {
            result.addError("Failed to read proof file: " + e.getMessage());
            result.setValid(false);
        }
        
        return result;
    }

    /**
     * Get the validator ID.
     */
    public String getValidatorId() {
        return validatorId;
    }

    /**
     * Set the validator ID.
     */
    public void setValidatorId(String validatorId) {
        this.validatorId = validatorId;
    }

    /**
     * Validation result holder.
     */
    public static class ValidationResult {
        private boolean valid;
        private ProofOfAntiquity proof;
        private java.util.List<String> errors = new java.util.ArrayList<>();

        public boolean isValid() {
            return valid;
        }

        public void setValid(boolean valid) {
            this.valid = valid;
        }

        public ProofOfAntiquity getProof() {
            return proof;
        }

        public void setProof(ProofOfAntiquity proof) {
            this.proof = proof;
        }

        public java.util.List<String> getErrors() {
            return errors;
        }

        public void addError(String error) {
            this.errors.add(error);
        }

        @Override
        public String toString() {
            if (valid) {
                return "ValidationResult{valid=true, score=" + 
                        (proof != null && proof.getScore() != null ? proof.getScore().getTotalScore() : "N/A") + "}";
            } else {
                return "ValidationResult{valid=false, errors=" + errors + "}";
            }
        }
    }
}
