/**
 * N64 Mining ROM — RustChain Attestation Protocol
 * Target: MIPS R4300i @ 93.75 MHz (VR4300)
 * 
 * Bounty: Rustchain #1877 (200 RTC)
 */

#ifndef N64_MINER_H
#define N64_MINER_H

#include <stdint.h>

/* ── Device Identity ─────────────────────────────────────────── */
#define DEVICE_ARCH       "mips_r4300"
#define DEVICE_FAMILY     "N64"
#define CPU_FREQ_HZ       93750000   /* 93.75 MHz */
#define COUNT_FREQ_HZ     46875000   /* CPU/2 — Count register rate */

/* ── Cache Geometry ──────────────────────────────────────────── */
#define DCACHE_SIZE       8192       /* 8 KB data cache */
#define ICACHE_SIZE       16384      /* 16 KB instruction cache */
#define CACHE_LINE_SIZE   16         /* 16 bytes per line */
#define DCACHE_LINES      (DCACHE_SIZE / CACHE_LINE_SIZE)
#define ICACHE_LINES      (ICACHE_SIZE / CACHE_LINE_SIZE)

/* ── TLB ─────────────────────────────────────────────────────── */
#define TLB_ENTRIES       32
#define TLB_MISS_PENALTY  30         /* ~30 cycles on real hardware */

/* ── Fingerprint Thresholds (anti-emulation) ─────────────────── */
#define COUNT_DRIFT_MAX_NS   500     /* Real HW: <500ns jitter */
#define COUNT_DRIFT_MIN_NS   50      /* Emulators often have 0 or >1000 */
#define CACHE_HIT_MAX_CYC    5       /* D-cache hit: 1-4 cycles */
#define CACHE_MISS_MIN_CYC   20      /* D-cache miss: 20-60 cycles */
#define RSP_JITTER_MAX_NS    200     /* RSP pipeline jitter */
#define TLB_MISS_MIN_CYC     25      /* Real TLB miss: 25-35 cycles */
#define TLB_MISS_MAX_CYC     40

/* ── Protocol Constants ──────────────────────────────────────── */
#define ATTEST_MAGIC         0x52544331  /* "RTC1" */
#define ATTEST_VERSION       1
#define FINGERPRINT_SAMPLES  64
#define SERIAL_BAUD          115200

/* ── Attestation Packet ──────────────────────────────────────── */
typedef struct {
    uint32_t magic;
    uint8_t  version;
    uint8_t  type;           /* 0=attest, 1=heartbeat, 2=balance_req, 4=reattest_req */
    uint16_t payload_len;
} packet_header_t;

#define PKT_TYPE_ATTEST      0
#define PKT_TYPE_HEARTBEAT   1
#define PKT_TYPE_BALANCE     2
#define PKT_TYPE_EPOCH_ACK   3
#define PKT_TYPE_REATTEST    4

typedef struct {
    uint32_t count_drift_ns;
    uint32_t cache_d_hit_cycles;
    uint32_t cache_d_miss_cycles;
    uint32_t cache_i_hit_cycles;
    uint32_t cache_i_miss_cycles;
    uint32_t rsp_jitter_ns;
    uint32_t tlb_miss_cycles;
    uint8_t  fingerprint_hash[32];   /* SHA-256 of all measurements */
} hw_fingerprint_t;

typedef struct {
    packet_header_t header;
    char            device_arch[16];
    char            device_family[8];
    char            miner_id[32];
    uint32_t        epoch;
    hw_fingerprint_t fingerprint;
} attestation_packet_t;

typedef struct {
    packet_header_t header;
    uint32_t        epoch;
    uint64_t        balance_rtc;     /* in smallest unit (1e-9 RTC) */
    uint32_t        multiplier_x100; /* 400 = 4.0x */
} epoch_ack_packet_t;

/* ── Mining State ────────────────────────────────────────────── */
typedef enum {
    STATE_INIT,
    STATE_FINGERPRINT,
    STATE_ATTEST,
    STATE_MINING,
    STATE_DISPLAY,
    STATE_ERROR
} miner_state_t;

typedef struct {
    miner_state_t    state;
    uint32_t         current_epoch;
    uint64_t         total_earned;      /* lifetime RTC earned (nanoRTC) */
    uint64_t         session_earned;    /* this session */
    uint32_t         attestations_sent;
    uint32_t         attestations_ok;
    hw_fingerprint_t last_fingerprint;
    uint8_t          mining_active;
    uint8_t          display_active;
    char             wallet[64];
} miner_context_t;

/* ── Function Prototypes ─────────────────────────────────────── */

/* fingerprint.c */
void     fingerprint_init(void);
int      fingerprint_collect(hw_fingerprint_t *fp);
int      fingerprint_validate(const hw_fingerprint_t *fp);
uint32_t measure_count_drift(void);
uint32_t measure_cache_latency(int is_icache, int force_miss);
uint32_t measure_rsp_jitter(void);
uint32_t measure_tlb_miss(void);
void     fingerprint_hash(hw_fingerprint_t *fp);

/* n64_miner.c */
void     miner_init(miner_context_t *ctx, const char *wallet);
int      miner_attest(miner_context_t *ctx);
void     miner_loop(miner_context_t *ctx);
void     miner_display(const miner_context_t *ctx);
int      serial_send(const void *data, uint32_t len);
int      serial_recv(void *buf, uint32_t max_len, uint32_t timeout_ms);

#endif /* N64_MINER_H */
