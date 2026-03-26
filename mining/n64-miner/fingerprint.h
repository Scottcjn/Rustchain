/**
 * N64 Hardware Fingerprint — Anti-Emulation Detection
 * 
 * Uses MIPS R4300i-specific timing characteristics to prove
 * the code is running on real N64 hardware, not an emulator.
 */

#ifndef FINGERPRINT_H
#define FINGERPRINT_H

#include "n64_miner.h"

/* ── MIPS CP0 Register Access ────────────────────────────────── */

/* Read CP0 Count register (increments at CPU_FREQ/2) */
static inline uint32_t read_count(void) {
    uint32_t val;
    __asm__ volatile("mfc0 %0, $9" : "=r"(val));
    return val;
}

/* Read CP0 Cause register */
static inline uint32_t read_cause(void) {
    uint32_t val;
    __asm__ volatile("mfc0 %0, $13" : "=r"(val));
    return val;
}

/* ── Cache Control ───────────────────────────────────────────── */

/* Invalidate D-cache line at address */
static inline void dcache_invalidate(volatile void *addr) {
    __asm__ volatile(
        "cache 0x11, 0(%0)"  /* D-cache Hit Invalidate */
        : : "r"(addr)
    );
}

/* Invalidate I-cache line at address */
static inline void icache_invalidate(volatile void *addr) {
    __asm__ volatile(
        "cache 0x10, 0(%0)"  /* I-cache Hit Invalidate */
        : : "r"(addr)
    );
}

/* ── Timing Helpers ──────────────────────────────────────────── */

/* Convert Count register ticks to nanoseconds */
static inline uint32_t ticks_to_ns(uint32_t ticks) {
    /* Count runs at 46.875 MHz → 1 tick ≈ 21.33 ns */
    return (ticks * 1000) / 47;  /* approximate */
}

/* Convert Count register ticks to CPU cycles */
static inline uint32_t ticks_to_cycles(uint32_t ticks) {
    return ticks * 2;  /* Count = CPU_FREQ / 2 */
}

/* ── Anti-Emulation Signatures ───────────────────────────────── */

/*
 * Emulator detection heuristics:
 *
 * 1. Count register: Real HW has measurable drift between reads.
 *    Emulators often return exact increments or skip cycles.
 *
 * 2. Cache timing: Real HW shows clear hit/miss bimodal distribution.
 *    Emulators often don't simulate cache at all (flat timing).
 *
 * 3. RSP pipeline: Vector unit operations on real hardware have
 *    consistent but slightly varying latency. Emulators are exact.
 *
 * 4. TLB miss: Real HW has ~30 cycle penalty. Emulators vary wildly.
 */

#define EMULATOR_FLAG_COUNT_EXACT    (1 << 0)  /* Zero drift = emulator */
#define EMULATOR_FLAG_CACHE_FLAT     (1 << 1)  /* No hit/miss delta */
#define EMULATOR_FLAG_RSP_EXACT      (1 << 2)  /* Zero jitter = emulator */
#define EMULATOR_FLAG_TLB_WRONG      (1 << 3)  /* TLB miss out of range */

#endif /* FINGERPRINT_H */
