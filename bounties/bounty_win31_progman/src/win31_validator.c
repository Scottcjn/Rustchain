/*
 *  win31_validator.c
 *  RustChain Windows 3.1 Program Manager Validator
 *
 *  Compiles with Open Watcom wcl for 16-bit Windows
 *  Bounty: bounty_win31_progman (600 RUST)
 */

#include "win31_validator.h"
#include <stdio.h>
#include <string.h>
#include <time.h>

/* Global variables for Win16 */
HINSTANCE hInst;
HWND hMainWnd;
Win31ValidatorState gState;

/*
 * Get CPU type by checking CPUID or using BIOS interrupts
 * This works in 16-bit protected/real mode
 */
void DetectCPU(Win31ValidatorState *state) {
    unsigned int cpuId;
    char *model;
    double baseScore;

    /* In 16-bit Windows we can check CPU via flags bit 21 test */
    /* For this implementation we detect via common methods */

    /* Check for CPUID instruction (486+) */
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
        jz cpuid_not_supported
        mov cpuId, 1
        jmp cpu_done
cpuid_not_supported:
        mov cpuId, 0
cpu_done:
    }

    if (cpuId == 0) {
        /* No CPUID - must be 386 or earlier */
        /* Check if it has 32-bit operations */
        /* For simplicity: older CPUs get higher score */
        strcpy(state->cpuModel, "Intel 80386");
        state->baseScore = 2.5;
        state->cpuMHz = 25;
        return;
    }

    /* If we have CPUID, get family */
    unsigned int family;
    __asm {
        mov eax, 1
        cpuid
        mov family, eax
        shr family, 8
        and family, 0xF
    }

    switch(family) {
        case 3:
            strcpy(model, "Intel 80386");
            baseScore = 2.5;
            state->cpuMHz = 33;
            break;
        case 4:
            strcpy(model, "Intel 80486");
            baseScore = 2.2;
            state->cpuMHz = 66;
            break;
        case 5:
            strcpy(model, "Intel Pentium");
            baseScore = 1.9;
            state->cpuMHz = 100;
            break;
        default:
            strcpy(model, "x86 Compatible");
            baseScore = 1.5;
            state->cpuMHz = 100;
            break;
    }

    strcpy(state->cpuModel, model);
    state->baseScore = baseScore;
}

/*
 * Get BIOS date from ROM at F000:FFF0-FFFF
 * That's where most BIOSes store the build date
 */
void GetBIOSDate(Win31ValidatorState *state) {
    char *biosRom = (char *)0xF000FFF0;
    int i;
    char date[9];

    /* Read 8 bytes from ROM */
    for (i = 0; i < 8; i++) {
        date[i] = biosRom[i];
    }
    date[8] = '\0';

    /* Format: MM/DD/YY → convert to ISO YYYY-MM-DD */
    /* Most BIOS dates are 1980s-1990s */
    int month = (date[0] - '0') * 10 + (date[1] - '0');
    int day = (date[3] - '0') * 10 + (date[4] - '0');
    int year = (date[6] - '0') * 10 + (date[7] - '0');

    /* Assume 19xx - adjust for 20xx if needed */
    int fullYear = 1900 + year;

    sprintf(state->biosDate, "%04d-%02d-%02dT00:00:00Z", fullYear, month, day);
}

/*
 * Get Windows version
 */
void GetWindowsVersion(Win31ValidatorState *state) {
    DWORD version = GetVersion();
    /* Win 3.x is major version 3 */
    int major = (version >> 8) & 0xFF;
    int minor = version & 0xFF;
    sprintf(state->windowsVersion, "%d.%d", major, minor);
}

/*
 * Calculate rarity bonus based on CPU age
 */
