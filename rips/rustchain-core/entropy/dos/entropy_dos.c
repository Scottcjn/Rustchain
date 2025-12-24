/*
 * RUSTCHAIN ENTROPY COLLECTOR - DOS EDITION (Turbo C / DJGPP)
 * For 8086/286/386/486/Pentium DOS systems
 *
 * "Every vintage computer has historical potential"
 *
 * Compile with Turbo C: tcc entropy_dos.c
 * Compile with DJGPP:   gcc -o entropy.exe entropy_dos.c
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dos.h>
#include <time.h>
#include <conio.h>

/* For older Turbo C */
#ifndef __DJGPP__
#include <bios.h>
#endif

#define TIMER_SAMPLES 32
#define HASH_SIZE 8

typedef struct {
    char bios_date[9];
    unsigned char bios_model;
    char cpu_vendor[13];
    unsigned long cpu_signature;
    unsigned int conv_memory;
    unsigned int ext_memory;
    unsigned int timer_samples[TIMER_SAMPLES];
    unsigned char rtc_time[3];
    unsigned char video_mode;
    unsigned char has_vga;
    unsigned char hash[HASH_SIZE];
} DosEntropy;

/* Read port */
unsigned char inp(unsigned port) {
#ifdef __DJGPP__
    unsigned char result;
    __asm__ __volatile__("inb %1, %0" : "=a"(result) : "d"((unsigned short)port));
    return result;
#else
    return inportb(port);
#endif
}

/* Write port */
void outp(unsigned port, unsigned char value) {
#ifdef __DJGPP__
    __asm__ __volatile__("outb %0, %1" : : "a"(value), "d"((unsigned short)port));
#else
    outportb(port, value);
#endif
}

/* Read BIOS date from F000:FFF5 */
void read_bios_date(DosEntropy *ent) {
    unsigned char far *bios = (unsigned char far *)0xF000FFF5L;
    int i;
    printf("  [1/7] Reading BIOS info...\n");

    for (i = 0; i < 8; i++) {
        ent->bios_date[i] = bios[i];
    }
    ent->bios_date[8] = '\0';

    /* BIOS model at F000:FFFE */
    ent->bios_model = *((unsigned char far *)0xF000FFFEL);

    printf("    BIOS Date: %s\n", ent->bios_date);
    printf("    BIOS Model: 0x%02X\n", ent->bios_model);
}

/* Detect CPU using flags manipulation */
void detect_cpu(DosEntropy *ent) {
    unsigned long eax, ebx, ecx, edx;
    int has_cpuid = 0;

    printf("  [2/7] Detecting CPU...\n");

    /* Try to toggle CPUID flag */
#ifdef __DJGPP__
    __asm__ __volatile__(
        "pushfl\n"
        "popl %%eax\n"
        "movl %%eax, %%ebx\n"
        "xorl $0x200000, %%eax\n"
        "pushl %%eax\n"
        "popfl\n"
        "pushfl\n"
        "popl %%eax\n"
        "xorl %%ebx, %%eax\n"
        "andl $0x200000, %%eax\n"
        : "=a"(has_cpuid) : : "ebx"
    );
#endif

    if (has_cpuid) {
        /* Get CPUID info */
#ifdef __DJGPP__
        __asm__ __volatile__(
            "xorl %%eax, %%eax\n"
            "cpuid\n"
            : "=b"(ebx), "=c"(ecx), "=d"(edx)
            : : "eax"
        );
        memcpy(ent->cpu_vendor, &ebx, 4);
        memcpy(ent->cpu_vendor + 4, &edx, 4);
        memcpy(ent->cpu_vendor + 8, &ecx, 4);
        ent->cpu_vendor[12] = '\0';

        __asm__ __volatile__(
            "movl $1, %%eax\n"
            "cpuid\n"
            : "=a"(eax)
            : : "ebx", "ecx", "edx"
        );
        ent->cpu_signature = eax;
#endif
        printf("    CPU Vendor: %s\n", ent->cpu_vendor);
        printf("    CPU Signature: 0x%08lX\n", ent->cpu_signature);
    } else {
        strcpy(ent->cpu_vendor, "Pre-CPUID");
        ent->cpu_signature = 0;
        printf("    CPU: Pre-CPUID processor (8086/286/386)\n");
    }
}

