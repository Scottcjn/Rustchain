/*
 * RustChain PlayStation 1 Miner
 * "Fossil Edition" - MIPS R3000A @ 33.87 MHz
 * 
 * Part of the RustChain Proof-of-Antiquity blockchain
 * Antiquity Multiplier: 2.8x (per RIP-304)
 * 
 * Wallet: RTC4325af95d26d59c3ef025963656d22af638bb96b
 */

#include <psxgpu.h>
#include <psxapi.h>
#include <psxpad.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#include "sha256.h"
#include "serial.h"
#include "fingerprint.h"
#include "memcard.h"

/* Version */
#define MINER_VERSION "0.1.0"
#define MINER_NAME "RustChain PS1 Miner"

/* Serial configuration */
#define SERIAL_BAUD 9600
#define SERIAL_BUFFER_SIZE 256

/* Memory card paths */
#define WALLET_PATH "bu00:RUSTCHN/WALLET.DAT"
#define CONFIG_PATH "bu00:RUSTCHN/CONFIG.DAT"

/* Node configuration */
#define NODE_URL "https://rustchain.org"
#define EPOCH_SECONDS 600

/* Global state */
static char wallet_id[64] = {0};
static uint32_t epoch_counter = 0;
static uint32_t last_attestation = 0;

/* Screen buffers */
static DISPENV disp[2];
static DRAWENV draw[2];
static int db = 0;

/* Prototypes */
void init_system(void);
void init_graphic(void);
void print_text(int x, int y, const char* str);
void generate_wallet(void);
int load_wallet(void);
int save_wallet(void);
void run_attestation_cycle(void);
void draw_ui(void);
void pad_update(void);

/* Main entry point */
int main(int argc, char* argv[]) {
    /* Initialize system */
    init_system();
    init_graphic();
    serial_init(SERIAL_BAUD);
    
    printf("%s v%s\n", MINER_NAME, MINER_VERSION);
    printf("MIPS R3000A @ 33.87 MHz | 2 MB RAM\n");
    printf("Antiquity Multiplier: 2.8x\n");
    printf("========================================\n\n");
    
    /* Try to load existing wallet */
    if (!load_wallet()) {
        printf("No wallet found. Generating new wallet...\n");
        generate_wallet();
        if (save_wallet()) {
            printf("Wallet saved to memory card.\n");
        } else {
            printf("WARNING: Could not save wallet!\n");
        }
    }
    
    printf("Wallet: %s\n", wallet_id);
    printf("\n");
    
    /* Run fingerprint checks */
    printf("Running hardware fingerprint checks...\n");
    fingerprint_data_t fp_data;
    if (fingerprint_collect(&fp_data)) {
        printf("Fingerprint collected successfully.\n");
        printf("  BIOS: %s\n", fp_data.bios_version);
        printf("  CD-ROM timing: %d cycles\n", fp_data.cdrom_timing);
        printf("  RAM timing: %d ns\n", fp_data.ram_timing_ns);
    } else {
        printf("WARNING: Fingerprint collection failed!\n");
    }
    printf("\n");
    
    /* Main loop */
    printf("Starting attestation cycles...\n");
    printf("Press SELECT to exit\n\n");
    
    while (1) {
        /* Check controller input */
        pad_update();
        
        /* Run attestation */
        run_attestation_cycle();
        
        /* Wait for next epoch (10 minutes) */
        /* In practice, use VSync for timing */
        for (int i = 0; i < 600 * 60; i++) {  /* 600 seconds * 60 Hz */
            VSync(0);
            pad_update();
        }
    }
    
    return 0;
}

/* Initialize system */
void init_system(void) {
    ResetCallback();
    FlushCache();
}

/* Initialize graphics */
void init_graphic(void) {
    int x, y, w, h;
    
    /* Set display areas */
    x = 0; y = 0; w = 320; h = 240;
    
    SetDefDispEnv(&disp[0], x, y, w, h);
    SetDefDispEnv(&disp[1], x, y + 240, w, h);
    SetDefDrawEnv(&draw[0], x, y + 240, w, h);
    SetDefDrawEnv(&draw[1], x, y, w, h);
    
    SetRGB0(&draw[0], 0, 0, 0);  /* Black background */
    SetRGB0(&draw[1], 0, 0, 0);
    
    PutDispEnv(&disp[0]);
    PutDrawEnv(&draw[0]);
    
    ClearScreen(&draw[0]);
    ClearScreen(&draw[1]);
}

/* Print text to screen */
void print_text(int x, int y, const char* str) {
    /* Simple text rendering - in production, use FntLoad/FntPrint */
    /* For now, just print to serial console */
    printf("%s\n", str);
}