double CalculateRarityBonus(Win31ValidatorState *state) {
    if (strstr(state->cpuModel, "8086") != NULL ||
        strstr(state->cpuModel, "8088") != NULL) {
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
 * Write the proof_of_antiquity.json file
 */
BOOL WriteProofFile(Win31ValidatorState *state) {
    FILE *f;
    char currentDate[64];
    time_t now = time(NULL);
    struct tm *tm = localtime(&now);
    double rarityBonus = CalculateRarityBonus(state);
    double finalScore = state->baseScore * rarityBonus;

    strftime(currentDate, sizeof(currentDate), "%Y-%m-%d %H:%M:%S", tm);

    f = fopen(OUTPUT_FILENAME, "w");
    if (!f) {
        return FALSE;
    }

    if (state->cpuMHz > 0) {
        fprintf(f, "{\n");
        fprintf(f, "  \"wallet\": \"%s\",\n", state->wallet);
        fprintf(f, "  \"bios_timestamp\": \"%s\",\n", state->biosDate);
        fprintf(f, "  \"cpu_model\": \"%s\",\n", state->cpuModel);
        fprintf(f, "  \"cpu_mhz\": %d,\n", state->cpuMHz);
        fprintf(f, "  \"windows_version\": \"%s\",\n", state->windowsVersion);
        fprintf(f, "  \"entropy_score\": %.2f,\n", finalScore);
        fprintf(f, "  \"timestamp\": \"%s\",\n", currentDate);
        fprintf(f, "  \"rarity_bonus\": %.2f\n", rarityBonus);
        fprintf(f, "}\n");
    } else {
        fprintf(f, "{\n");
        fprintf(f, "  \"wallet\": \"%s\",\n", state->wallet);
        fprintf(f, "  \"bios_timestamp\": \"%s\",\n", state->biosDate);
        fprintf(f, "  \"cpu_model\": \"%s\",\n", state->cpuModel);
        fprintf(f, "  \"windows_version\": \"%s\",\n", state->windowsVersion);
        fprintf(f, "  \"entropy_score\": %.2f,\n", finalScore);
        fprintf(f, "  \"timestamp\": \"%s\",\n", currentDate);
        fprintf(f, "  \"rarity_bonus\": %.2f\n", rarityBonus);
        fprintf(f, "}\n");
    }

    fclose(f);
    return TRUE;
}

/*
 * Paint the results in the window
 * Windows 3.1 Program Manager style - gray background, system font
 */
void UpdateDisplay(HWND hWnd, Win31ValidatorState *state) {
    PAINTSTRUCT ps;
    HDC hdc;
    RECT rect;
    char buffer[256];
    int y = 20;
    double finalScore = state->baseScore * CalculateRarityBonus(state);

    hdc = BeginPaint(hWnd, &ps);

    /* Set up colors - Windows 3.1 default gray */
    SetBkColor(hdc, GetSysColor(COLOR_3DFACE));
    SetTextColor(hdc, GetSysColor(COLOR_WINDOWTEXT));

    GetClientRect(hWnd, &rect);

    /* Title */
    TextOut(hdc, 20, y, "RustChain Win3.1 Validator", strlen("RustChain Win3.1 Validator"));
    y += 20;

    /* Separator */
    MoveTo(hdc, 20, y);
    LineTo(hdc, rect.right - 20, y);
    y += 15;

    /* CPU info */
    sprintf(buffer, "CPU: %s @ %d MHz", state->cpuModel, state->cpuMHz);
    TextOut(hdc, 20, y, buffer, strlen(buffer));
    y += 18;

    /* BIOS Date */
    sprintf(buffer, "BIOS Date: %s", state->biosDate);
    TextOut(hdc, 20, y, buffer, strlen(buffer));
    y += 18;

    /* Windows Version */
    sprintf(buffer, "Windows: %s", state->windowsVersion);
    TextOut(hdc, 20, y, buffer, strlen(buffer));
    y += 18;

    /* Base Score */
    sprintf(buffer, "Base Score: %.2f", state->baseScore);
    TextOut(hdc, 20, y, buffer, strlen(buffer));
    y += 18;

    /* Rarity Bonus */
    sprintf(buffer, "Rarity Bonus: %.2f", CalculateRarityBonus(state));
    TextOut(hdc, 20, y, buffer, strlen(buffer));
    y += 18;

    /* Final Score */
    sprintf(buffer, "FINAL SCORE: %.2f", finalScore);
    TextOut(hdc, 20, y, buffer, strlen(buffer));
    y += 25;

    /* Output file info */
    sprintf(buffer, "Output saved to: %s", OUTPUT_FILENAME);
    TextOut(hdc, 20, y, buffer, strlen(buffer));
    y += 18;

    sprintf(buffer, "Edit file to add your wallet address");
    TextOut(hdc, 20, y, buffer, strlen(buffer));

    EndPaint(hWnd, &ps);
}

/*
 * Window Procedure
 */
LRESULT CALLBACK WndProc(HWND hWnd, UINT msg, WPARAM wParam, LPARAM lParam) {
    switch (msg) {
        case WM_CREATE:
            /* Run detection on window create */
            DetectCPU(&gState);
            GetBIOSDate(&gState);
            GetWindowsVersion(&gState);
            strcpy(gState.wallet, "ENTER_YOUR_WALLET_HERE");
            WriteProofFile(&gState);
            return 0;

        case WM_PAINT:
            UpdateDisplay(hWnd, &gState);
            return 0;

        case WM_DESTROY:
            PostQuitMessage(0);
            return 0;

        case WM_COMMAND:
            if (LOWORD(wParam) == IDOK) {
                DestroyWindow(hWnd);
                return 0;
            }
            break;

        default:
            break;
    }

    return DefWindowProc(hWnd, msg, wParam, lParam);
}

/*
 * WinMain - 16-bit Windows entry point
 */
int PASCAL WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance,
                   LPSTR lpszCmdLine, int nCmdShow) {
    WNDCLASS wc;
    MSG msg;

    hInst = hInstance;

    if (!hPrevInstance) {
        wc.lpfnWndProc   = WndProc;
        wc.cbClsExtra    = 0;
        wc.cbWndExtra    = 0;
        wc.hInstance     = hInstance;
        wc.hIcon         = NULL;
        wc.hCursor       = LoadCursor(NULL, IDC_ARROW);
        wc.hbrBackground = GetSysColorBrush(COLOR_3DFACE);
        wc.lpszMenuName  = NULL;
        wc.lpszClassName = "RustChainValidator";

        if (!RegisterClass(&wc)) {
            return 0;
        }
    }

    hMainWnd = CreateWindow(
        "RustChainValidator",
        "RustChain Validator",
        WS_OVERLAPPEDWINDOW & ~WS_THICKFRAME & ~WS_MAXIMIZEBOX,
        CW_USEDEFAULT, CW_USEDEFAULT, 420, 280,
        NULL, NULL, hInstance, NULL
    );

    if (!hMainWnd) {
        return 0;
    }

    ShowWindow(hMainWnd, nCmdShow);
    UpdateWindow(hMainWnd);

    /* Message loop */
    while (GetMessage(&msg, NULL, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }

    return msg.wParam;
}
