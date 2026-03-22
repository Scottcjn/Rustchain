/*
 *  macos_validator.c
 *  RustChain Classic Mac OS 7.5+ Validator
 *
 *  Uses classic Mac Toolbox API
 *  Compiles with THINK C 7.5 and Retro68
 */

#include "macos_validator.h"
#include <StdIO.h>
#include <String.h>
#include <Memory.h>
#include <Folders.h>

/* Global state */
MacValidatorState gState;

/*
 * Initialize globals
 */
void InitState(void) {
    memset(&gState, 0, sizeof(gState));
    gState.cpuMHz = 0;
    gState.entropyScore = 0.0;
    /* Default wallet is empty, user must edit or enter */
    strcpy(gState.walletAddr, "");
}

/*
 * Detect CPU type and speed using Gestalt
 */
void DetectCPUType(void) {
    long response;
    long cpuFamily;
    long cpuSpeed;

    strcpy(gState.cpuModel, "Unknown");

    if (Gestalt(gestaltSysVersion, &response) == noErr) {
        /* System version in BCD: 0x750 = 7.5 */
        long major = (response >> 8) & 0x0F;
        long minor = response & 0x0F;
        sprintf(gState.systemVersion, "%ld.%ld", major, minor);
    }

    if (Gestalt(gestaltProcessorType, &response) == noErr) {
        cpuFamily = response;

        switch(cpuFamily) {
            case gestalt68000:
                strcpy(gState.cpuModel, "Motorola 68000");
                gState.entropyScore = 3.0;
                break;
            case gestalt68010:
                strcpy(gState.cpuModel, "Motorola 68010");
                gState.entropyScore = 2.9;
                break;
            case gestalt68020:
                strcpy(gState.cpuModel, "Motorola 68020");
                gState.entropyScore = 2.8;
                break;
            case gestalt68030:
                strcpy(gState.cpuModel, "Motorola 68030");
                gState.entropyScore = 2.6;
                break;
            case gestalt68040:
                strcpy(gState.cpuModel, "Motorola 68040");
                gState.entropyScore = 2.4;
                break;
            case gestalt68060:
                strcpy(gState.cpuModel, "Motorola 68060");
                gState.entropyScore = 2.2;
                break;
            case gestaltPowerPC:
                strcpy(gState.cpuModel, "PowerPC");
                gState.entropyScore = 2.4;

                /* Try to get specific PowerPC model */
                if (Gestalt(gestaltPowerPCSubType, &response) == noErr) {
                    switch(response) {
                        case gestaltPowerPC601:
                            strcat(gState.cpuModel, " 601");
                            gState.entropyScore = 2.5;
                            break;
                        case gestaltPowerPC603:
                            strcat(gState.cpuModel, " 603");
                            gState.entropyScore = 2.3;
                            break;
                        case gestaltPowerPC603e:
                            strcat(gState.cpuModel, " 603e");
                            gState.entropyScore = 2.2;
                            break;
                        case gestaltPowerPC604:
                            strcat(gState.cpuModel, " 604");
                            gState.entropyScore = 2.1;
                            break;
                        case gestaltPowerPC750:
                            strcat(gState.cpuModel, " 750 (G3)");
                            gState.entropyScore = 2.0;
                            break;
                        case gestaltPowerPC7400:
                            strcat(gState.cpuModel, " 7400 (G4)");
                            gState.entropyScore = 1.9;
                            break;
                    }
                }
                break;
            default:
                strcpy(gState.cpuModel, "Unknown Motorola");
                gState.entropyScore = 1.5;
                break;
        }
    }

    /* Get CPU speed in MHz */
    if (Gestalt(gestaltClockSpeed, &response) == noErr) {
        gState.cpuMHz = response / 1000000; /* Convert Hz to MHz */
    } else {
        gState.cpuMHz = 0;
    }

    /* Get machine name */
    if (Gestalt(gestaltMachineName, &response) == noErr) {
        /* response is a handle to a Pascal string */
        Handle h = (Handle)response;
        Str255 name;
        BlockMoveData(*h, name+1, **h);
        name[0] = **h;
        /* Convert Pascal string to C string */
        int len = name[0];
        int i;
        for (i = 0; i < len && i < sizeof(gState.machineName)-1; i++) {
            gState.machineName[i] = name[i+1];
        }
        gState.machineName[i] = '\0';
    } else {
        strcpy(gState.machineName, "Unknown Mac");
    }
}

