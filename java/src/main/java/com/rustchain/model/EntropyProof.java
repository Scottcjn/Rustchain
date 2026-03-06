package com.rustchain.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * Entropy proof data generated through hardware-based randomness.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
@JsonInclude(JsonInclude.Include.NON_NULL)
public class EntropyProof {

    @JsonProperty("method")
    private String method;

    @JsonProperty("seed")
    private String seed;

    @JsonProperty("iterations")
    private long iterations;

    @JsonProperty("duration_ms")
    private long durationMs;

    @JsonProperty("hash")
    private String hash;

    @JsonProperty("timestamp_start")
    private long timestampStart;

    @JsonProperty("timestamp_end")
    private long timestampEnd;

    public EntropyProof() {
    }

    // Getters and Setters
    public String getMethod() {
        return method;
    }

    public void setMethod(String method) {
        this.method = method;
    }

    public String getSeed() {
        return seed;
    }

    public void setSeed(String seed) {
        this.seed = seed;
    }

    public long getIterations() {
        return iterations;
    }

    public void setIterations(long iterations) {
        this.iterations = iterations;
    }

    public long getDurationMs() {
        return durationMs;
    }

    public void setDurationMs(long durationMs) {
        this.durationMs = durationMs;
    }

    public String getHash() {
        return hash;
    }

    public void setHash(String hash) {
        this.hash = hash;
    }

    public long getTimestampStart() {
        return timestampStart;
    }

    public void setTimestampStart(long timestampStart) {
        this.timestampStart = timestampStart;
    }

    public long getTimestampEnd() {
        return timestampEnd;
    }

    public void setTimestampEnd(long timestampEnd) {
        this.timestampEnd = timestampEnd;
    }
}
