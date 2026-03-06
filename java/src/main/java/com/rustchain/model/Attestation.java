package com.rustchain.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

/**
 * Attestation data containing signatures and verification info.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
@JsonInclude(JsonInclude.Include.NON_NULL)
public class Attestation {

    @JsonProperty("signature")
    private String signature;

    @JsonProperty("public_key")
    private String publicKey;

    @JsonProperty("algorithm")
    private String algorithm;

    @JsonProperty("witnesses")
    private List<Witness> witnesses;

    @JsonProperty("verified")
    private boolean verified;

    public Attestation() {
    }

    // Getters and Setters
    public String getSignature() {
        return signature;
    }

    public void setSignature(String signature) {
        this.signature = signature;
    }

    public String getPublicKey() {
        return publicKey;
    }

    public void setPublicKey(String publicKey) {
        this.publicKey = publicKey;
    }

    public String getAlgorithm() {
        return algorithm;
    }

    public void setAlgorithm(String algorithm) {
        this.algorithm = algorithm;
    }

    public List<Witness> getWitnesses() {
        return witnesses;
    }

    public void setWitnesses(List<Witness> witnesses) {
        this.witnesses = witnesses;
    }

    public boolean isVerified() {
        return verified;
    }

    public void setVerified(boolean verified) {
        this.verified = verified;
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    @JsonInclude(JsonInclude.Include.NON_NULL)
    public static class Witness {
        @JsonProperty("node_id")
        private String nodeId;

        @JsonProperty("signature")
        private String signature;

        @JsonProperty("timestamp")
        private long timestamp;

        public Witness() {
        }

        // Getters and Setters
        public String getNodeId() {
            return nodeId;
        }

        public void setNodeId(String nodeId) {
            this.nodeId = nodeId;
        }

        public String getSignature() {
            return signature;
        }

        public void setSignature(String signature) {
            this.signature = signature;
        }

        public long getTimestamp() {
            return timestamp;
        }

        public void setTimestamp(long timestamp) {
            this.timestamp = timestamp;
        }
    }
}
