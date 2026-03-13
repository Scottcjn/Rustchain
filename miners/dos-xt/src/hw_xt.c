/*
 * Hardware Detection Implementation for IBM PC/XT
 */

#include <stdio.h>
#include <string.h>
#include <dos.h>
#include <i86.h>

#include "hw_xt.h"
#include "pit.h"

/* Global hardware info */
static hw_xt_info_t g_hw_info;

/*
 * Initialize hardware detection module
 */
int hw_xt_init(void)
{
    memset(&g_hw_info, 0, sizeof(g_hw_info));
    
    /* Platform identification */
    strcpy(g_hw_info.platform, "DOS-XT");
    strcpy(g_hw_info.cpu, "Intel 8088");
    g_hw_info.cpu_mhz = 4;  /* 4.77 MHz rounded */
    
    /* Get memory size */
    g_hw_info.mem_kb = get_mem_size();
    
    /* Get BIOS information */
    get_bios_date(g_hw_info.bios_date, sizeof(g_hw_info.bios_date));
    get_bios_vendor(g_hw_info.bios_vendor, sizeof(g_hw_info.bios_vendor));
    
    /* Measure PIT drift (primary anti-emulation check) */
    g_hw_info.pit_drift = measure_pit_drift(10);
    
    return 0;
}

/*
 * Get system memory size using BIOS interrupt 0x12
 * Returns memory size in KB
 */
unsigned int get_mem_size(void)
{
    union REGS regs;
    
    regs.h.ah = 0x12;  /* BIOS function: Get memory size */
    int86(0x10, &regs, &regs);  /* Actually use INT 0x12 directly */
    
    /* Direct INT 0x12 */
    _AX = 0;
    geninterrupt(0x12);
    
    return _AX;  /* AX contains memory size in KB */
}

/*
 * Get BIOS date string from F000:FFF0
 * The last 13 bytes of BIOS ROM contain the date in MM/DD/YY format
 */
void get_bios_date(char *buf, unsigned int bufsize)
{
    if (bufsize < 9) return;
    
    /* BIOS date is at F000:FFF0, but we read backwards */
    /* The date string is 8 bytes: MM/DD/YY */
    far char *bios_rom = (far char *)0xF000FFF0L;
    
    /* Search backwards for date pattern */
    /* Real IBM BIOS dates look like: 01/15/82 */
    int i;
    for (i = 0; i < 100 && i < bufsize - 1; i++) {
        char c = bios_rom[-i];
        if (c >= '0' && c <= '9') {
            /* Found start of date, copy 8 bytes */
            int j;
            for (j = 0; j < 8 && (i + j) < 100; j++) {
                buf[j] = bios_rom[-(i - j)];
            }
            buf[8] = '\0';
            return;
        }
    }
    
    /* Fallback: try fixed offset */
    strncpy(buf, "01/01/80", bufsize - 1);
    buf[bufsize - 1] = '\0';
}

/*
 * Get BIOS vendor by analyzing ROM signatures
 */
void get_bios_vendor(char *buf, unsigned int bufsize)
{
    if (bufsize < 16) return;
    
    far char *bios_rom = (far char *)0xF0000000L;
    
    /* Check for common BIOS signatures */
    /* IBM PC/XT BIOS starts with specific bytes */
    
    /* Look for "IBM" string in BIOS */
    if (bios_rom[0x000E] == 'I' && bios_rom[0x000F] == 'B' && 
        bios_rom[0x0010] == 'M') {
        strncpy(buf, "IBM", bufsize - 1);
    }
    /* Look for "AMI" (American Megatrends) */
    else if (bios_rom[0x0000] == 'A' && bios_rom[0x0001] == 'M' && 
             bios_rom[0x0002] == 'I') {
        strncpy(buf, "AMI", bufsize - 1);
    }
    /* Look for "Award" */
    else if (strncmp((char far *)bios_rom, "Award", 5) == 0) {
        strncpy(buf, "Award", bufsize - 1);
    }
    /* Look for "Phoenix" */
    else if (strncmp((char far *)bios_rom, "Phoenix", 7) == 0) {
        strncpy(buf, "Phoenix", bufsize - 1);
    }
    else {
        strncpy(buf, "Unknown", bufsize - 1);
    }
    
    buf[bufsize - 1] = '\0';
}