/*
 * Get System Folder creation timestamp
 * This is a good proxy for when the machine was set up / manufactured
 */
void GetSystemFolderTimestamp(void) {
    FSSpec folderSpec;
    IOParam io;
    short vRefNum;
    long dirID;

    /* Find System Folder */
    if (FindFolder(kOnSystemDisk, kSystemFolderType, kDontCreateFolder, &vRefNum, &dirID) == noErr) {
        /* Get FSSpec for System Folder */
        if (FSMakeFSSpec(vRefNum, dirID, "\pSystem", &folderSpec) == noErr) {
            /* Get creation date */
            HFileInfo fileInfo;
            if (PBGetCatInfoSync(&folderSpec, &fileInfo) == noErr) {
                gState.creationDate = fileInfo.creationDate;
                /* Mac OS epoch is 1904, we need 1970 for ISO */
                return;
            }
        }
    }

    gState.creationDate = 0;
}

/*
 * Convert Mac OS date (seconds since 1904-01-01) to ISO 8601 string
 */
void MacDateToISO(long macDate, char *buf, int bufLen) {
    /* Mac epoch: 1904-01-01 00:00:00 UTC
     * Unix epoch: 1970-01-01 00:00:00 UTC
     * Difference: 2082844800 seconds
     */
    time_t unixDate = (time_t)(macDate - 2082844800UL);
    struct tm *tm = gmtime(&unixDate);

    if (tm != NULL) {
        strftime(buf, bufLen, "%Y-%m-%dT00:00:00Z", tm);
    } else {
        strcpy(buf, "1990-01-01T00:00:00Z");
    }
}

/*
 * Get current timestamp as ISO 8601
 */
void GetCurrentTimestampISO(char *buf, int bufLen) {
    time_t now = time(NULL);
    struct tm *tm = localtime(&now);
    strftime(buf, bufLen, "%Y-%m-%d %H:%M:%S", tm);
}

/*
 * Calculate rarity bonus based on CPU model
 */
double CalculateRarityBonus(void) {
    /* Older/rarer CPUs get higher bonus */
    if (strstr(gState.cpuModel, "68000") != NULL) return 1.20;
    if (strstr(gState.cpuModel, "68010") != NULL) return 1.18;
    if (strstr(gState.cpuModel, "68020") != NULL) return 1.15;
    if (strstr(gState.cpuModel, "68030") != NULL) return 1.10;
    if (strstr(gState.cpuModel, "68040") != NULL) return 1.05;
    if (strstr(gState.cpuModel, "PowerPC 601") != NULL) return 1.08;
    if (strstr(gState.cpuModel, "PowerPC 603") != NULL) return 1.03;
    /* Default bonus */
    return 1.0;
}

/*
 * Generate the proof_of_antiquity.json output file
 */
