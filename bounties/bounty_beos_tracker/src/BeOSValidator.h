/*
 *  BeOSValidator.h
 *  RustChain Native BeOS/Haiku Validator
 *  Bounty: bounty_beos_tracker (400 RUST)
 */

#ifndef BEOS_VALIDATOR_H
#define BEOS_VALIDATOR_H

#include <os/Os.h>
#include <os/Window.h>
#include <os/View.h>
#include <os/Button.h>
#include <os/String.h>
#include <fs/Path.h>
#include <stdio.h>

#define OUTPUT_FILE "proof_of_antiquity.json"

struct BeValidatorState {
    char cpuModel[64];
    int cpuMHz;
    char biosDate[32];
    char systemVersion[32];
    double baseScore;
    double rarityBonus;
    unsigned long loopCycles;
    char wallet[80];
};

// Function prototypes
void DetectCPU(BeValidatorState *state);
void GetSystemDate(BeValidatorState *state);
void GetSystemVersion(BeValidatorState *state);
unsigned long GenerateEntropy(void);
double CalculateRarityBonus(BeValidatorState *state);
double CalculateScore(BeValidatorState *state);
bool WriteProof(BeValidatorState *state);

#endif /* BEOS_VALIDATOR_H */
