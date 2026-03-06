package com.rustchain.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.Map;

/**
 * Additional metadata for the proof.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
@JsonInclude(JsonInclude.Include.NON_NULL)
public class Metadata {

    @JsonProperty("validator_version")
    private String validatorVersion;

    @JsonProperty("protocol_version")
    private String protocolVersion;

    @JsonProperty("network")
    private String network;

    @JsonProperty("epoch")
    private long epoch;

    @JsonProperty("block_height")
    private long blockHeight;

    @JsonProperty("badges")
    private java.util.List<String> badges;

    @JsonProperty("extra")
    private Map<String, Object> extra;

    public Metadata() {
    }

    // Getters and Setters
    public String getValidatorVersion() {
        return validatorVersion;
    }

    public void setValidatorVersion(String validatorVersion) {
        this.validatorVersion = validatorVersion;
    }

    public String getProtocolVersion() {
        return protocolVersion;
    }

    public void setProtocolVersion(String protocolVersion) {
        this.protocolVersion = protocolVersion;
    }

    public String getNetwork() {
        return network;
    }

    public void setNetwork(String network) {
        this.network = network;
    }

    public long getEpoch() {
        return epoch;
    }

    public void setEpoch(long epoch) {
        this.epoch = epoch;
    }

    public long getBlockHeight() {
        return blockHeight;
    }

    public void setBlockHeight(long blockHeight) {
        this.blockHeight = blockHeight;
    }

    public java.util.List<String> getBadges() {
        return badges;
    }

    public void setBadges(java.util.List<String> badges) {
        this.badges = badges;
    }

    public Map<String, Object> getExtra() {
        return extra;
    }

    public void setExtra(Map<String, Object> extra) {
        this.extra = extra;
    }
}
