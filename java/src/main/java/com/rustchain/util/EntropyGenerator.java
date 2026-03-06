package com.rustchain.util;

import com.rustchain.model.EntropyProof;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.util.Random;

/**
 * Generates entropy proofs through CPU-intensive operations.
 * This simulates the proof-of-work aspect of RustChain validation.
 */
public class EntropyGenerator {

    private static final Logger logger = LoggerFactory.getLogger(EntropyGenerator.class);

    private static final String DEFAULT_METHOD = "cpu_loop_hash";
    private static final long DEFAULT_ITERATIONS = 1_000_000;

    private final Random random;

    public EntropyGenerator() {
        this.random = new SecureRandom();
    }

    /**
     * Generate an entropy proof using CPU-intensive hashing.
     *
     * @return EntropyProof containing the proof data
     */
    public EntropyProof generateProof() {
        return generateProof(DEFAULT_ITERATIONS);
    }

    /**
     * Generate an entropy proof with custom iteration count.
     *
     * @param iterations Number of hash iterations
     * @return EntropyProof containing the proof data
     */
    public EntropyProof generateProof(long iterations) {
        logger.info("Generating entropy proof with {} iterations", iterations);

        EntropyProof proof = new EntropyProof();
        proof.setMethod(DEFAULT_METHOD);
        proof.setIterations(iterations);

        // Generate initial seed
        String seed = generateSeed();
        proof.setSeed(seed);

        // Record start time
        long startTime = System.currentTimeMillis();
        proof.setTimestampStart(startTime);

        // Perform CPU-intensive hashing
        String hash = performHashIterations(seed, iterations);
        proof.setHash(hash);

        // Record end time
        long endTime = System.currentTimeMillis();
        proof.setTimestampEnd(endTime);
        proof.setDurationMs(endTime - startTime);

        logger.info("Entropy proof generated in {}ms, hash: {}", 
                proof.getDurationMs(), 
                hash.substring(0, Math.min(16, hash.length())) + "...");

        return proof;
    }

    /**
     * Generate a random seed using SecureRandom.
     */
    public String generateSeed() {
        byte[] seedBytes = new byte[32];
        random.nextBytes(seedBytes);
        return bytesToHex(seedBytes);
    }

    /**
     * Perform iterative hashing to generate entropy.
     */
    private String performHashIterations(String input, long iterations) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] current = input.getBytes(StandardCharsets.UTF_8);

            for (long i = 0; i < iterations; i++) {
                current = digest.digest(current);
                
                // Mix in counter to prevent optimization
                current[0] ^= (byte) (i & 0xFF);
                current[1] ^= (byte) ((i >> 8) & 0xFF);
            }

            return bytesToHex(current);
        } catch (NoSuchAlgorithmException e) {
            logger.error("SHA-256 not available", e);
            return "error_no_sha256";
        }
    }

    /**
     * Generate entropy using timing variations.
     * This method uses loop timing to generate additional entropy.
     *
     * @param durationMs Duration to run entropy generation
     * @return Additional entropy as hex string
     */
    public String generateTimingEntropy(long durationMs) {
        logger.debug("Generating timing entropy for {}ms", durationMs);

        StringBuilder entropyBuilder = new StringBuilder();
        long endTime = System.currentTimeMillis() + durationMs;
        long counter = 0;

        while (System.currentTimeMillis() < endTime) {
            // Busy loop with varying iterations
            long iterations = (random.nextInt(1000) + 1) * 1000;
            long start = System.nanoTime();
            
            for (long i = 0; i < iterations; i++) {
                counter++;
            }
            
            long elapsed = System.nanoTime() - start;
            
            // Extract entropy from timing variations
            byte timingByte = (byte) (elapsed & 0xFF);
            entropyBuilder.append(String.format("%02x", timingByte));
        }

        logger.debug("Generated {} bytes of timing entropy", entropyBuilder.length() / 2);
        return entropyBuilder.toString();
    }

    /**
     * Combine multiple entropy sources.
     *
     * @param entropySources Array of entropy hex strings
     * @return Combined hash of all entropy sources
     */
    public String combineEntropy(String... entropySources) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            
            for (String entropy : entropySources) {
                if (entropy != null && !entropy.isEmpty()) {
                    digest.update(entropy.getBytes(StandardCharsets.UTF_8));
                }
            }
            
            return bytesToHex(digest.digest());
        } catch (NoSuchAlgorithmException e) {
            logger.error("SHA-256 not available", e);
            return "error_combine";
        }
    }

    /**
     * Calculate entropy bonus score based on proof quality.
     *
     * @param proof The entropy proof
     * @return Bonus score (0-500)
     */
    public int calculateEntropyBonus(EntropyProof proof) {
        int bonus = 0;

        // Bonus for longer duration (more work)
        long duration = proof.getDurationMs();
        if (duration > 5000) {
            bonus += 200;
        } else if (duration > 2000) {
            bonus += 150;
        } else if (duration > 1000) {
            bonus += 100;
        } else if (duration > 500) {
            bonus += 50;
        }

        // Bonus for higher iterations
        long iterations = proof.getIterations();
        if (iterations > 10_000_000) {
            bonus += 300;
        } else if (iterations > 5_000_000) {
            bonus += 200;
        } else if (iterations > 1_000_000) {
            bonus += 100;
        }

        // Bonus for hash quality (leading zeros)
        String hash = proof.getHash();
        if (hash != null) {
            int leadingZeros = countLeadingZeros(hash);
            bonus += Math.min(leadingZeros * 50, 200);
        }

        return Math.min(bonus, 500); // Cap at 500
    }

    private int countLeadingZeros(String hex) {
        int count = 0;
        for (char c : hex.toCharArray()) {
            if (c == '0') {
                count++;
            } else {
                break;
            }
        }
        return count;
    }

    /**
     * Convert byte array to hex string.
     */
    private String bytesToHex(byte[] bytes) {
        StringBuilder sb = new StringBuilder(bytes.length * 2);
        for (byte b : bytes) {
            sb.append(String.format("%02x", b));
        }
        return sb.toString();
    }

    /**
     * Verify an entropy proof (basic validation).
     *
     * @param proof The proof to verify
     * @return true if proof appears valid
     */
    public boolean verifyProof(EntropyProof proof) {
        if (proof == null) return false;
        if (proof.getHash() == null || proof.getHash().isEmpty()) return false;
        if (proof.getSeed() == null || proof.getSeed().isEmpty()) return false;
        if (proof.getIterations() <= 0) return false;
        if (proof.getDurationMs() <= 0) return false;

        // Verify hash format (should be 64 hex chars for SHA-256)
        if (proof.getHash().length() != 64) return false;

        return true;
    }
}
