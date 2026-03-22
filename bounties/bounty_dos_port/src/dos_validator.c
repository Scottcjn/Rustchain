/*
 *  dos_validator.c
 *  RustChain MS-DOS Real-Mode Validator
 *  Bounty: bounty_dos_port (500 RUST)
 *
 *  Compiles with Open Watcom wcl for 16-bit DOS
 *  Creates .COM executable (tiny model)
 */

#include "dos_validator.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

/*
 * Detect CPU by checking flags bit 21 for CPUID capability
 */
void DetectCPU(DOSValidatorState *state) {
    unsigned int hasCPUID;
    unsigned int family;

    /* Check for CPUID instruction */
    __asm {
        pushfd
        pop eax
        mov ebx, eax
        xor eax, 0x200000
        push eax
        popfd
        pushfd
        pop eax
        xor eax, ebx
        jz no_cpuid
        mov hasCPUID, 1
        jmp cpu_done
no_cpuid:
        mov hasCPUID, 0
cpu_done:
    }

    if (!hasCPUID) {
        /* No CPUID - must be 80386 or earlier */
        /* Try to detect via flags to see if it's 286 or 8086 */
        /* For simplicity, older CPUs get higher score */
        __asm {
            pushf
            pop ax
            mov bx, ax
            xor ax, 0x0800
            push ax
            popf
            pushf
            pop ax
            and ax, 0x0800
            jnz is_286
            /* 8086/8088 - can't change IOPL bit */
            mov family, 0;
            jmp cpu_detected
is_286:
            mov family, 2;
cpu_detected:
        }

        switch(family) {
            case 0:
                strcpy(state->cpuModel, "Intel 8086/8088");
                state->baseScore = 3.0;
                state->cpuMHz = 8;
                break;
            case 2:
                strcpy(state->cpuModel, "Intel 80286");
                state->baseScore = 2.8;
                state->cpuMHz = 12;
                break;
            default:
                strcpy(state->cpuModel, "Intel 80386");
                state->baseScore = 2.5;
                state->cpuMHz = 25;
                break;
        }
        return;
    }

    /* We have CPUID - get family */
    __asm {
        mov eax, 1
        cpuid
        mov family, eax
        shr family, 8
        and family, 0xF
    }

    switch(family) {
        case 3:
            strcpy(state->cpuModel, "Intel 80386");
            state->baseScore = 2.5;
            state->cpuMHz = 33;
            break;
        case 4:
            strcpy(state->cpuModel, "Intel 80486");
            state->baseScore = 2.2;
            state->cpuMHz = 66;
            break;
        case 5:
            strcpy(state->cpuModel, "Intel Pentium");
            state->baseScore = 1.9;
            state->cpuMHz = 100;
            break;
        default:
            strcpy(state->cpuModel, "x86 Compatible");
            state->baseScore = 1.5;
            state->cpuMHz = 100;
            break;
    }
}

/*
 * Read BIOS date from F000:FFF0 where BIOS stores it
 */
void ReadBIOSDate(DOSValidatorState *state) {
    char __far *biosRom = (char __far *)0xF000FFF0;
    int i;
    char date[9];
    int month, day, year;
    int fullYear;

    /* Read 8 bytes */
    for (i = 0; i < 8; i++) {
        date[i] = biosRom[i];
    }
    date[8] = '\0';

    /* MM/DD/YY -> ISO YYYY-MM-DD */
    month = (date[0] - '0') * 10 + (date[1] - '0');
    day = (date[3] - '0') * 10 + (date[4] - '0');
    year = (date[6] - '0') * 10 + (date[7] - '0');
    fullYear = 1900 + year;

    sprintf(state->biosDate, "%04d-%02d-%02dT00:00:00Z", fullYear, month, day);
}

/*
 * Generate entropy by running a long loop
 * The timing varies based on actual CPU speed and system load
 * creating unique entropy
 */