/*
 * Read PIT counter 0
 * PIT 8253/8254 is at ports 0x40-0x43
 */
unsigned int read_pit_counter(void)
{
    unsigned int count;
    
    /* Latch counter 0 */
    outp(0x43, 0x00);
    
    /* Read low byte, then high byte */
    count = inp(0x40);
    count |= (inp(0x40) << 8);
    
    return count;
}

/*
 * Measure PIT timer drift
 * 
 * The PIT runs at 1.193182 MHz (1193182 Hz)
 * In 1 second, it should count 1193182 ticks.
 * However, real crystals have slight variations.
 * 
 * We measure the counter value over a fixed time period
 * and calculate the drift from theoretical value.
 */
unsigned long measure_pit_drift(unsigned int samples)
{
    unsigned long total_drift = 0;
    unsigned int i;
    
    /* Theoretical ticks per 100ms */
    unsigned long expected_ticks = 119318;  /* 1193182 / 10 */
    
    for (i = 0; i < samples; i++) {
        unsigned long start = read_pit_counter();
        
        /* Wait approximately 100ms using BIOS delay */
        delay(100);
        
        unsigned long end = read_pit_counter();
        
        /* Calculate actual ticks (handle wraparound) */
        unsigned long ticks;
        if (end > start) {
            /* Counter wrapped around */
            ticks = (65536 - start) + end;
        } else {
            ticks = start - end;
        }
        
        /* Calculate drift from expected */
        long drift = ticks - expected_ticks;
        if (drift < 0) drift = -drift;
        
        total_drift += drift;
    }
    
    return total_drift / samples;
}

/*
 * Measure ISA bus I/O timing
 * 
 * Real ISA bus has physical propagation delays (~100-300ns per I/O).
 * Emulators typically have zero or minimal I/O delay.
 * 
 * We measure the time to perform a sequence of I/O operations.
 */
unsigned long measure_isa_timing(unsigned int samples)
{
    unsigned long total_time = 0;
    unsigned int i;
    
    for (i = 0; i < samples; i++) {
        unsigned long start = read_pit_counter();
        
        /* Perform sequence of I/O operations */
        /* Use keyboard controller port (0x60) - safe to access */
        volatile unsigned char dummy;
        int j;
        for (j = 0; j < 100; j++) {
            outp(0x60, 0x00);  /* Write (may be ignored) */
            dummy = inp(0x60);  /* Read */
        }
        (void)dummy;  /* Suppress warning */
        
        unsigned long end = read_pit_counter();
        
        unsigned long time;
        if (end > start) {
            time = (65536 - start) + end;
        } else {
            time = start - end;
        }
        
        total_time += time;
    }
    
    return total_time / samples;
}

/*
 * Read CMOS RTC
 * CMOS is accessed via ports 0x70 (index) and 0x71 (data)
 */
void read_cmos_rtc(unsigned char *hour, unsigned char *min, unsigned char *sec)
{
    /* Disable NMI during CMOS access */
    outp(0x70, 0x80 | 0x04);  /* Index 4 = seconds, bit 7 = disable NMI */
    *sec = inp(0x71);
    
    outp(0x70, 0x80 | 0x02);  /* Index 2 = minutes */
    *min = inp(0x71);
    
    outp(0x70, 0x80 | 0x00);  /* Index 0 = hours */
    *hour = inp(0x71);
}

/*
 * Measure CMOS RTC drift
 * This requires multiple measurements over time.
 * For simplicity, we return a fixed value for now.
 */
