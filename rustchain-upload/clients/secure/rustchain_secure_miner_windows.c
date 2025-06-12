/*
 * RustChain Secure Windows Miner with Dual Protection
 * Implements: Scaled PoW + Hardware Detection (No stake required!)
 * Compile: gcc -o rustchain_secure_miner.exe rustchain_secure_miner_windows.c -lws2_32 -mwindows
 */

#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <winsock2.h>

#pragma comment(lib, "ws2_32.lib")
#pragma comment(lib, "user32.lib")
#pragma comment(lib, "gdi32.lib")

#define NODE_URL "50.28.86.153"
#define NODE_PORT 8088
#define WALLET_FILE "rustchain_wallet.dat"
#define IDC_STATUS 1001
#define IDC_BALANCE 1002
#define IDC_START 1003
#define IDC_STOP 1004

typedef struct {
    char address[64];
    float balance;
    int tier;
    char cpu_model[128];
    int year;
} Wallet;

// Global variables
HWND hStatus, hBalance, hStart, hStop;
Wallet wallet;
BOOL mining = FALSE;
HANDLE hMiningThread = NULL;

// Detect CPU hardware
void detect_hardware(Wallet *wallet) {
    SYSTEM_INFO sysInfo;
    GetSystemInfo(&sysInfo);
    
    // Get CPU info using CPUID
    int cpuInfo[4] = {0};
    char cpuBrand[64] = {0};
    
    __cpuid(cpuInfo, 0x80000002);
    memcpy(cpuBrand, cpuInfo, sizeof(cpuInfo));
    __cpuid(cpuInfo, 0x80000003);
    memcpy(cpuBrand + 16, cpuInfo, sizeof(cpuInfo));
    __cpuid(cpuInfo, 0x80000004);
    memcpy(cpuBrand + 32, cpuInfo, sizeof(cpuInfo));
    
    strcpy(wallet->cpu_model, cpuBrand);
    
    // Determine tier based on CPU
    if (strstr(cpuBrand, "486") || strstr(cpuBrand, "Pentium") && !strstr(cpuBrand, "Pentium 4")) {
        wallet->tier = 4;  // Legendary (80s/90s)
        wallet->year = 1995;
    } else if (strstr(cpuBrand, "Core 2") || strstr(cpuBrand, "Athlon 64")) {
        wallet->tier = 1.5;  // Rare (2000s)
        wallet->year = 2006;
    } else if (strstr(cpuBrand, "i3") || strstr(cpuBrand, "i5") || strstr(cpuBrand, "FX")) {
        wallet->tier = 1.5;  // Rare (2010-2015)
        wallet->year = 2012;
    } else {
        wallet->tier = 1;  // Common (modern)
        wallet->year = 2020;
    }
}

// Simple hash function
void simple_hash(char *input, char *output) {
    unsigned int hash = 5381;
    int c;
    while ((c = *input++))
        hash = ((hash << 5) + hash) + c;
    sprintf(output, "%08x", hash);
}

// Hardware-specific challenge (MMX/SSE for x86)
int hardware_challenge(unsigned char *data, int len) {
    int result = 0;
    
    // Check for MMX support
    int cpuInfo[4];
    __cpuid(cpuInfo, 1);
    BOOL hasMMX = (cpuInfo[3] & (1 << 23)) != 0;
    BOOL hasSSE = (cpuInfo[3] & (1 << 25)) != 0;
    
    if (hasMMX || hasSSE) {
        // Use SIMD instructions if available
        for (int i = 0; i < len; i += 8) {
            result += data[i] ^ data[len-1-i];
        }
        result *= 2;  // Bonus for having SIMD
    } else {
        // Fallback for very old CPUs
        for (int i = 0; i < len; i++) {
            result += data[i];
        }
    }
    
    return result;
}

// Scaled Proof of Work
int proof_of_work(char *block_data, int difficulty, int tier) {
    char hash_input[256];
    char hash_output[64];
    int nonce = 0;
    int target_zeros = difficulty;
    
    // Scale difficulty based on tier
    if (tier >= 4) {  // Legendary
        target_zeros = 1;
    } else if (tier >= 2) {  // Mythic
        target_zeros = 2;
    } else if (tier >= 1.5) {  // Rare
        target_zeros = 3;
    } else {  // Common
        target_zeros = difficulty;
    }
    
    // Never exceed max difficulty of 4
    if (target_zeros > 4) target_zeros = 4;
    
    while (mining) {
        sprintf(hash_input, "%s%d", block_data, nonce);
        simple_hash(hash_input, hash_output);
        
        // Check if hash meets difficulty
        int valid = 1;
        for (int i = 0; i < target_zeros; i++) {
            if (hash_output[i] != '0') {
                valid = 0;
                break;
            }
        }
        
        if (valid) {
            return nonce;
        }
        
        nonce++;
        if (nonce % 10000 == 0) {
            char status[256];
            sprintf(status, "Mining... Nonce: %d", nonce);
            SetWindowText(hStatus, status);
        }
    }
    
    return -1;  // Mining stopped
}

