package com.rustchain.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * Scoring information for the validator.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
@JsonInclude(JsonInclude.Include.NON_NULL)
public class Score {

    @JsonProperty("base_score")
    private int baseScore;

    @JsonProperty("vintage_bonus")
    private int vintageBonus;

    @JsonProperty("entropy_bonus")
    private int entropyBonus;

    @JsonProperty("uptime_bonus")
    private int uptimeBonus;

    @JsonProperty("total_score")
    private int totalScore;

    @JsonProperty("rank")
    private String rank;

    @JsonProperty("multiplier")
    private double multiplier;

    public Score() {
    }

    // Getters and Setters
    public int getBaseScore() {
        return baseScore;
    }

    public void setBaseScore(int baseScore) {
        this.baseScore = baseScore;
    }

    public int getVintageBonus() {
        return vintageBonus;
    }

    public void setVintageBonus(int vintageBonus) {
        this.vintageBonus = vintageBonus;
    }

    public int getEntropyBonus() {
        return entropyBonus;
    }

    public void setEntropyBonus(int entropyBonus) {
        this.entropyBonus = entropyBonus;
    }

    public int getUptimeBonus() {
        return uptimeBonus;
    }

    public void setUptimeBonus(int uptimeBonus) {
        this.uptimeBonus = uptimeBonus;
    }

    public int getTotalScore() {
        return totalScore;
    }

    public void setTotalScore(int totalScore) {
        this.totalScore = totalScore;
    }

    public String getRank() {
        return rank;
    }

    public void setRank(String rank) {
        this.rank = rank;
    }

    public double getMultiplier() {
        return multiplier;
    }

    public void setMultiplier(double multiplier) {
        this.multiplier = multiplier;
    }

    /**
     * Calculate total score from components.
     */
    public void calculateTotal() {
        this.totalScore = (int) ((baseScore + vintageBonus + entropyBonus + uptimeBonus) * multiplier);
    }
}
