#ifndef FINGERPRINT_H
#define FINGERPRINT_H

#include <stdint.h>

typedef struct {
    double mean_ns;
    double variance_ns;
    double min_ns;
    double max_ns;
    int sample_count;
} entropy_data_t;

typedef struct {
    const char *nonce;
    char commitment_hex[65];
    entropy_data_t entropy;
    double entropy_score;
} entropy_report_t;

typedef struct {
    char cpu_type[64];
    int has_cpuid;
    uint32_t cpuid_result;
    int has_387;
    char fpu_type[32];
    int memory_kb;
    int cache_kb;
    int bus_speed_mhz;
    char mac[18];
    char hostname[32];
} fingerprint_t;

void fingerprint_collect(fingerprint_t *fp);

#endif