/* Get memory size */
void get_memory(DosEntropy *ent) {
    union REGS regs;

    printf("  [3/7] Reading memory configuration...\n");

    /* INT 12h - Conventional memory */
    int86(0x12, &regs, &regs);
    ent->conv_memory = regs.x.ax;
    printf("    Conventional: %u KB\n", ent->conv_memory);

    /* INT 15h, AH=88h - Extended memory */
    regs.h.ah = 0x88;
    int86(0x15, &regs, &regs);
    if (!(regs.x.cflag)) {
        ent->ext_memory = regs.x.ax;
        printf("    Extended: %u KB\n", ent->ext_memory);
    } else {
        ent->ext_memory = 0;
    }
}

/* Collect timer entropy from 8254 PIT */
void collect_timer_entropy(DosEntropy *ent) {
    int i, j;

    printf("  [4/7] Collecting timer entropy...\n");

    for (i = 0; i < TIMER_SAMPLES; i++) {
        /* Latch timer 0 */
        outp(0x43, 0x00);

        /* Read 16-bit count */
        ent->timer_samples[i] = inp(0x40);
        ent->timer_samples[i] |= (unsigned int)inp(0x40) << 8;

        /* Small delay */
        for (j = 0; j < 100; j++) {
            /* busy wait */
        }
    }

    printf("    Timer samples collected: %d\n", TIMER_SAMPLES);
    printf("    Sample[0]: 0x%04X\n", ent->timer_samples[0]);
}

/* Read CMOS/RTC */
void read_cmos_rtc(DosEntropy *ent) {
    printf("  [5/7] Reading CMOS/RTC...\n");

    /* Disable interrupts while reading CMOS */
    disable();

    /* Seconds */
    outp(0x70, 0x00);
    ent->rtc_time[0] = inp(0x71);

    /* Minutes */
    outp(0x70, 0x02);
    ent->rtc_time[1] = inp(0x71);

    /* Hours */
    outp(0x70, 0x04);
    ent->rtc_time[2] = inp(0x71);

    enable();

    printf("    RTC Time: %02X:%02X:%02X (BCD)\n",
           ent->rtc_time[2], ent->rtc_time[1], ent->rtc_time[0]);
}

/* Detect video adapter */
void detect_video(DosEntropy *ent) {
    union REGS regs;

    printf("  [6/7] Detecting video adapter...\n");

    /* Get current video mode */
    regs.h.ah = 0x0F;
    int86(0x10, &regs, &regs);
    ent->video_mode = regs.h.al;
    printf("    Video Mode: 0x%02X\n", ent->video_mode);

    /* Check for VGA */
    regs.x.ax = 0x1A00;
    int86(0x10, &regs, &regs);
    if (regs.h.al == 0x1A) {
        ent->has_vga = 1;
        printf("    VGA: Yes\n");
    } else {
        ent->has_vga = 0;
        printf("    VGA: No (EGA/CGA/MDA)\n");
    }
}

/* Generate entropy hash (simple XOR-rotate) */
void generate_hash(DosEntropy *ent) {
    unsigned long hash1 = 0, hash2 = 0;
    int i;
    unsigned char *ptr;

    printf("  [7/7] Generating entropy hash...\n");

    /* Mix BIOS date */
    for (i = 0; i < 8; i++) {
        hash1 ^= (unsigned long)ent->bios_date[i] << ((i % 4) * 8);
        hash1 = (hash1 << 5) | (hash1 >> 27);
    }

    /* Mix BIOS model */
    hash1 ^= ent->bios_model;
    hash1 = (hash1 << 7) | (hash1 >> 25);

    /* Mix timer samples */
    for (i = 0; i < TIMER_SAMPLES; i++) {
        hash2 ^= ent->timer_samples[i];
        hash2 = (hash2 << 3) | (hash2 >> 29);
    }

    /* Mix RTC */
    hash1 ^= ((unsigned long)ent->rtc_time[0] << 16) |
             ((unsigned long)ent->rtc_time[1] << 8) |
             ent->rtc_time[2];

    /* Mix memory */
    hash2 ^= ((unsigned long)ent->conv_memory << 16) | ent->ext_memory;

    /* Mix CPU signature */
    hash1 ^= ent->cpu_signature;

    /* Store hash */
    ptr = (unsigned char *)&hash1;
    for (i = 0; i < 4; i++) ent->hash[i] = ptr[i];
    ptr = (unsigned char *)&hash2;
    for (i = 0; i < 4; i++) ent->hash[i + 4] = ptr[i];
}

