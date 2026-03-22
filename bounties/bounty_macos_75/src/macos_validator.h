/*
 *  macos_validator.h
 *  RustChain Classic Mac OS Validator
 *  Bounty: bounty_macos_75 (750 RUST)
 *
 *  Compiles with THINK C 7.5 and Retro68
 */

#ifndef MACOS_VALIDATOR_H
#define MACOS_VALIDATOR_H

#include <Types.h>
#include <Files.h>
#include <Gestalt.h>
#include <Processes.h>
#include <Dialogs.h>
#include <TextEdit.h>
#include <Menus.h>
#include <Windows.h>
#include <Events.h>

/* Constants */
#define kMaxBufSize  1024
#define kOutputFileName "\pproof_of_antiquity.json"

/* Function prototypes */
void DetectCPUType(void);
void GetSystemFolderTimestamp(void);
void GenerateProofFile(void);
void ShowAboutDialog(void);
pascal void MainLoop(void);

/* Global state */
typedef struct {
    char cpuModel[64];
    long cpuMHz;
    char systemVersion[32];
    char machineName[64];
    long creationDate;
    char walletAddr[80];
    double entropyScore;
} MacValidatorState;

extern MacValidatorState gState;

#endif /* MACOS_VALIDATOR_H */
