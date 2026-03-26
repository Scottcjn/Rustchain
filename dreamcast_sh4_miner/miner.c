/* SPDX-License-Identifier: MIT */
/* miner.c - RustChain Miner for Sega Dreamcast (SH4 Linux) */

#include "fingerprint.h"
#include "networking.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define MINER_VERSION    "1.0.0"
#define MINER_ARCH      "sh4"
#define MINER_FAMILY    "dreamcast"
#define MINER_HZ        200000000
#define HEARTBEAT_SECS  60

typedef struct {
    const char *wallet;
    const char *node_url;
    int         attest_only;
} MinerArgs;

static void print_usage(const char *argv0) {
    printf("RustChain Dreamcast SH4 Miner v%s\n", MINER_VERSION);
    printf("Usage: %s --wallet WALLET [--node URL] [--attest-only] [--help]\n", argv0);
    printf("  --wallet ID      Your RustChain wallet/miner ID (required)\n");
    printf("  --node URL       RustChain node URL (default: rustchain.org)\n");
    printf("  --attest-only    Submit attestation and exit\n");
    printf("  --help           Show this help\n");
}

static bool parse_args(MinerArgs *args, int argc, char **argv) {
    int i;
    memset(args, 0, sizeof(*args));
    args->wallet = NULL;
    args->node_url = "rustchain.org";
    args->attest_only = 0;

    for (i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--wallet") == 0 && i + 1 < argc) {
            args->wallet = argv[++i];
        } else if (strcmp(argv[i], "--node") == 0 && i + 1 < argc) {
            args->node_url = argv[++i];
        } else if (strcmp(argv[i], "--attest-only") == 0) {
            args->attest_only = 1;
        } else if (strcmp(argv[i], "--help") == 0 || strcmp(argv[i], "-h") == 0) {
            print_usage(argv[0]);
            exit(0);
        } else {
            fprintf(stderr, "Unknown option: %s\n", argv[i]);
            print_usage(argv[0]);
            return false;
        }
    }

    if (!args->wallet) {
        fprintf(stderr, "ERROR: --wallet is required\n");
        print_usage(argv[0]);
        return false;
    }
    return true;
}

static void print_banner(void) {
    printf("\n");
    printf("  RustChain Dreamcast SH4 Miner v%s\n", MINER_VERSION);
    printf("  Architecture : %s (%s)\n", MINER_ARCH, MINER_FAMILY);
    printf("  CPU          : Hitachi SH7750 @ %d MHz\n", MINER_HZ / 1000000);
    printf("  Multiplier   : %.1fx (SH4 Antiquity Bonus)\n", MULTIPLIER);
    printf("\n");
}

static void print_fingerprint_report(const SH4Fingerprint *fp) {
    printf("--- Hardware Fingerprint Report ---\n");
    printf("  Architecture : %s\n", fingerprint_arch());
    printf("  Family       : %s\n", fingerprint_family());
    printf("  Multiplier   : %.1fx\n", get_multiplier());
    printf("  TMU drift    : %.2f ppm\n", fp->tmu.tmu_drift_ppm);
    printf("  TMU variance : %.6f\n", fp->tmu.tmu_variance);
    printf("  I-cache hit  : %u cycles\n", fp->cache.icache_hit_cycles);
    printf("  D-cache hit  : %u cycles\n", fp->cache.dcache_hit_cycles);
    printf("  FMUL latency : %u cycles\n", fp->fpu.fmul_latency);
    printf("  FADD latency : %u cycles\n", fp->fpu.fadd_latency);
    printf("  Anti-EMU     : %s\n",
           is_emulator(fp) ? "FAILED" : "PASS");
    printf("  FP Hash      : 0x%08x\n", fp->fp_hash);
    printf("----------------------------------------\n\n");
}

static int heartbeat_loop(MinerArgs *args, const SH4Fingerprint *fp) {
    int heartbeat_count = 0;
    printf("Entering heartbeat loop (%ds interval)...\n\n", HEARTBEAT_SECS);

    while (1) {
        printf("[Heartbeat #%d] Submitting attestation...\n", ++heartbeat_count);
        if (submit_attestation(args->wallet, fp->fp_hash, args->node_url)) {
            printf("  Result: SUCCESS\n");
        } else {
            printf("  Result: FAILED (will retry)\n");
        }
        printf("  Next heartbeat in %d seconds...\n\n", HEARTBEAT_SECS);
        sleep(HEARTBEAT_SECS);
    }
    return 0;
}

int main(int argc, char **argv) {
    MinerArgs args;
    SH4Fingerprint fp;

    if (!parse_args(&args, argc, argv)) {
        return 1;
    }

    print_banner();

    printf("Initializing network...\n");
    if (!net_init()) {
        fprintf(stderr, "ERROR: Failed to initialize network\n");
        return 1;
    }

    printf("Collecting SH4 hardware fingerprints...\n");
    printf("  (This may take 10-30 seconds for TMU sampling)\n\n");
    fingerprint_init(&fp);

    if (!fingerprint_collect(&fp)) {
        fprintf(stderr, "ERROR: Failed to collect hardware fingerprint\n");
        return 1;
    }

    print_fingerprint_report(&fp);

    if (is_emulator(&fp)) {
        printf("WARNING: Emulator detected! Real Dreamcast hardware required.\n\n");
    }

    printf("Submitting attestation...\n");
    if (!submit_attestation(args.wallet, fp.fp_hash, args.node_url)) {
        fprintf(stderr, "WARNING: Initial attestation failed.\n\n");
    } else {
        printf("Initial attestation: SUCCESS\n\n");
    }

    if (args.attest_only) {
        printf("Attest-only mode: exiting.\n");
        return 0;
    }

    printf("Miner is running! Multiplier: %.1fx\n", MULTIPLIER);
    return heartbeat_loop(&args, &fp);
}