long measure_cmos_drift(void)
{
    /* TODO: Implement proper drift measurement */
    /* This would require measuring RTC over several minutes */
    return 0;
}

/*
 * Measure CPU timing using PIT
 */
unsigned long measure_cpu_timing(void)
{
    unsigned long start = read_pit_counter();
    
    /* Execute fixed computation */
    volatile unsigned long acc = 0;
    int i;
    for (i = 0; i < 10000; i++) {
        acc ^= (i * 31UL) & 0xFFFFFFFFUL;
        acc += (acc >> 3);
    }
    
    unsigned long end = read_pit_counter();
    
    unsigned long time;
    if (end > start) {
        time = (65536 - start) + end;
    } else {
        time = start - end;
    }
    
    return time;
}

/*
 * Generate hardware fingerprint
 */
void generate_hardware_fingerprint(char *buf, unsigned int bufsize)
{
    if (bufsize < 64) return;
    
    /* Combine multiple hardware measurements */
    sprintf(buf, "%s-%s-%lu-%u",
            g_hw_info.bios_vendor,
            g_hw_info.bios_date,
            g_hw_info.pit_drift,
            g_hw_info.mem_kb);
}

/*
 * Generate miner ID
 * Format: xt-{hostname_prefix}-{fingerprint_prefix}
 */
void generate_miner_id_xt(char *buf, unsigned int bufsize)
{
    if (bufsize < 64) return;
    
    char fingerprint[64];
    generate_hardware_fingerprint(fingerprint, sizeof(fingerprint));
    
    /* Get hostname (or use "pcxt" as default) */
    char hostname[32] = "pcxt";
    /* In DOS, we could use the machine name from NETWORK.CFG if available */
    
    /* Create miner ID */
    snprintf(buf, bufsize, "xt-%.10s-%.8s", hostname, fingerprint);
}

/*
 * Detect if running in emulator
 */
int detect_emulator(void)
{
    int emulator_score = 0;
    
    /* Check 1: PIT drift too precise (emulators are too accurate) */
    /* Real hardware: drift > 100 ticks variation */
    /* Emulators: drift < 10 ticks (too precise) */
    if (g_hw_info.pit_drift < 50) {
        emulator_score += 40;
    }
    
    /* Check 2: ISA timing too fast */
    unsigned long isa_time = measure_isa_timing(5);
    if (isa_time < 100) {  /* Too fast, likely emulated */
        emulator_score += 30;
    }
    
    /* Check 3: CPU timing consistency */
    /* Real 8088 has slight variations; emulators are too consistent */
    unsigned long t1 = measure_cpu_timing();
    unsigned long t2 = measure_cpu_timing();
    unsigned long t3 = measure_cpu_timing();
    
    /* If all three are identical, likely emulated */
    if (t1 == t2 && t2 == t3) {
        emulator_score += 30;
    }
    
    /* Check 4: BIOS vendor check */
    /* DOSBox uses generic BIOS strings */
    if (strcmp(g_hw_info.bios_vendor, "Unknown") == 0 ||
        strcmp(g_hw_info.bios_vendor, "DOSBox") == 0) {
        emulator_score += 50;
    }
    
    /* Threshold: score >= 50 indicates emulator */
    return (emulator_score >= 50) ? 1 : 0;
}

/*
 * Get emulator detection report
 */
void get_emulator_report(char *buf, unsigned int bufsize)
{
    if (bufsize < 128) return;
    
    strcpy(buf, "Emulator Detection Report:\n");
    
    if (g_hw_info.pit_drift < 50) {
        strcat(buf, "  - PIT drift too precise (emulator signature)\n");
    }
    
    if (strcmp(g_hw_info.bios_vendor, "Unknown") == 0) {
        strcat(buf, "  - Generic BIOS detected (emulator signature)\n");
    }
    
    /* Add more details as needed */
}