unsigned long GenerateEntropy(DOSValidatorState *state) {
    volatile unsigned long i;
    clock_t start, end;
    unsigned long cycles;

    start = clock();

    /* Long loop to create entropy through timing variation */
    for (i = 0; i < MAX_LOOPS; i++) {
        /* Do some dummy work to keep it CPU-bound */
        __asm {
            nop
            nop
        }
    }

    end = clock();
    cycles = (unsigned long)(end - start);
    state->loopCycles = cycles;

    return cycles;
}

/*
 * Calculate rarity bonus
 */
double GetRarityBonus(DOSValidatorState *state) {
    if (strstr(state->cpuModel, "8086") != NULL) {
        return 1.25;
    }
    if (strstr(state->cpuModel, "286") != NULL) {
        return 1.18;
    }
    if (strstr(state->cpuModel, "386") != NULL) {
        return 1.10;
    }
    if (strstr(state->cpuModel, "486") != NULL) {
        return 1.05;
    }
    return 1.0;
}

/*
 * Calculate final score
 */
double CalculateScore(DOSValidatorState *state) {
    double bonus = GetRarityBonus(state);
    state->rarityBonus = bonus;
    return state->baseScore * bonus;
}

/*
 * Write proof file in JSON format
 */
int WriteProof(DOSValidatorState *state) {
    FILE *f;
    char currentDate[64];
    time_t now = time(NULL);
    struct tm *tm = localtime(&now);
    double finalScore = CalculateScore(state);

    strftime(currentDate, sizeof(currentDate), "%Y-%m-%d %H:%M:%S", tm);

    f = fopen(OUTPUT_FILE, "w");
    if (!f) {
        return 0;
    }

    fprintf(f, "{\n");
    fprintf(f, "  \"wallet\": \"%s\",\n", state->wallet);
    fprintf(f, "  \"bios_timestamp\": \"%s\",\n", state->biosDate);
    fprintf(f, "  \"cpu_model\": \"%s\",\n", state->cpuModel);
    fprintf(f, "  \"cpu_mhz\": %d,\n", state->cpuMHz);
    fprintf(f, "  \"entropy_score\": %.2f,\n", finalScore);
    fprintf(f, "  \"entropy_loop_cycles\": %lu,\n", state->loopCycles);
    fprintf(f, "  \"timestamp\": \"%s\",\n", currentDate);
    fprintf(f, "  \"rarity_bonus\": %.2f\n", state->rarityBonus);
    fprintf(f, "}\n");

    fclose(f);
    return 1;
}

/*
 * Display results on DOS console
 */
void DisplayResults(DOSValidatorState *state) {
    double finalScore = CalculateScore(state);

    printf("\n");
    printf("RustChain MS-DOS Validator\n");
    printf("===========================\n\n");
    printf("CPU:        %s\n", state->cpuModel);
    printf("CPU Speed:  %d MHz\n", state->cpuMHz);
    printf("BIOS Date:   %s\n", state->biosDate);
    printf("Base Score: %.2f\n", state->baseScore);
    printf("Rarity Bonus: %.2f\n", state->rarityBonus);
    printf("FINAL SCORE: %.2f\n", finalScore);
    printf("\n");
    printf("Entropy loop cycles: %lu\n", state->loopCycles);
    printf("\n");
    printf("Output written to: %s\n", OUTPUT_FILE);
    printf("Edit this file to add your wallet address\n");
    printf("\n");
}

/*
 * Main entry point for DOS
 */
int main(void) {
    DOSValidatorState state;
    int success;

    /* Initialize */
    memset(&state, 0, sizeof(state));
    strcpy(state.wallet, "227fa20c24e7ed1286f9bef6d0050e18e38b2fbbf645cfe846b6febc7a37a48e");

    /* Detect hardware */
    DetectCPU(&state);
    ReadBIOSDate(&state);

    /* Generate entropy */
    printf("Generating entropy, please wait...\n");
    GenerateEntropy(&state);

    /* Display results */
    DisplayResults(&state);

    /* Write proof */
    success = WriteProof(&state);

    if (!success) {
        printf("ERROR: Could not write %s\n", OUTPUT_FILE);
        return 1;
    }

    printf("Done!\n");
    return 0;
}
