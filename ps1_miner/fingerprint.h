/*
 * Hardware Fingerprint Header for PS1
 */

#ifndef FINGERPRINT_H
#define FINGERPRINT_H

#include <stdint.h>

/* Fingerprint data structure */
typedef struct {
    char bios_version[64];      /* BIOS version string */
    uint32_t bios_hash;          /* Hash of BIOS version */
    int cdrom_timing;           /* CD-ROM access timing (cycles) */
    int ram_timing_ns;          /* RAM timing (nanoseconds) */
    int gte_timing;             /* GTE timing (cycles) */
    int controller_jitter;      /* Controller port jitter variance */
    uint32_t timer_entropy[3];  /* Additional timer entropy */
} fingerprint_data_t;

/* Collect all fingerprint data */
int fingerprint_collect(fingerprint_data_t* fp);

/* Validate fingerprint (anti-emulation check) */
int fingerprint_validate(const fingerprint_data_t* fp);

/* Print fingerprint data (for debugging) */
void fingerprint_print(const fingerprint_data_t* fp);

#endif /* FINGERPRINT_H */
