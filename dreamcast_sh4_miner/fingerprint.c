/* SPDX-License-Identifier: MIT */
/* fingerprint.c - SH4 Hardware Fingerprinting Implementation */

#include "fingerprint.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

/* SH4-specific inline assembly for TMU access */
static inline uint32_t sh4_read_tcnt0(void) {
    uint32_t val;
    __asm__ volatile ("movc %0, tcnt0, #0" : "=&r"(val));
    return val;
}

static inline void sh4_delay_cycles(uint32_t cycles) {
    __asm__ volatile (
        "1:\n\t"
        "tst r0, r0\n\t"
        "bf/s 1b\n\t"
        "add #-%0, r0"
        :
        : "i"(1), "r"(cycles)
        : "r0", "t", "memory"
    );
}

#define TMU_SAMPLES      256
#define CACHE_SAMPLES    1024
#define FPU_SAMPLES      512
#define TMU_FREQ         6750000  /* 27MHz / 4 */
#define EMULATOR_VARIANCE_THRESHOLD  0.001f

static uint32_t tmu_counter_read(void) {
    return sh4_read_tcnt0();
}

void tmu_collect(TMUFingerprint *fp) {
    uint32_t samples[TMU_SAMPLES];
    uint32_t i;
    uint64_t sum = 0, sum_sq = 0;
    uint32_t first, last;

    for (i = 0; i < TMU_SAMPLES; i++) {
        samples[i] = tmu_counter_read();
        sh4_delay_cycles(200000);
    }

    first = samples[0];
    last = samples[TMU_SAMPLES - 1];
    fp->tmu_base = first;
    fp->tmu_samples = TMU_SAMPLES;

    uint32_t elapsed_units = (last - first) & 0xFFFFFFFF;
    float elapsed_seconds = (float)elapsed_units / (float)TMU_FREQ;
    uint32_t expected_count = (uint32_t)(elapsed_seconds * TMU_FREQ);
    float drift_ppm = ((float)elapsed_units - (float)expected_count) / (float)expected_count * 1e6f;
    fp->tmu_drift_ppm = drift_ppm;

    for (i = 1; i < TMU_SAMPLES; i++) {
        uint32_t diff = samples[i] - samples[i-1];
        sum += diff;
        sum_sq += (uint64_t)diff * (uint64_t)diff;
    }

    float mean = (float)sum / (float)(TMU_SAMPLES - 1);
    float variance = ((float)sum_sq / (float)(TMU_SAMPLES - 1)) - (mean * mean);
    if (variance < 0) variance = 0;
    fp->tmu_variance = variance;
}

static uint8_t cache_buffer[8192] __attribute__((aligned(16)));

void cache_collect(CacheFingerprint *fp) {
    uint32_t i;
    volatile uint8_t *buf = (volatile uint8_t *)cache_buffer;

    for (i = 0; i < sizeof(cache_buffer); i += 16) {
        (void)buf[i];
    }

    uint64_t seq_sum = 0, seq_sum_sq = 0;
    uint64_t rand_sum = 0, rand_sum_sq = 0;
    uint32_t offsets[] = {0, 64, 128, 192, 256, 320, 384, 448};

    for (i = 0; i < CACHE_SAMPLES; i++) {
        uint32_t start, end;
        __asm__ volatile (
            "movc %0, tcor0, #0\n\t"
            "mov.b @%1, r0\n\t"
            "movc %2, tcor0, #0"
            : "=&r"(start)
            : "r"(buf + (i % 512) * 16)
            : "r"(end)
            : "r0", "memory", "tcor0"
        );
        uint32_t t = end - start;
        seq_sum += t;
        seq_sum_sq += (uint64_t)t * (uint64_t)t;
    }

    for (i = 0; i < CACHE_SAMPLES; i++) {
        uint32_t start, end;
        uint32_t off = offsets[i % 8];
        __asm__ volatile (
            "movc %0, tcor0, #0\n\t"
            "mov.b @%1, r0\n\t"
            "movc %2, tcor0, #0"
            : "=&r"(start)
            : "r"(buf + off)
            : "r"(end)
            : "r0", "memory", "tcor0"
        );
        uint32_t t = end - start;
        rand_sum += t;
        rand_sum_sq += (uint64_t)t * (uint64_t)t;
    }

    fp->icache_hit_cycles = (uint32_t)((float)seq_sum / (float)CACHE_SAMPLES);
    fp->dcache_hit_cycles = (uint32_t)((float)rand_sum / (float)CACHE_SAMPLES);
    fp->cache_miss_cycles = (uint32_t)((float)(rand_sum - seq_sum) / (float)CACHE_SAMPLES);

    float seq_mean = (float)seq_sum / (float)CACHE_SAMPLES;
    float seq_variance = ((float)seq_sum_sq / (float)CACHE_SAMPLES) - (seq_mean * seq_mean);
    if (seq_variance < 0) seq_variance = 0;
    fp->icache_variance = seq_variance;

    float rand_mean = (float)rand_sum / (float)CACHE_SAMPLES;
    float rand_variance = ((float)rand_sum_sq / (float)CACHE_SAMPLES) - (rand_mean * rand_mean);
    if (rand_variance < 0) rand_variance = 0;
    fp->dcache_variance = rand_variance;

    fp->icache_line_size = 16;
    fp->dcache_line_size = 16;
}

