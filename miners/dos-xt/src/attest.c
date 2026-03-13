/*
 * Hardware Attestation Implementation
 */

#include <stdio.h>
#include <string.h>
#include <dos.h>

#include "attest.h"
#include "hw_xt.h"
#include "pit.h"
#include "network.h"

/*
 * Initialize attestation module
 */
int attest_init(void)
{
    return 0;
}

/*
 * Collect entropy from hardware timing
 */
void collect_entropy(entropy_data_t *entropy, unsigned int samples)
{
    unsigned int i;
    unsigned long times[48];
    
    if (samples > 48) samples = 48;
    
    /* Collect timing samples */
    for (i = 0; i < samples; i++) {
        unsigned long start = pit_read_counter0();
        
        /* Execute fixed computation */
        volatile unsigned long acc = 0;
        int j;
        for (j = 0; j < 1000; j++) {
            acc ^= (j * 31UL) & 0xFFFFFFFFUL;
        }
        
        unsigned long end = pit_read_counter0();
        
        /* Calculate elapsed ticks */
        if (end > start) {
            times[i] = (65536 - start) + end;
        } else {
            times[i] = start - end;
        }
    }
    
    /* Calculate statistics */
    unsigned long sum = 0;
    entropy->min_ns = 0xFFFFFFFFUL;
    entropy->max_ns = 0;
    
    for (i = 0; i < samples; i++) {
        sum += times[i];
        
        if (times[i] < entropy->min_ns) {
            entropy->min_ns = times[i];
        }
        if (times[i] > entropy->max_ns) {
            entropy->max_ns = times[i];
        }
        
        /* Store first 12 samples */
        if (i < 12) {
            entropy->samples[i] = times[i];
        }
    }
    
    entropy->mean_ns = sum / samples;
    entropy->sample_count = samples;
    
    /* Calculate variance */
    unsigned long var_sum = 0;
    for (i = 0; i < samples; i++) {
        long diff = (long)times[i] - (long)entropy->mean_ns;
        var_sum += (diff * diff);
    }
    entropy->variance_ns = var_sum / samples;
    
    /* Use variance as entropy score */
    entropy->entropy_score = entropy->variance_ns;
}

/*
 * Simplified SHA256 (placeholder - full implementation is large)
 * For production, would need complete SHA256 implementation
 */
void sha256_simple(const char *data, unsigned int len, char *hash)
{
    /* 
     * NOTE: This is a PLACEHOLDER.
     * Full SHA256 for 8088 requires ~4KB of code.
     * For the actual implementation, we would:
     * 1. Use a compact SHA256 implementation
     * 2. Or use lookup tables in XMS/EMS memory
     * 3. Or delegate to a coprocessor if available
     *
     * For now, generate a simple hash (NOT CRYPTOGRAPHICALLY SECURE)
     */
    
    unsigned long h0 = 0x6a09e667UL;
    unsigned long h1 = 0xbb67ae85UL;
    unsigned long h2 = 0x3c6ef372UL;
    unsigned long h3 = 0xa54ff53aUL;
    
    unsigned int i;
    for (i = 0; i < len; i++) {
        unsigned long temp = h0;
        h0 = h1;
        h1 = h2;
        h2 = h3;
        h3 = temp ^ (data[i] * 0x9e3779b9UL);
    }
    
    /* Convert to hex string */
    sprintf(hash, "%08lx%08lx%08lx%08lx", h0, h1, h2, h3);
}

/*
 * Generate commitment hash
 */
void generate_commitment(const char *nonce, const char *wallet,
                         const entropy_data_t *entropy, char *commitment)
{
    char data[512];
    
    /* Build data string: nonce + wallet + entropy */
    sprintf(data, "%s%s%lu%lu%lu%lu%u",
            nonce, wallet,
            entropy->mean_ns, entropy->variance_ns,
            entropy->min_ns, entropy->max_ns,
            entropy->sample_count);
    
    sha256_simple(data, strlen(data), commitment);
}

/*
 * Get challenge nonce from node
 */
