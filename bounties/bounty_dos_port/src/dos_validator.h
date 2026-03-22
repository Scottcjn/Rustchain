/*
 *  dos_validator.h
 *  RustChain MS-DOS Real-Mode Validator
 *  Bounty: bounty_dos_port (500 RUST)
 *
 *  Compiles with Open Watcom for 16-bit DOS
 */

#ifndef DOS_VALIDATOR_H
#define DOS_VALIDATOR_H

#include <stddef.h>
#include <time.h>

/* Constants */
#define OUTPUT_FILE     "proof_of_antiquity.json"
#define MAX_LOOPS       1000000
#define BUF_SIZE        256

/* Global state */
typedef struct {
    char cpuModel[64];
    int cpuMHz;
    char biosDate[32];
    double baseScore;
    double rarityBonus;
    unsigned long loopCycles;
    char wallet[80];
} DOSValidatorState;

/* Function prototypes */
void DetectCPU(DOSValidatorState *state);
void ReadBIOSDate(DOSValidatorState *state);
unsigned long GenerateEntropy(DOSValidatorState *state);
double CalculateScore(DOSValidatorState *state);
double GetRarityBonus(DOSValidatorState *state);
int WriteProof(DOSValidatorState *state);
void DisplayResults(DOSValidatorState *state);

#endif /* DOS_VALIDATOR_H */