void fpu_collect(FPUFingerprint *fp) {
    float a = 1.234f, b = 5.678f, result = 0.0f;
    uint32_t i;
    uint32_t fmul_times[FPU_SAMPLES];
    uint32_t fadd_times[FPU_SAMPLES];
    uint32_t fdiv_times[64];

    uint32_t sr;
    __asm__ volatile ("stc sr, %0" : "=&r"(sr));
    fp->has_fpu = (sr & 0x8000) ? 1 : 0;
    fp->sh4_variant = 0;

    for (i = 0; i < FPU_SAMPLES; i++) {
        uint32_t start, end;
        __asm__ volatile (
            "movc %0, tcor0, #0\n\t"
            "fmul %2, %1\n\t"
            "fmov.s %1, %3\n\t"
            "movc %4, tcor0, #0"
            : "=&r"(start), "+&r"(a)
            : "r"(b), "r"(result), "r"(end)
            : "memory", "tcor0"
        );
        fmul_times[i] = end - start;
    }

    for (i = 0; i < FPU_SAMPLES; i++) {
        uint32_t start, end;
        __asm__ volatile (
            "movc %0, tcor0, #0\n\t"
            "fadd %2, %1\n\t"
            "fmov.s %1, %3\n\t"
            "movc %4, tcor0, #0"
            : "=&r"(start), "+&r"(a)
            : "r"(b), "r"(result), "r"(end)
            : "memory", "tcor0"
        );
        fadd_times[i] = end - start;
    }

    for (i = 0; i < 64; i++) {
        uint32_t start, end;
        __asm__ volatile (
            "movc %0, tcor0, #0\n\t"
            "fdiv %2, %1\n\t"
            "fmov.s %1, %3\n\t"
            "movc %4, tcor0, #0"
            : "=&r"(start), "+&r"(a)
            : "r"(b), "r"(result), "r"(end)
            : "memory", "tcor0"
        );
        fdiv_times[i] = end - start;
    }

    uint64_t fmul_sum = 0, fmul_sum_sq = 0;
    uint64_t fadd_sum = 0, fadd_sum_sq = 0;
    uint64_t fdiv_sum = 0;

    for (i = 0; i < FPU_SAMPLES; i++) {
        fmul_sum += fmul_times[i];
        fmul_sum_sq += (uint64_t)fmul_times[i] * (uint64_t)fmul_times[i];
    }
    for (i = 0; i < FPU_SAMPLES; i++) {
        fadd_sum += fadd_times[i];
        fadd_sum_sq += (uint64_t)fadd_times[i] * (uint64_t)fadd_times[i];
    }
    for (i = 0; i < 64; i++) {
        fdiv_sum += fdiv_times[i];
    }

    fp->fmul_latency = (uint32_t)(fmul_sum / FPU_SAMPLES);
    fp->fadd_latency = (uint32_t)(fadd_sum / FPU_SAMPLES);
    fp->fdiv_latency = (uint32_t)(fdiv_sum / 64);

    float fmul_mean = (float)fmul_sum / (float)FPU_SAMPLES;
    float fmul_variance = ((float)fmul_sum_sq / (float)FPU_SAMPLES) - (fmul_mean * fmul_mean);
    if (fmul_variance < 0) fmul_variance = 0;
    fp->fpu_variance = fmul_variance;
}

bool check_tmu_anomaly(const TMUFingerprint *fp) {
    return fp->tmu_variance < EMULATOR_VARIANCE_THRESHOLD;
}

bool check_cache_anomaly(const CacheFingerprint *fp) {
    return fp->icache_variance < EMULATOR_VARIANCE_THRESHOLD;
}

bool check_fpu_anomaly(const FPUFingerprint *fp) {
    return fp->fpu_variance < EMULATOR_VARIANCE_THRESHOLD;
}

bool check_anti_emu(const SH4Fingerprint *fp) {
    bool tmu_ok = !check_tmu_anomaly(&fp->tmu);
    bool cache_ok = !check_cache_anomaly(&fp->cache);
    bool fpu_ok = !check_fpu_anomaly(&fp->fpu);
    return (tmu_ok ? 1 : 0) + (cache_ok ? 1 : 0) + (fpu_ok ? 1 : 0) >= 2;
}

void fingerprint_init(SH4Fingerprint *fp) {
    memset(fp, 0, sizeof(*fp));
    fp->magic = 0x53483444;
    fp->version = 1;
    fp->struct_size = sizeof(*fp);
}

bool fingerprint_collect(SH4Fingerprint *fp) {
    tmu_collect(&fp->tmu);
    cache_collect(&fp->cache);
    fpu_collect(&fp->fpu);

    fp->anti_emu.anti_emu_pass = check_anti_emu(fp) ? 1 : 0;
    fp->anti_emu.tmu_valid = 1;
    fp->anti_emu.cache_valid = 1;
    fp->anti_emu.fpu_valid = fp->fpu.has_fpu ? 1 : 0;

    fp->fp_hash = fingerprint_hash(fp);
    return true;
}

bool is_emulator(const SH4Fingerprint *fp) {
    return !fp->anti_emu.anti_emu_pass;
}

const char* fingerprint_arch(void) { return DEVICE_ARCH; }
const char* fingerprint_family(void) { return DEVICE_FAMILY; }
float get_multiplier(void) { return MULTIPLIER; }

uint32_t fingerprint_hash(const SH4Fingerprint *fp) {
    uint32_t hash = 0x53483444;
    const uint32_t *data = (const uint32_t *)fp;
    int i;
    for (i = 0; i < (int)(sizeof(*fp) / 4) - 1; i++) {
        hash ^= data[i] + 0x9e3779b9 + (hash << 6) + (hash >> 2);
    }
    return hash;
}