OSErr GenerateProofFile(void) {
    short refNum;
    OSErr err;
    char isoDate[64];
    char currentDate[64];
    char output[2048];
    long len;
    double rarityBonus = CalculateRarityBonus();
    double finalScore = gState.entropyScore * rarityBonus;

    /* Convert timestamp */
    if (gState.creationDate != 0) {
        MacDateToISO(gState.creationDate, isoDate, sizeof(isoDate));
    } else {
        strcpy(isoDate, "");
    }

    GetCurrentTimestampISO(currentDate, sizeof(currentDate));

    /* Format JSON output */
    if (gState.cpuMHz > 0) {
        sprintf(output,
            "{\n"
            "  \"wallet\": \"%s\",\n"
            "  \"bios_timestamp\": \"%s\",\n"
            "  \"cpu_model\": \"%s\",\n"
            "  \"cpu_mhz\": %ld,\n"
            "  \"system_version\": \"%s\",\n"
            "  \"machine_name\": \"%s\",\n"
            "  \"entropy_score\": %.2f,\n"
            "  \"timestamp\": \"%s\",\n"
            "  \"rarity_bonus\": %.2f\n"
            "}\n",
            gState.walletAddr,
            isoDate,
            gState.cpuModel,
            gState.cpuMHz,
            gState.systemVersion,
            gState.machineName,
            finalScore,
            currentDate,
            rarityBonus
        );
    } else {
        sprintf(output,
            "{\n"
            "  \"wallet\": \"%s\",\n"
            "  \"bios_timestamp\": \"%s\",\n"
            "  \"cpu_model\": \"%s\",\n"
            "  \"system_version\": \"%s\",\n"
            "  \"machine_name\": \"%s\",\n"
            "  \"entropy_score\": %.2f,\n"
            "  \"timestamp\": \"%s\",\n"
            "  \"rarity_bonus\": %.2f\n"
            "}\n",
            gState.walletAddr,
            isoDate,
            gState.cpuModel,
            gState.systemVersion,
            gState.machineName,
            finalScore,
            currentDate,
            rarityBonus
        );
    }

    /* Create the file */
    err = FSpCreate(&(((FileSpec*)(&(((FSSpec*)(&(((FSSpec){currentDirSpec}))))))->fileSpec)), kOutputFileName, 'RUST', 'TEXT');
    if (err != noErr && err != dupFNErr) {
        return err;
    }

    err = FSpOpenDF(&(((FileSpec*)(&(((FSSpec*)(&(((FSSpec){currentDirSpec}))))))->fileSpec)), fsRdWrPerm, &refNum);
    if (err != noErr) {
        return err;
    }

    len = strlen(output);
    err = FSWrite(refNum, &len, output);
    FSClose(refNum);

    return err;
}

/*
 * Simple dialog showing results
 */
void ShowResultDialog(char *message) {
    DialogPtr dialog;
    EventRecord event;
    int buttonHit;

    dialog = GetNewDialog(128, NULL, (WindowPtr)-1);
    SetDialogText(dialog, 1, message);
    ShowWindow(dialog);

    /* Modal loop */
    do {
        ModalDialog(NULL, &buttonHit, &event);
    } while (buttonHit == 0);

    DisposeDialog(dialog);
}

/*
 * Main entry point for Classic Mac
 */
int main(void) {
    OSErr err;
    char resultMsg[512];

    InitGraf(&thePort);
    InitWindows();
    InitMenus();
    TEInit();
    InitDialogs(NULL);
    FlushEvents(everyEvent, 0);

    InitState();

    /* Ask user for wallet address */
    /* In a simple app, we just use a default and note it */
    strcpy(gState.walletAddr, "ENTER_YOUR_WALLET_HERE");

    /* Detect hardware */
    DetectCPUType();
    GetSystemFolderTimestamp();

    /* Write proof file */
    err = GenerateProofFile();

    if (err == noErr) {
        sprintf(resultMsg,
            "Success!\n"
            "CPU: %s @ %ld MHz\n"
            "Machine: %s\n"
            "System: %s\n"
            "Score: %.2f\n"
            "\n"
            "File saved: proof_of_antiquity.json\n"
            "Edit the file to put your wallet address",
            gState.cpuModel,
            gState.cpuMHz,
            gState.machineName,
            gState.systemVersion,
            gState.entropyScore * CalculateRarityBonus()
        );
        ShowResultDialog(resultMsg);
    } else {
        sprintf(resultMsg, "Error writing file: %d", err);
        ShowResultDialog(resultMsg);
    }

    return 0;
}

/* Entry point for THINK C */
#ifdef THINK_C
void main(void) {
    main();
    ExitToShell();
}
#endif
