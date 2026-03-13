/*
 * Hardware Fingerprint Collection for PS1
 * Collects unique hardware identifiers for attestation
 */

#include "fingerprint.h"
#include <psxapi.h>
#include <psxgpu.h>
#include <stdint.h>
#include <string.h>

/* BIOS ROM location */
#define BIOS_BASE 0xBFC00000
#define BIOS_SIZE 0x80000  /* 512 KB */

/* Get BIOS version string */
static void get_bios_version(char* buf, int len) {
    /* BIOS version is at offset 0 in BIOS ROM */
    const char* bios_str = (const char*)BIOS_BASE;
    
    /* Copy up to len-1 characters */
    int i;
    for (i = 0; i < len - 1 && bios_str[i] != '\0'; i++) {
        buf[i] = bios_str[i];
    }
    buf[i] = '\0';
}

/* Calculate simple hash of BIOS version */
static uint32_t hash_bios_version(const char* str) {
    uint32_t hash = 5381;
    int c;
    
    while ((c = *str++)) {
        hash = ((hash << 5) + hash) + c;  /* hash * 33 + c */
    }
    
    return hash;
}

/* Measure CD-ROM timing (mechanical variance) */
static int measure_cdrom_timing(void) {
    /* 
     * CD-ROM access timing varies due to:
     * - Motor speed variance
     * - Laser positioning
     * - Mechanical wear
     * 
     * We measure the time to read a specific sector.
     */
    
    uint32_t start, end;
    volatile uint8_t data;
    
    /* Try to read from CD-ROM controller */
    /* Note: This is simplified - real implementation would use CD-ROM registers */
    
    start = GetRCnt(0);
    
    /* Access CD-ROM controller registers */
    /* In real implementation, this would trigger actual CD read */
    /* For now, we simulate with a delay loop that varies by hardware */
    for (int i = 0; i < 1000; i++) {
        data = *(volatile uint8_t*)(0x1F801800 + (i % 256));
    }
    
    end = GetRCnt(0);
    
    return (end - start);
}

/* Measure RAM timing variance */
static int measure_ram_timing(void) {
    /* 
     * RAM timing varies due to:
     * - Memory chip characteristics
     * - Temperature
     * - Manufacturing variance
     */
    
    volatile uint32_t* ram = (volatile uint32_t*)0x80000000;
    uint32_t start, end;
    volatile uint32_t acc = 0;
    
    start = GetRCnt(0);
    
    /* Sequential read/write pattern */
    for (int i = 0; i < 10000; i++) {
        ram[i % 1024] = i;
        acc ^= ram[i % 1024];
    }
    
    end = GetRCnt(0);
    
    /* Convert to nanoseconds (approximate) */
    /* Counter runs at system clock / 8 */
    int cycles = end - start;
    int ns = (cycles * 8 * 1000) / 33;  /* 33.87 MHz system clock */
    
    return ns;
}

/* Measure GPU (GTE) timing fingerprint */
static int measure_gte_timing(void) {
    /* 
     * GTE (Geometry Transfer Engine) timing varies
     * This is unique to each PS1's GPU
     */
    
    uint32_t start, end;
    
    start = GetRCnt(0);
    
    /* Execute some GTE operations */
    /* Simplified - real implementation would use GTE commands */
    for (int i = 0; i < 100; i++) {
        /* GTE NOP equivalent */
        __asm__ volatile ("nop");
    }
    
    end = GetRCnt(0);
    
    return (end - start);
}

/* Collect controller port jitter */
static int measure_controller_jitter(void) {
    /* 
     * Controller port timing has jitter due to:
     * - Shift register timing
     * - Button contact variance
     * - Cable resistance
     */
    
    int samples[10];
    int i, j;
    
    for (i = 0; i < 10; i++) {
        uint32_t start = GetRCnt(0);
        
        /* Read controller port (simplified) */
        volatile uint8_t* pad = (volatile uint8_t*)0x1F801040;
        for (j = 0; j < 100; j++) {
            (void)*pad;
        }
        
        uint32_t end = GetRCnt(0);
        samples[i] = end - start;
    }
    
    /* Calculate variance */
    int sum = 0;
    for (i = 0; i < 10; i++) {
        sum += samples[i];
    }
    int mean = sum / 10;
    
    int variance = 0;
    for (i = 0; i < 10; i++) {
        int diff = samples[i] - mean;
        variance += diff * diff;
    }
    
    return variance / 10;
}

/* Collect all fingerprint data */
int fingerprint_collect(fingerprint_data_t* fp) {
    if (!fp) return 0;
    
    /* Clear structure */
    memset(fp, 0, sizeof(fingerprint_data_t));
    
    /* Get BIOS version */
    get_bios_version(fp->bios_version, sizeof(fp->bios_version));
    fp->bios_hash = hash_bios_version(fp->bios_version);
    
    /* Measure CD-ROM timing */
    fp->cdrom_timing = measure_cdrom_timing();
    
    /* Measure RAM timing */
    fp->ram_timing_ns = measure_ram_timing();
    
    /* Measure GTE timing */
    fp->gte_timing = measure_gte_timing();
    
    /* Measure controller jitter */
    fp->controller_jitter = measure_controller_jitter();
    
    /* Additional entropy from timers */
    fp->timer_entropy[0] = GetRCnt(0);
    fp->timer_entropy[1] = GetRCnt(1);
    fp->timer_entropy[2] = GetRCnt(2);
    
    return 1;
}

/* Validate fingerprint (anti-emulation check) */
int fingerprint_validate(const fingerprint_data_t* fp) {
    if (!fp) return 0;
    
    /* Emulators typically have:
     * - Zero or very consistent timing (no jitter)
     * - Perfect CD-ROM timing
     * - Standardized BIOS strings
     */
    
    /* Check for emulator signatures */
    
    /* 1. Controller jitter should be > 0 on real hardware */
    if (fp->controller_jitter == 0) {
        return 0;  /* Likely emulator */
    }
    
    /* 2. CD-ROM timing should have some variance */
    if (fp->cdrom_timing < 100) {
        return 0;  /* Too fast, likely emulated */
    }
    
    /* 3. RAM timing should be reasonable */
    if (fp->ram_timing_ns < 1000 || fp->ram_timing_ns > 100000) {
        return 0;  /* Out of expected range */
    }
    
    /* 4. BIOS version should match known PS1 BIOS strings */
    if (strncmp(fp->bios_version, "Sony Computer Entertainment", 25) != 0) {
        /* May still be valid for some regions */
        /* Just log a warning */
    }
    
    return 1;  /* Passed validation */
}

/* Print fingerprint data (for debugging) */
void fingerprint_print(const fingerprint_data_t* fp) {
    printf("=== Fingerprint Data ===\n");
    printf("BIOS: %s\n", fp->bios_version);
    printf("BIOS Hash: 0x%08X\n", fp->bios_hash);
    printf("CD-ROM Timing: %d cycles\n", fp->cdrom_timing);
    printf("RAM Timing: %d ns\n", fp->ram_timing_ns);
    printf("GTE Timing: %d cycles\n", fp->gte_timing);
    printf("Controller Jitter: %d\n", fp->controller_jitter);
    printf("Timer Entropy: %d, %d, %d\n", 
           fp->timer_entropy[0], 
           fp->timer_entropy[1], 
           fp->timer_entropy[2]);
    printf("========================\n");
}
