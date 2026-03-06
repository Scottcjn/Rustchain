package com.rustchain.examples;

import com.rustchain.model.ProofOfAntiquity;
import com.rustchain.model.Score;
import com.rustchain.validator.ValidatorCore;

/**
 * Example: Basic validation and proof generation.
 * 
 * Compile: javac -cp rustchain.jar BasicValidation.java
 * Run: java -cp .:rustchain.jar BasicValidation
 */
public class BasicValidation {

    public static void main(String[] args) {
        try {
            // Create validator
            ValidatorCore validator = new ValidatorCore();
            
            System.out.println("RustChain Basic Validation Example");
            System.out.println("==================================");
            System.out.println("Validator ID: " + validator.getValidatorId());
            System.out.println();
            
            // Generate proof (with 500k iterations for faster execution)
            System.out.println("Generating proof...");
            ProofOfAntiquity proof = validator.validate(500_000);
            
            // Display results
            Score score = proof.getScore();
            System.out.println();
            System.out.println("Results:");
            System.out.println("  CPU: " + proof.getHardwareFingerprint().getCpu().getModel());
            System.out.println("  Era: " + proof.getHardwareFingerprint().getCpu().getEra());
            System.out.println("  Total Score: " + score.getTotalScore());
            System.out.println("  Rank: " + score.getRank());
            System.out.println();
            
            // Save proof
            String outputFile = "example_proof.json";
            validator.saveProof(proof, outputFile);
            System.out.println("Proof saved to: " + outputFile);
            
        } catch (Exception e) {
            System.err.println("Error: " + e.getMessage());
            e.printStackTrace();
        }
    }
}