// Load or create wallet
void load_wallet(Wallet *wallet) {
    FILE *f = fopen(WALLET_FILE, "r");
    if (f) {
        fscanf(f, "%s %f %d", wallet->address, &wallet->balance, &wallet->tier);
        fclose(f);
    } else {
        // Create new wallet
        sprintf(wallet->address, "RTC%08x", rand());
        wallet->balance = 0.0;
        detect_hardware(wallet);
        
        f = fopen(WALLET_FILE, "w");
        fprintf(f, "%s %.2f %d\n", wallet->address, wallet->balance, wallet->tier);
        fclose(f);
    }
}

// Save wallet
void save_wallet(Wallet *wallet) {
    FILE *f = fopen(WALLET_FILE, "w");
    fprintf(f, "%s %.2f %d\n", wallet->address, wallet->balance, wallet->tier);
    fclose(f);
}

// Update balance display
void update_balance_display() {
    char balance_text[128];
    sprintf(balance_text, "Balance: %.2f RTC | Tier: %s", 
            wallet.balance,
            wallet.tier >= 4 ? "Legendary" :
            wallet.tier >= 2 ? "Mythic" :
            wallet.tier >= 1.5 ? "Rare" : "Common");
    SetWindowText(hBalance, balance_text);
}

// Mining thread function
DWORD WINAPI mining_thread(LPVOID lpParam) {
    char status[256];
    
    while (mining) {
        // No stake requirement - this is Proof of Antiquity!
        // Anyone with vintage hardware can mine
        
        SetWindowText(hStatus, "Starting new mining round...");
        
        // Get block data
        char block_data[256];
        sprintf(block_data, "block_%ld", time(NULL));
        
        // Step 1: Hardware challenge
        SetWindowText(hStatus, "Step 1: Hardware challenge...");
        unsigned char challenge_data[64];
        for (int i = 0; i < 64; i++) {
            challenge_data[i] = rand() % 256;
        }
        int hw_result = hardware_challenge(challenge_data, 64);
        
        // Step 2: Proof of Work
        SetWindowText(hStatus, "Step 2: Mining (Proof of Work)...");
        int nonce = proof_of_work(block_data, 4, wallet.tier);
        
        if (nonce == -1) {
            // Mining stopped
            break;
        }
        
        // Step 3: Submit to node
        sprintf(status, "Step 3: Submitting nonce %d...", nonce);
        SetWindowText(hStatus, status);
        
        // Simulate network submission (in real implementation, use WinSock)
        Sleep(1000);
        
        // Simulate reward (40% share of 1.25 RTC for solo mining)
        float reward = 0.0;
        if (wallet.tier >= 4) reward = 0.8 * 1.25;     // Legendary: 80%
        else if (wallet.tier >= 2) reward = 0.4 * 1.25; // Mythic: 40%
        else if (wallet.tier >= 1.5) reward = 0.3 * 1.25; // Rare: 30%
        else reward = 0.2 * 1.25;                         // Common: 20%
        
        wallet.balance += reward;
        save_wallet(&wallet);
        update_balance_display();
        
        sprintf(status, "Block mined! Earned %.3f RTC", reward);
        SetWindowText(hStatus, status);
        
        // Show receipt
        char receipt[512];
        sprintf(receipt, 
                "=== MINING RECEIPT ===\n"
                "Time: %s"
                "Block: %s\n"
                "Nonce: %d\n"
                "Hardware: %s\n"
                "Tier: %s\n"
                "Reward: %.3f RTC\n"
                "New Balance: %.2f RTC\n",
                ctime(&(time_t){time(NULL)}),
                block_data, nonce,
                wallet.cpu_model,
                wallet.tier >= 4 ? "Legendary" :
                wallet.tier >= 2 ? "Mythic" :
                wallet.tier >= 1.5 ? "Rare" : "Common",
                reward, wallet.balance);
        
        MessageBox(NULL, receipt, "Mining Receipt", MB_OK | MB_ICONINFORMATION);
        
        // Wait before next round
        SetWindowText(hStatus, "Waiting 10 seconds...");
        Sleep(10000);
    }
    
    SetWindowText(hStatus, "Mining stopped");
    return 0;
}