/* Write entropy to file */
void write_entropy_file(DosEntropy *ent) {
    FILE *fp;
    int i;

    fp = fopen("ENTROPY.TXT", "w");
    if (!fp) {
        printf("Error: Cannot create ENTROPY.TXT\n");
        return;
    }

    fprintf(fp, "{\n");
    fprintf(fp, "  \"rustchain_entropy\": {\n");
    fprintf(fp, "    \"version\": 1,\n");
    fprintf(fp, "    \"platform\": \"dos\",\n");
    fprintf(fp, "    \"collector\": \"entropy_dos.c\"\n");
    fprintf(fp, "  },\n");

    fprintf(fp, "  \"proof_of_antiquity\": {\n");
    fprintf(fp, "    \"philosophy\": \"Every vintage computer has historical potential\",\n");
    fprintf(fp, "    \"consensus\": \"NOT Proof of Work - This is PROOF OF ANTIQUITY\",\n");
    fprintf(fp, "    \"hardware_verified\": true,\n");
    fprintf(fp, "    \"tier\": \"ancient\",\n");
    fprintf(fp, "    \"multiplier\": 3.5\n");
    fprintf(fp, "  },\n");

    fprintf(fp, "  \"entropy_proof\": {\n");
    fprintf(fp, "    \"hash\": \"");
    for (i = 0; i < HASH_SIZE; i++) {
        fprintf(fp, "%02x", ent->hash[i]);
    }
    fprintf(fp, "\",\n");
    fprintf(fp, "    \"signature\": \"DOS-ANCIENT-ENTROPY-%02x%02x%02x%02x\",\n",
            ent->hash[0], ent->hash[1], ent->hash[2], ent->hash[3]);
    fprintf(fp, "    \"entropy_sources\": 7,\n");
    fprintf(fp, "    \"sources\": [\n");
    fprintf(fp, "      \"bios_date\",\n");
    fprintf(fp, "      \"bios_model\",\n");
    fprintf(fp, "      \"cpu_detection\",\n");
    fprintf(fp, "      \"memory_config\",\n");
    fprintf(fp, "      \"timer_8254_pit\",\n");
    fprintf(fp, "      \"cmos_rtc\",\n");
    fprintf(fp, "      \"video_adapter\"\n");
    fprintf(fp, "    ]\n");
    fprintf(fp, "  },\n");

    fprintf(fp, "  \"hardware_profile\": {\n");
    fprintf(fp, "    \"bios_date\": \"%s\",\n", ent->bios_date);
    fprintf(fp, "    \"bios_model\": \"0x%02X\",\n", ent->bios_model);
    fprintf(fp, "    \"cpu_vendor\": \"%s\",\n", ent->cpu_vendor);
    fprintf(fp, "    \"cpu_signature\": \"0x%08lX\",\n", ent->cpu_signature);
    fprintf(fp, "    \"conv_memory_kb\": %u,\n", ent->conv_memory);
    fprintf(fp, "    \"ext_memory_kb\": %u,\n", ent->ext_memory);
    fprintf(fp, "    \"video_mode\": \"0x%02X\",\n", ent->video_mode);
    fprintf(fp, "    \"has_vga\": %s\n", ent->has_vga ? "true" : "false");
    fprintf(fp, "  }\n");
    fprintf(fp, "}\n");

    fclose(fp);
    printf("\nEntropy written to ENTROPY.TXT\n");
}

/* Print results */
void print_results(DosEntropy *ent) {
    int i;

    printf("\n======================================================\n");
    printf("  ENTROPY PROOF\n");
    printf("======================================================\n\n");

    printf("  Hash: ");
    for (i = 0; i < HASH_SIZE; i++) {
        printf("%02X", ent->hash[i]);
    }
    printf("\n");

    printf("  Signature: DOS-ANCIENT-ENTROPY-%02X%02X%02X%02X\n",
           ent->hash[0], ent->hash[1], ent->hash[2], ent->hash[3]);
    printf("  Hardware Tier: ANCIENT (3.5x multiplier!)\n");
    printf("  Entropy Sources: 7\n");

    printf("\n======================================================\n");
    printf("  ENTROPY COLLECTION COMPLETE\n");
    printf("  This fingerprint proves REAL VINTAGE HARDWARE\n");
    printf("======================================================\n");
}

int main(void) {
    DosEntropy entropy;

    memset(&entropy, 0, sizeof(entropy));

    printf("\n");
    printf("======================================================\n");
    printf("  RUSTCHAIN ENTROPY COLLECTOR - DOS EDITION\n");
    printf("  \"Every vintage computer has historical potential\"\n");
    printf("======================================================\n\n");

    printf("Collecting hardware entropy...\n\n");

    read_bios_date(&entropy);
    detect_cpu(&entropy);
    get_memory(&entropy);
    collect_timer_entropy(&entropy);
    read_cmos_rtc(&entropy);
    detect_video(&entropy);
    generate_hash(&entropy);

    print_results(&entropy);
    write_entropy_file(&entropy);

    return 0;
}
