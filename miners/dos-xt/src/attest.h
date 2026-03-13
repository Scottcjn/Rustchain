/*
 * Hardware Attestation Module
 * 
 * Implements the RustChain attestation protocol:
 * 1. Get challenge nonce from node
 * 2. Collect entropy (hardware timing measurements)
 * 3. Generate commitment hash
 * 4. Submit attestation report
 */

#ifndef ATTEST_H
#define ATTEST_H

#ifdef __cplusplus
extern "C" {
#endif

/* Maximum sizes */
#define MAX_NONCE_SIZE      64
#define MAX_WALLET_SIZE     64
#define MAX_MINER_ID_SIZE   64
#define MAX_HASH_SIZE       64

/* Entropy data structure */
typedef struct {
    unsigned long mean_ns;        /* Mean execution time (nanoseconds) */
    unsigned long variance_ns;    /* Variance (used as entropy score) */
    unsigned long min_ns;         /* Minimum time */
    unsigned long max_ns;         /* Maximum time */
    unsigned int sample_count;    /* Number of samples */
    unsigned long samples[12];    /* First 12 samples */
} entropy_data_t;

/* Attestation report structure */
typedef struct {
    char miner[MAX_WALLET_SIZE];
    char miner_id[MAX_MINER_ID_SIZE];
    char nonce[MAX_NONCE_SIZE];
    entropy_data_t entropy;
    char commitment[MAX_HASH_SIZE];
    unsigned long entropy_score;
} attestation_report_t;

/*
 * Initialize attestation module
 */
int attest_init(void);

/*
 * Collect entropy from hardware timing measurements
 * Uses PIT timer to measure CPU execution variance
 */
void collect_entropy(entropy_data_t *entropy, unsigned int samples);

/*
 * Generate SHA256 hash (simplified for 8088)
 * Note: Full SHA256 is expensive; we use a simplified version
 */
void sha256_simple(const char *data, unsigned int len, char *hash);

/*
 * Generate commitment hash
 * commitment = SHA256(nonce + wallet + entropy_json)
 */
void generate_commitment(const char *nonce, const char *wallet, 
                         const entropy_data_t *entropy, char *commitment);

/*
 * Get challenge nonce from node
 */
int get_challenge_nonce(const char *node_url, char *nonce, unsigned int nonce_size);

/*
 * Submit attestation report to node
 */
int submit_attestation(const char *node_url, const attestation_report_t *report);

/*
 * Complete attestation flow
 * 1. Get challenge
 * 2. Collect entropy
 * 3. Generate commitment
 * 4. Submit report
 *
 * Returns: 0 on success, -1 on error
 */
int attest_to_node(const char *node_url, const char *wallet, const char *miner_id);

#ifdef __cplusplus
}
#endif

#endif /* ATTEST_H */