/* Generate new wallet ID */
void generate_wallet(void) {
    uint8_t entropy[32];
    uint8_t hash[32];
    SHA256_CTX ctx;
    
    /* Collect entropy from hardware */
    fingerprint_data_t fp;
    fingerprint_collect(&fp);
    
    /* Combine with timing entropy */
    uint32_t time1 = GetRCnt(0);
    uint32_t time2 = GetRCnt(0);
    uint32_t time3 = GetRCnt(0);
    
    /* Build entropy buffer */
    memcpy(entropy, &fp.bios_hash, 4);
    memcpy(entropy + 4, &fp.cdrom_timing, 4);
    memcpy(entropy + 8, &fp.ram_timing_ns, 4);
    memcpy(entropy + 12, &time1, 4);
    memcpy(entropy + 16, &time2, 4);
    memcpy(entropy + 20, &time3, 4);
    
    /* Add some CPU jitter */
    volatile uint32_t acc = 0;
    for (int i = 0; i < 10000; i++) {
        acc ^= (i * 31);
    }
    memcpy(entropy + 24, &acc, 4);
    
    /* Hash to create wallet ID */
    sha256_init(&ctx);
    sha256_update(&ctx, entropy, 28);
    sha256_final(&ctx, hash);
    
    /* Format as hex string with RTC suffix */
    char hex[65];
    for (int i = 0; i < 19; i++) {
        sprintf(hex + (i * 2), "%02x", hash[i]);
    }
    hex[38] = '\0';
    
    snprintf(wallet_id, sizeof(wallet_id), "%sRTC", hex);
}

/* Load wallet from memory card */
int load_wallet(void) {
    /* Try to open wallet file */
    int fd = open(WALLET_PATH, O_RDONLY);
    if (fd < 0) {
        return 0;  /* File not found */
    }
    
    /* Read wallet ID */
    int len = read(fd, wallet_id, sizeof(wallet_id) - 1);
    close(fd);
    
    if (len > 0) {
        wallet_id[len] = '\0';
        return 1;
    }
    
    return 0;
}

/* Save wallet to memory card */
int save_wallet(void) {
    /* Create directory if needed */
    mkdir("bu00:RUSTCHN");
    
    /* Open file for writing */
    int fd = open(WALLET_PATH, O_WRONLY | O_CREAT | O_TRUNC);
    if (fd < 0) {
        return 0;
    }
    
    /* Write wallet ID */
    int len = strlen(wallet_id);
    int written = write(fd, wallet_id, len);
    close(fd);
    
    return (written == len);
}

/* Run attestation cycle */
void run_attestation_cycle(void) {
    char buffer[SERIAL_BUFFER_SIZE];
    char response[SERIAL_BUFFER_SIZE];
    
    printf("\n[Epoch %d] Starting attestation...\n", epoch_counter);
    
    /* Collect fresh fingerprint */
    fingerprint_data_t fp;
    if (!fingerprint_collect(&fp)) {
        printf("ERROR: Fingerprint collection failed\n");
        return;
    }
    
    /* Build attestation JSON */
    /* Simplified format for PS1 */
    snprintf(buffer, sizeof(buffer),
        "ATTEST:{"
        "\"wallet\":\"%s\","
        "\"epoch\":%d,"
        "\"bios_hash\":%u,"
        "\"cdrom_timing\":%d,"
        "\"ram_timing\":%d,"
        "\"nonce\":%u"
        "}",
        wallet_id,
        epoch_counter,
        fp.bios_hash,
        fp.cdrom_timing,
        fp.ram_timing_ns,
        GetRCnt(0)  /* Use timer as nonce */
    );
    
    /* Send to PC bridge via serial */
    printf("Sending: %s\n", buffer);
    serial_send(buffer, strlen(buffer));
    
    /* Wait for response */
    int len = serial_recv(response, sizeof(response) - 1);
    if (len > 0) {
        response[len] = '\0';
        printf("Response: %s\n", response);
        
        if (strstr(response, "OK")) {
            printf("Attestation successful!\n");
            last_attestation = epoch_counter;
        } else {
            printf("Attestation failed.\n");
        }
    } else {
        printf("No response from bridge.\n");
    }
    
    epoch_counter++;
}

/* Controller input handling */
static unsigned short pad_buf[2];
static struct PADTYPE* pad[2];

void pad_update(void) {
    int i;
    static int first = 1;
    
    if (first) {
        first = 0;
        for (i = 0; i < 2; i++) {
            pad_buf[i] = 0;
            pad[i] = (struct PADTYPE*)getPadBase(i + 1);
            if (pad[i]) {
                setPadPort(i + 1, 0, 1);
            }
        }
    }
    
    for (i = 0; i < 2; i++) {
        if (pad[i]) {
            pad[i] = (struct PADTYPE*)padState(i + 1, 0, pad_buf);
            if (pad_buf[i] & PADL_SEL) {
                /* SELECT pressed - exit */
                printf("Exiting...\n");
                exit(0);
            }
        }
    }
}

/* Clear screen helper */
void ClearScreen(DRAWENV* env) {
    RECT rect;
    setRECT(&rect, env->ox, env->oy, env->w, env->h);
    ClearImage(&rect, 0, 0, 0);
}
