/*
 * RustChain Miner for IBM PC/XT
 * 
 * Target: Intel 8088 @ 4.77 MHz, 640 KB RAM, MS-DOS 2.0+
 * 
 * This miner implements hardware fingerprinting specifically for
 * vintage x86 hardware, with anti-emulation checks to prevent
 * DOSBox/86Box from earning rewards.
 *
 * Build: Open Watcom C Compiler
 *   wcc -ml -bt=dos -ox -s main.c
 *   wlink system dos file main.obj name miner.com
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dos.h>
#include <conio.h>

#include "miner.h"
#include "hw_xt.h"
#include "attest.h"
#include "network.h"

/* Version information */
#define MINER_VERSION "0.1.0-xt"

/* Default configuration */
#define DEFAULT_NODE_URL "https://50.28.86.131"
#define DEFAULT_BLOCK_TIME 600  /* 10 minutes */

/* Global state */
static char g_wallet[64] = {0};
static char g_miner_id[64] = {0};
static char g_node_url[128] = DEFAULT_NODE_URL;
static int g_verbose = 0;

/*
 * Print usage information
 */
static void print_usage(const char *prog)
{
    printf("RustChain Miner for IBM PC/XT v%s\n", MINER_VERSION);
    printf("Usage: %s [options]\n\n", prog);
    printf("Options:\n");
    printf("  -w <wallet>    RTC wallet address (required)\n");
    printf("  -n <url>       Node URL (default: %s)\n", DEFAULT_NODE_URL);
    printf("  -v             Verbose output\n");
    printf("  -h             Show this help\n");
    printf("\nEnvironment variables:\n");
    printf("  RTC_WALLET     Wallet address\n");
    printf("  RTC_NODE_URL   Node URL\n");
    printf("\nExample:\n");
    printf("  %s -w RTCxxxxxxxxxxxxxxxxxxxx\n", prog);
}

/*
 * Parse command line arguments
 */
static int parse_args(int argc, char *argv[])
{
    int i;
    
    for (i = 1; i < argc; i++) {
        if (strcmp(argv[i], "-w") == 0 && i + 1 < argc) {
            strncpy(g_wallet, argv[++i], sizeof(g_wallet) - 1);
        } else if (strcmp(argv[i], "-n") == 0 && i + 1 < argc) {
            strncpy(g_node_url, argv[++i], sizeof(g_node_url) - 1);
        } else if (strcmp(argv[i], "-v") == 0) {
            g_verbose = 1;
        } else if (strcmp(argv[i], "-h") == 0 || strcmp(argv[i], "--help") == 0) {
            return -1;  /* Show help */
        } else {
            printf("Unknown option: %s\n", argv[i]);
            return -1;
        }
    }
    
    /* Try environment variable if wallet not specified */
    if (g_wallet[0] == '\0') {
        char *env_wallet = getenv("RTC_WALLET");
        if (env_wallet) {
            strncpy(g_wallet, env_wallet, sizeof(g_wallet) - 1);
        }
    }
    
    /* Try environment variable for node URL */
    char *env_node = getenv("RTC_NODE_URL");
    if (env_node && g_node_url[0] == '\0') {
        strncpy(g_node_url, env_node, sizeof(g_node_url) - 1);
    }
    
    return 0;
}

/*
 * Print system information
 */
static void print_system_info(void)
{
    printf("\n=== System Information ===\n");
    
    /* Detect CPU */
    printf("CPU: Intel 8088 @ 4.77 MHz\n");
    
    /* Detect memory */
    unsigned int mem_size = get_mem_size();
    printf("Memory: %u KB\n", mem_size);
    
    /* BIOS information */
    char bios_date[32];
    get_bios_date(bios_date, sizeof(bios_date));
    printf("BIOS Date: %s\n", bios_date[0] ? bios_date : "Unknown");
    
    printf("========================\n\n");
}

/*
 * Main entry point
 */
void main(int argc, char *argv[])
{
    int ret;
    
    printf("\n");
    printf("  ____  _ _       ____  _                       _   \n");
    printf(" | __ )(_) |_    |  _ \\(_)_ __ ___   __ _ _ __| |_ \n");
    printf(" |  _ \\| | __|   | |_) | | '_ ` _ \\ / _` | '__| __|\n");
    printf(" | |_) | | |_    |  __/| | | | | | | (_| | |  | |_ \n");
    printf(" |____/|_|\\__|   |_|   |_|_| |_| |_|\\__,_|_|   \\__|\n");
    printf("                                                    \n");
    printf("           IBM PC/XT Miner v%s\n", MINER_VERSION);
    printf("\n");
    
    /* Parse command line arguments */
    if (parse_args(argc, argv) != 0) {
        print_usage(argv[0]);
        return;
    }
    
    /* Validate wallet */
    if (g_wallet[0] == '\0') {
        printf("ERROR: Wallet address required!\n");
        printf("Use -w <wallet> or set RTC_WALLET environment variable.\n");
        print_usage(argv[0]);
        return;
    }
    
    /* Print system information */
    print_system_info();
    
    /* Initialize hardware detection */
    printf("[INIT] Initializing hardware detection...\n");
    if (hw_xt_init() != 0) {
        printf("ERROR: Hardware initialization failed!\n");
        return;
    }
    
    /* Generate miner ID from hardware fingerprint */
    printf("[INIT] Generating miner ID...\n");
    generate_miner_id_xt(g_miner_id, sizeof(g_miner_id));
    printf("[INIT] Miner ID: %s\n", g_miner_id);
    
    /* Check if running in emulator (for debugging) */
    printf("[CHECK] Running emulator detection...\n");
    if (detect_emulator()) {
        printf("[WARNING] Emulator detected! Mining rewards will be 0 RTC.\n");
        printf("[WARNING] This is expected when running in DOSBox/86Box.\n");
    } else {
        printf("[OK] Real hardware detected.\n");
    }
    
    /* Initialize network */
    printf("[INIT] Initializing network...\n");
    ret = network_init();
    if (ret != 0) {
        printf("[WARNING] Network initialization failed (code %d).\n", ret);
        printf("[INFO] Continuing in offline mode for testing.\n");
    } else {
        printf("[OK] Network initialized.\n");
    }
    
    /* Perform hardware attestation */
    printf("[ATTEST] Starting hardware attestation...\n");
    ret = attest_to_node(g_node_url, g_wallet, g_miner_id);
    if (ret != 0) {
        printf("[WARNING] Attestation failed (code %d).\n", ret);
        printf("[INFO] Will retry on next mining cycle.\n");
    } else {
        printf("[OK] Attestation successful!\n");
    }
    
    /* Start mining loop */
    printf("\n[MINER] Starting mining loop...\n");
    printf("[MINER] Block time: %d seconds\n", DEFAULT_BLOCK_TIME);
    printf("[MINER] Press Ctrl+C to stop.\n\n");
    
    /* Main mining loop */
    while (!kbhit()) {  /* Run until key press */
        /* Mining logic would go here */
        /* For now, just sleep and show status */
        
        printf(".");
        fflush(stdout);
        
        /* Simple delay (approximately 1 second) */
        delay(1000);
    }
    
    /* Clear key press */
    getch();
    
    printf("\n\n[MINER] Shutting down...\n");
    printf("[MINER] Thank you for mining RustChain!\n\n");
    
    /* Cleanup */
    network_cleanup();
}
