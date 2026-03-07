package com.rustchain;

import com.rustchain.model.*;
import com.rustchain.util.EntropyGenerator;
import com.rustchain.util.HardwareDetector;
import com.rustchain.validator.ValidatorCore;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Unit tests for RustChain Java SDK.
 */
public class RustChainSDKTest {

    private ValidatorCore validator;
    private HardwareDetector hardwareDetector;
    private EntropyGenerator entropyGenerator;

    @BeforeEach
    public void setUp() {
        validator = new ValidatorCore();
        hardwareDetector = new HardwareDetector();
        entropyGenerator = new EntropyGenerator();
    }

    @Test
    @DisplayName("Hardware Detector should detect CPU information")
    public void testHardwareDetectorCPU() {
        HardwareFingerprint fingerprint = hardwareDetector.detect();

        assertNotNull(fingerprint);
        assertNotNull(fingerprint.getCpu());
        assertNotNull(fingerprint.getCpu().getVendor());
        assertNotNull(fingerprint.getCpu().getModel());
        assertTrue(fingerprint.getCpu().getCores() > 0);
        assertTrue(fingerprint.getCpu().getVintageScore() > 0);
        assertNotNull(fingerprint.getCpu().getEra());
    }

    @Test
    @DisplayName("Hardware Detector should detect OS information")
    public void testHardwareDetectorOS() {
        HardwareFingerprint fingerprint = hardwareDetector.detect();

        assertNotNull(fingerprint);
        assertNotNull(fingerprint.getOs());
        assertNotNull(fingerprint.getOs().getName());
        assertNotNull(fingerprint.getOs().getVersion());
        assertNotNull(fingerprint.getOs().getArchitecture());
    }

    @Test
    @DisplayName("Hardware Detector should detect memory information")
    public void testHardwareDetectorMemory() {
        HardwareFingerprint fingerprint = hardwareDetector.detect();

        assertNotNull(fingerprint);
        assertNotNull(fingerprint.getMemory());
        assertTrue(fingerprint.getMemory().getTotalMB() > 0);
    }

    @Test
    @DisplayName("Entropy Generator should generate valid proof")
    public void testEntropyGenerator() {
        EntropyProof proof = entropyGenerator.generateProof(100000);

        assertNotNull(proof);
        assertNotNull(proof.getMethod());
        assertNotNull(proof.getSeed());
        assertTrue(proof.getIterations() > 0);
        assertTrue(proof.getDurationMs() > 0);
        assertNotNull(proof.getHash());
        assertEquals(64, proof.getHash().length()); // SHA-256 produces 64 hex chars
        assertTrue(entropyGenerator.verifyProof(proof));
    }

    @Test
    @DisplayName("Entropy Generator should calculate bonus scores")
    public void testEntropyBonusCalculation() {
        EntropyProof proof = entropyGenerator.generateProof(1000000);
        int bonus = entropyGenerator.calculateEntropyBonus(proof);

        assertTrue(bonus >= 0);
        assertTrue(bonus <= 500);
    }

    @Test
    @DisplayName("Validator Core should generate complete proof")
    public void testValidatorCoreValidation() {
        ProofOfAntiquity proof = validator.validate(100000);

        assertNotNull(proof);
        assertNotNull(proof.getValidatorId());
        assertTrue(proof.getTimestamp() > 0);
        assertNotNull(proof.getHardwareFingerprint());
        assertNotNull(proof.getEntropyProof());
        assertNotNull(proof.getScore());
        assertNotNull(proof.getAttestation());
        assertNotNull(proof.getMetadata());

        // Verify score calculation
        Score score = proof.getScore();
        assertTrue(score.getTotalScore() > 0);
        assertNotNull(score.getRank());
    }

    @Test
    @DisplayName("Validator Core should save and load proof")
    public void testValidatorCoreSaveLoad() throws IOException {
        // Generate proof
        ProofOfAntiquity proof = validator.validate(100000);

        // Create temp file
        Path tempFile = Files.createTempFile("proof_", ".json");
        tempFile.toFile().deleteOnExit();

        // Save proof
        validator.saveProof(proof, tempFile.toString());
        assertTrue(Files.exists(tempFile));

        // Load proof
        ProofOfAntiquity loadedProof = validator.loadProof(tempFile.toString());

        // Verify
        assertNotNull(loadedProof);
        assertEquals(proof.getValidatorId(), loadedProof.getValidatorId());
        assertEquals(proof.getTimestamp(), loadedProof.getTimestamp());
        assertNotNull(loadedProof.getHardwareFingerprint());
        assertNotNull(loadedProof.getEntropyProof());
    }

    @Test
    @DisplayName("Validator Core should validate proof file")
    public void testValidatorCoreValidationResult() throws IOException {
        // Generate valid proof
        ProofOfAntiquity proof = validator.validate(100000);

        // Create temp file
        Path tempFile = Files.createTempFile("proof_", ".json");
        tempFile.toFile().deleteOnExit();

        // Save proof
        validator.saveProof(proof, tempFile.toString());

        // Validate proof file
        ValidatorCore.ValidationResult result = validator.validateProofFile(tempFile.toString());

        assertTrue(result.isValid());
        assertTrue(result.getErrors().isEmpty());
        assertNotNull(result.getProof());
    }

    @Test
    @DisplayName("Validator Core should detect invalid proof file")
    public void testValidatorCoreInvalidFile() {
        // Test with non-existent file
        ValidatorCore.ValidationResult result = validator.validateProofFile("nonexistent.json");

        assertFalse(result.isValid());
        assertFalse(result.getErrors().isEmpty());
    }

    @Test
    @DisplayName("Score calculation should produce valid ranks")
    public void testScoreRanks() {
        ProofOfAntiquity proof = validator.validate(100000);
        Score score = proof.getScore();

        assertNotNull(score.getRank());
        assertTrue(score.getTotalScore() > 0);

        // Verify rank is one of the expected values
        String rank = score.getRank();
        assertTrue(rank.matches("Common|Uncommon|Rare|Epic|Legendary"));
    }

    @Test
    @DisplayName("Metadata should contain version information")
    public void testMetadataVersions() {
        ProofOfAntiquity proof = validator.validate(100000);
        Metadata metadata = proof.getMetadata();

        assertNotNull(metadata.getValidatorVersion());
        assertNotNull(metadata.getProtocolVersion());
        assertTrue(metadata.getValidatorVersion().contains("java"));
    }

    @Test
    @DisplayName("Hardware fingerprint should have BIOS info")
    public void testBIOSInfo() {
        HardwareFingerprint fingerprint = hardwareDetector.detect();

        assertNotNull(fingerprint.getBios());
        assertNotNull(fingerprint.getBios().getVendor());
    }

    @Test
    @DisplayName("Entropy seed should be unique")
    public void testEntropySeedUniqueness() {
        String seed1 = entropyGenerator.generateSeed();
        String seed2 = entropyGenerator.generateSeed();

        assertNotNull(seed1);
        assertNotNull(seed2);
        assertNotEquals(seed1, seed2);
        assertEquals(64, seed1.length()); // 32 bytes = 64 hex chars
        assertEquals(64, seed2.length());
    }

    @Test
    @DisplayName("Combined entropy should produce valid hash")
    public void testEntropyCombination() {
        String entropy1 = entropyGenerator.generateSeed();
        String entropy2 = entropyGenerator.generateSeed();

        String combined = entropyGenerator.combineEntropy(entropy1, entropy2);

        assertNotNull(combined);
        assertEquals(64, combined.length());
    }
}
