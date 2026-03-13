/*
 * RustChain Miner Core Definitions
 */

#ifndef MINER_H
#define MINER_H

#ifdef __cplusplus
extern "C" {
#endif

/* Miner version */
#define MINER_VERSION_MAJOR 0
#define MINER_VERSION_MINOR 1
#define MINER_VERSION_PATCH 0
#define MINER_VERSION_STRING "0.1.0-xt"

/* Mining configuration */
#define DEFAULT_BLOCK_TIME_SECS     600     /* 10 minutes */
#define DEFAULT_ATTESTATION_TTL     580     /* Slightly less than block time */
#define DEFAULT_NODE_PORT           443     /* HTTPS */

/* Mining state */
typedef struct {
    char wallet[64];
    char miner_id[64];
    char node_url[128];
    unsigned long block_time;
    unsigned long attestation_ttl;
    int verbose;
    int dry_run;
} miner_config_t;

typedef struct {
    unsigned long hashes_computed;
    unsigned long shares_submitted;
    unsigned long accepted_shares;
    unsigned long rejected_shares;
    unsigned long total_earnings;
    unsigned long uptime_seconds;
} miner_stats_t;

/*
 * Initialize miner with configuration
 */
int miner_init(miner_config_t *config);

/*
 * Run mining loop
 */
int miner_run(miner_config_t *config);

/*
 * Stop miner gracefully
 */
void miner_stop(void);

/*
 * Get miner statistics
 */
void miner_get_stats(miner_stats_t *stats);

/*
 * Check wallet balance
 */
int miner_check_balance(const char *wallet, unsigned long *balance);

#ifdef __cplusplus
}
#endif

#endif /* MINER_H */
