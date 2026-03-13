/*
 * Hardware Detection for IBM PC/XT
 * 
 * This module implements hardware fingerprinting and emulator detection
 * specifically for vintage x86 hardware (8088/8086).
 *
 * Key anti-emulation checks:
 * - PIT (8253/8254) timer drift measurement
 * - BIOS string analysis
 * - ISA bus timing
 * - CMOS RTC drift
 * - CPU cycle timing
 */

#ifndef HW_XT_H
#define HW_XT_H

#ifdef __cplusplus
extern "C" {
#endif

/* Hardware information structure */
typedef struct {
    char platform[32];      /* "DOS-XT" */
    char cpu[64];           /* "Intel 8088" */
    unsigned int cpu_mhz;   /* 4.77 */
    unsigned int mem_kb;    /* Memory in KB */
    char bios_date[32];     /* BIOS date string */
    char bios_vendor[64];   /* BIOS vendor */
    unsigned long pit_drift; /* PIT drift measurement */
    unsigned char mac[6];   /* MAC address (if available) */
} hw_xt_info_t;

/*
 * Initialize hardware detection module
 * Returns: 0 on success, -1 on error
 */
int hw_xt_init(void);

/*
 * Get system memory size in KB
 * Uses BIOS interrupt 0x12
 */
unsigned int get_mem_size(void);

/*
 * Get BIOS date string
 * Stored at F000:FFF0 (last 13 bytes of BIOS ROM)
 * Format: MM/DD/YY or MM/DD/YY - 
 */
void get_bios_date(char *buf, unsigned int bufsize);

/*
 * Get BIOS vendor string
 * Analyzes BIOS ROM for vendor signatures
 */
void get_bios_vendor(char *buf, unsigned int bufsize);

/*
 * Read PIT (8253/8254) counter 0
 * Returns: 16-bit counter value
 */
unsigned int read_pit_counter(void);

/*
 * Measure PIT timer drift
 * This is the PRIMARY anti-emulation check.
 * Real crystals have slight frequency variations.
 * Emulators (DOSBox) use host timer, too precise.
 *
 * Returns: Average drift in timer ticks per second
 * Typical real hardware: 1190-1196 (vs theoretical 1193)
 */
unsigned long measure_pit_drift(unsigned int samples);

/*
 * Measure ISA bus I/O timing
 * Real ISA bus has physical propagation delays.
 * Emulators have instantaneous I/O.
 *
 * Returns: Average I/O delay in CPU cycles
 */
unsigned long measure_isa_timing(unsigned int samples);

/*
 * Read CMOS RTC via ports 0x70-0x71
 * Returns: BCD-encoded time values
 */
void read_cmos_rtc(unsigned char *hour, unsigned char *min, unsigned char *sec);

/*
 * Measure CMOS RTC drift over time
 * Real RTC crystals drift; emulators sync to host clock.
 *
 * Returns: Drift measurement (seconds per hour)
 */
long measure_cmos_drift(void);

/*
 * Execute fixed computation and measure CPU cycles
 * Uses PIT to measure execution time.
 * Real 8088 has specific cycle counts; emulators vary.
 *
 * Returns: Execution time in PIT ticks
 */
unsigned long measure_cpu_timing(void);

/*
 * Generate hardware fingerprint
 * Combines multiple hardware measurements into unique ID.
 *
 * Parameters:
 *   buf - Output buffer (at least 64 bytes)
 *   bufsize - Buffer size
 */
void generate_hardware_fingerprint(char *buf, unsigned int bufsize);

/*
 * Generate miner ID from hardware fingerprint
 * Format: xt-{hostname_prefix}-{fingerprint_prefix}
 *
 * Parameters:
 *   buf - Output buffer (at least 64 bytes)
 *   bufsize - Buffer size
 */
void generate_miner_id_xt(char *buf, unsigned int bufsize);

/*
 * Detect if running in emulator (DOSBox, 86Box, etc.)
 * Uses multiple heuristics:
 * - PIT drift too precise
 * - ISA timing too fast
 * - BIOS strings generic
 * - CPU timing inconsistent
 *
 * Returns: 1 if emulator detected, 0 if real hardware
 */
int detect_emulator(void);

/*
 * Get detailed emulator detection report
 * Populates explanation of why emulator was detected.
 *
 * Parameters:
 *   buf - Output buffer
 *   bufsize - Buffer size
 */
void get_emulator_report(char *buf, unsigned int bufsize);

#ifdef __cplusplus
}
#endif

#endif /* HW_XT_H */
