/*
 *  win31_validator.h
 *  RustChain Windows 3.1 Validator
 *  Bounty: bounty_win31_progman (600 RUST)
 *
 *  Compiles with Open Watcom for 16-bit Windows
 */

#ifndef WIN31_VALIDATOR_H
#define WIN31_VALIDATOR_H

#include <windows.h>
#include <winuser.h>
#include <wingdi.h>
#include <winprocs.h>
#include <stddef.h>

/* Constants */
#define MAX_BUFFER  256
#define OUTPUT_FILENAME "proof_of_antiquity.json"

/* Global state */
typedef struct {
    char cpuModel[64];
    int cpuMHz;
    char windowsVersion[32];
    char biosDate[32];
    double baseScore;
    double rarityBonus;
    char wallet[80];
} Win31ValidatorState;

/* Function prototypes */
LRESULT CALLBACK WndProc(HWND, UINT, WPARAM, LPARAM);
void DetectCPU(Win31ValidatorState*);
void GetBIOSDate(Win31ValidatorState*);
void GetWindowsVersion(Win31ValidatorState*);
BOOL WriteProofFile(Win31ValidatorState*);
void UpdateDisplay(HWND, Win31ValidatorState*);

#endif /* WIN31_VALIDATOR_H */
