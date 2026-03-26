/* SPDX-License-Identifier: MIT */
/* fingerprint.h - SH4 Hardware Fingerprinting Interface */

#ifndef FINGERPRINT_H
#define FINGERPRINT_H

#include <stdint.h>
#include <stdbool.h>

#define DEVICE_ARCH     "sh4"
#define DEVICE_FAMILY   "dreamcast"
#define DEVICE_MODEL    "SH7750"
#define MULTIPLIER      3.0f

#pragma pack(push, 1)
typedef struct {
    uint32_t    tmu_base;
    float       tmu_drift_ppm;
    float       tmu_variance;
    uint8_t     tmu_samples;
    uint8_t     _pad[3];
} TMUFingerprint;

typedef struct {
    uint32_t    icache_hit_cycles;
    uint32_t    dcache_hit_cycles;
    uint32_t    cache_miss_cycles;
    float       icache_variance;
    float       dcache_variance;
    uint8_t     icache_line_size;
    uint8_t     dcache_line_size;
    uint8_t     _pad[2];
} CacheFingerprint;

typedef struct {
    uint32_t    fmul_latency;
    uint32_t    fadd_latency;
    uint32_t    fdiv_latency;
    float       fpu_variance;
    uint8_t     has_fpu;
    uint8_t     sh4_variant;
    uint8_t     _pad[2];
} FPUFingerprint;

typedef struct {
    uint8_t     tmu_valid;
    uint8_t     cache_valid;
    uint8_t     fpu_valid;
    uint8_t     anti_emu_pass;
    uint8_t     _pad[4];
} AntiEmuFingerprint;

typedef struct {
    uint32_t    magic;
    uint16_t    version;
    uint16_t    struct_size;
    TMUFingerprint   tmu;
    CacheFingerprint cache;
    FPUFingerprint   fpu;
    AntiEmuFingerprint anti_emu;
    uint32_t    fp_hash;
    uint32_t    timestamp;
    uint32_t    _pad;
} SH4Fingerprint;
#pragma pack(pop)

void        fingerprint_init(SH4Fingerprint *fp);
bool        fingerprint_collect(SH4Fingerprint *fp);
uint32_t    fingerprint_hash(const SH4Fingerprint *fp);
bool        is_emulator(const SH4Fingerprint *fp);
const char* fingerprint_arch(void);
const char* fingerprint_family(void);
float       get_multiplier(void);
void        tmu_collect(TMUFingerprint *fp);
void        cache_collect(CacheFingerprint *fp);
void        fpu_collect(FPUFingerprint *fp);
bool        check_anti_emu(const SH4Fingerprint *fp);
bool        check_tmu_anomaly(const TMUFingerprint *fp);
bool        check_cache_anomaly(const CacheFingerprint *fp);
bool        check_fpu_anomaly(const FPUFingerprint *fp);

#endif /* FINGERPRINT_H */