int get_challenge_nonce(const char *node_url, char *nonce, unsigned int nonce_size)
{
    char response[256];
    
    /* POST to /attest/challenge */
    int ret = http_post(node_url, "/attest/challenge", "{}", response, sizeof(response));
    
    if (ret != 0) {
        return -1;
    }
    
    /* Parse JSON response to extract nonce */
    /* Simple parsing: look for "nonce":"value" */
    char *start = strstr(response, "\"nonce\"");
    if (!start) {
        return -1;
    }
    
    start = strchr(start, ':');
    if (!start) {
        return -1;
    }
    
    start++;  /* Skip ':' */
    
    /* Skip whitespace and quotes */
    while (*start == ' ' || *start == '"' || *start == ':') {
        start++;
    }
    
    /* Extract nonce value */
    unsigned int i;
    for (i = 0; i < nonce_size - 1 && *start && *start != '"'; i++) {
        nonce[i] = *start++;
    }
    nonce[i] = '\0';
    
    return 0;
}

/*
 * Submit attestation report
 */
int submit_attestation(const char *node_url, const attestation_report_t *report)
{
    char json[1024];
    char response[256];
    
    /* Build JSON report */
    sprintf(json,
        "{"
        "\"miner\":\"%s\","
        "\"miner_id\":\"%s\","
        "\"nonce\":\"%s\","
        "\"entropy\":{"
            "\"mean_ns\":%lu,"
            "\"variance_ns\":%lu,"
            "\"min_ns\":%lu,"
            "\"max_ns\":%lu,"
            "\"sample_count\":%u"
        "},"
        "\"commitment\":\"%s\","
        "\"entropy_score\":%lu"
        "}",
        report->miner, report->miner_id, report->nonce,
        report->entropy.mean_ns, report->entropy.variance_ns,
        report->entropy.min_ns, report->entropy.max_ns,
        report->entropy.sample_count,
        report->commitment, report->entropy_score);
    
    /* POST to /attest/submit */
    int ret = http_post(node_url, "/attest/submit", json, response, sizeof(response));
    
    if (ret != 0) {
        return -1;
    }
    
    /* Check response for success */
    if (strstr(response, "\"ok\":true") || strstr(response, "\"ok\": true")) {
        return 0;
    }
    
    return -1;
}

/*
 * Complete attestation flow
 */
int attest_to_node(const char *node_url, const char *wallet, const char *miner_id)
{
    attestation_report_t report;
    char nonce[MAX_NONCE_SIZE];
    
    /* Initialize report */
    memset(&report, 0, sizeof(report));
    strncpy(report.miner, wallet, sizeof(report.miner) - 1);
    strncpy(report.miner_id, miner_id, sizeof(report.miner_id) - 1);
    
    /* Step 1: Get challenge nonce */
    printf("[ATTEST] Getting challenge nonce...\n");
    if (get_challenge_nonce(node_url, nonce, sizeof(nonce)) != 0) {
        printf("[ATTEST] Failed to get challenge (network may be unavailable)\n");
        return -1;
    }
    strncpy(report.nonce, nonce, sizeof(report.nonce) - 1);
    printf("[ATTEST] Nonce: %.16s...\n", nonce);
    
    /* Step 2: Collect entropy */
    printf("[ATTEST] Collecting entropy...\n");
    collect_entropy(&report.entropy, 48);
    printf("[ATTEST] Entropy score: %lu\n", report.entropy.entropy_score);
    
    /* Step 3: Generate commitment */
    printf("[ATTEST] Generating commitment...\n");
    generate_commitment(nonce, wallet, &report.entropy, report.commitment);
    printf("[ATTEST] Commitment: %.16s...\n", report.commitment);
    
    /* Step 4: Submit report */
    printf("[ATTEST] Submitting attestation report...\n");
    if (submit_attestation(node_url, &report) != 0) {
        printf("[ATTEST] Failed to submit report\n");
        return -1;
    }
    
    printf("[ATTEST] Attestation successful!\n");
    return 0;
}