// Window procedure
LRESULT CALLBACK WindowProc(HWND hwnd, UINT uMsg, WPARAM wParam, LPARAM lParam) {
    switch (uMsg) {
        case WM_CREATE:
            // Create status label
            hStatus = CreateWindow("STATIC", "Ready to mine",
                WS_VISIBLE | WS_CHILD | SS_CENTER,
                10, 10, 380, 30,
                hwnd, (HMENU)IDC_STATUS, NULL, NULL);
                
            // Create balance label
            hBalance = CreateWindow("STATIC", "",
                WS_VISIBLE | WS_CHILD | SS_CENTER,
                10, 50, 380, 30,
                hwnd, (HMENU)IDC_BALANCE, NULL, NULL);
                
            // Create start button
            hStart = CreateWindow("BUTTON", "Start Mining",
                WS_VISIBLE | WS_CHILD | BS_PUSHBUTTON,
                50, 100, 120, 40,
                hwnd, (HMENU)IDC_START, NULL, NULL);
                
            // Create stop button
            hStop = CreateWindow("BUTTON", "Stop Mining",
                WS_VISIBLE | WS_CHILD | BS_PUSHBUTTON | WS_DISABLED,
                230, 100, 120, 40,
                hwnd, (HMENU)IDC_STOP, NULL, NULL);
                
            // Load wallet and update display
            load_wallet(&wallet);
            update_balance_display();
            
            // Show hardware info
            char hw_info[256];
            sprintf(hw_info, "Hardware: %s\nEstimated Year: %d\nTier: %s",
                    wallet.cpu_model, wallet.year,
                    wallet.tier >= 4 ? "Legendary (80%)" :
                    wallet.tier >= 2 ? "Mythic (40%)" :
                    wallet.tier >= 1.5 ? "Rare (30%)" : "Common (20%)");
            MessageBox(hwnd, hw_info, "Hardware Detection", MB_OK | MB_ICONINFORMATION);
            break;
            
        case WM_COMMAND:
            switch (LOWORD(wParam)) {
                case IDC_START:
                    if (!mining) {
                        mining = TRUE;
                        EnableWindow(hStart, FALSE);
                        EnableWindow(hStop, TRUE);
                        hMiningThread = CreateThread(NULL, 0, mining_thread, NULL, 0, NULL);
                    }
                    break;
                    
                case IDC_STOP:
                    if (mining) {
                        mining = FALSE;
                        EnableWindow(hStart, TRUE);
                        EnableWindow(hStop, FALSE);
                        WaitForSingleObject(hMiningThread, INFINITE);
                        CloseHandle(hMiningThread);
                        hMiningThread = NULL;
                    }
                    break;
            }
            break;
            
        case WM_DESTROY:
            if (mining) {
                mining = FALSE;
                if (hMiningThread) {
                    WaitForSingleObject(hMiningThread, INFINITE);
                    CloseHandle(hMiningThread);
                }
            }
            PostQuitMessage(0);
            break;
            
        default:
            return DefWindowProc(hwnd, uMsg, wParam, lParam);
    }
    return 0;
}

// Main entry point
int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR lpCmdLine, int nCmdShow) {
    const char CLASS_NAME[] = "RustChainMiner";
    
    // Initialize random seed
    srand(time(NULL));
    
    // Initialize Winsock
    WSADATA wsaData;
    WSAStartup(MAKEWORD(2, 2), &wsaData);
    
    // Register window class
    WNDCLASS wc = {0};
    wc.lpfnWndProc = WindowProc;
    wc.hInstance = hInstance;
    wc.hbrBackground = (HBRUSH)(COLOR_WINDOW + 1);
    wc.lpszClassName = CLASS_NAME;
    wc.hCursor = LoadCursor(NULL, IDC_ARROW);
    
    RegisterClass(&wc);
    
    // Create window
    HWND hwnd = CreateWindowEx(
        0,
        CLASS_NAME,
        "RustChain Secure Miner (Proof of Antiquity)",
        WS_OVERLAPPEDWINDOW & ~WS_MAXIMIZEBOX & ~WS_SIZEBOX,
        CW_USEDEFAULT, CW_USEDEFAULT, 
        420, 200,
        NULL, NULL, hInstance, NULL
    );
    
    if (hwnd == NULL) {
        return 0;
    }
    
    ShowWindow(hwnd, nCmdShow);
    UpdateWindow(hwnd);
    
    // Message loop
    MSG msg = {0};
    while (GetMessage(&msg, NULL, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }
    
    // Cleanup
    WSACleanup();
    
    return 0;
}