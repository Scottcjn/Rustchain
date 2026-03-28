/*
 * miner6502.c — RustChain PoA Miner for Apple IIe (MOS 6502)
 *
 * Targets CC65 compiler: cl65 -t apple2enh -O miner6502.c sha256_6502.c -o MINER
 *
 * Networking via Uthernet II (W5100 chip in slot 3).
 * No floats, no 64-bit types, 8/16-bit arithmetic only.
 *
 * License: MIT
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <conio.h>      /* CC65: cgetc, cputs, gotoxy */
#include <peekpoke.h>   /* CC65: PEEK, POKE */

#include "w5100.h"
#include "sha256_6502.h"

/* ------------------------------------------------------------------ */
/*  Configuration                                                      */
/* ------------------------------------------------------------------ */

#define NODE_HOST       "rustchain.org"
#define NODE_PORT       8088
#define ATTEST_PATH     "/attest/submit"
#define MINER_ID        "apple2-miner"
#define DEVICE_ARCH     "6502"
#define POLL_SECONDS    60      /* seconds between attestations */

/* Uthernet II default slot */
#define UTHERNET_SLOT   3

/* ------------------------------------------------------------------ */
/*  Hardware fingerprint                                               */
/* ------------------------------------------------------------------ */

/*
 * On a real 6502, we measure cycle timing by counting loop iterations
 * during a fixed-duration busy wait. The exact count depends on the
 * CPU clock (1.023 MHz for Apple IIe) and bus timing quirks.
 * Emulators rarely get the sub-cycle timing exactly right.
 */

static unsigned int fp_cycle_count;
static unsigned char fp_ram_banks;
static unsigned char fp_aux_ram;

static void measure_fingerprint(void) {
    unsigned int count = 0;
    unsigned char i;

    /*
     * Timing loop: increment counter while checking a hardware
     * register that changes at a known rate. On Apple IIe, the
     * keyboard strobe ($C000) bit 7 clears on read of $C010.
     * We use the vertical blank counter instead — read $C019.
     *
     * Count iterations during one vertical blank period (~16.7ms).
     */
    /* Wait for VBL to start */
    while (PEEK(0xC019) < 0x80) { ++count; }
    count = 0;
    /* Count during VBL */
    while (PEEK(0xC019) >= 0x80) { ++count; }

    fp_cycle_count = count;

    /* Detect auxiliary RAM (128K IIe) */
    /* Try switching to aux RAM bank */
    POKE(0xC005, 0);   /* Write to aux */
    POKE(0x0800, 0xA5); /* Write marker */
    POKE(0xC004, 0);   /* Back to main */

    fp_aux_ram = 0;
    if (PEEK(0x0800) != 0xA5) {
        /* Main RAM didn't see the write — aux RAM exists */
        POKE(0xC005, 0);
        if (PEEK(0x0800) == 0xA5) {
            fp_aux_ram = 1;
        }
        POKE(0xC004, 0);   /* Back to main */
    }

    /* Count RAM pages (each page = 256 bytes) */
    fp_ram_banks = fp_aux_ram ? 128 : 64;  /* 128KB or 64KB */
}

/* ------------------------------------------------------------------ */
/*  JSON payload builder (manual, no library)                          */
/* ------------------------------------------------------------------ */

static char json_buf[512];

static void build_payload(void) {
    char hash_hex[65];
    unsigned char hash[32];
    sha256_ctx ctx;
    char tmp[32];

    /* Hash the fingerprint data for a unique identifier */
    sha256_init(&ctx);

    /* Convert cycle count to string and hash it */
    sprintf(tmp, "%u", fp_cycle_count);
    sha256_update(&ctx, (const unsigned char *)tmp, strlen(tmp));

    sprintf(tmp, "%u", (unsigned int)fp_ram_banks);
    sha256_update(&ctx, (const unsigned char *)tmp, strlen(tmp));

    sha256_final(&ctx, hash);

    /* Convert hash to hex string (first 16 chars) */
    {
        unsigned char j;
        static const char hex[] = "0123456789abcdef";
        for (j = 0; j < 8; j++) {
            hash_hex[j * 2]     = hex[hash[j] >> 4];
            hash_hex[j * 2 + 1] = hex[hash[j] & 0x0F];
        }
        hash_hex[16] = '\0';
    }

    sprintf(json_buf,
        "{\"miner\":\"%s\","
        "\"device\":{\"arch\":\"%s\",\"cores\":1,\"model\":\"MOS6502\",\"clock_mhz\":1},"
        "\"fingerprint\":{"
            "\"cycle_count\":%u,"
            "\"ram_kb\":%u,"
            "\"aux_ram\":%s,"
            "\"simd_identity\":\"%s\""
        "}}",
        MINER_ID,
        DEVICE_ARCH,
        fp_cycle_count,
        (unsigned int)fp_ram_banks,
        fp_aux_ram ? "true" : "false",
        hash_hex
    );
}

/* ------------------------------------------------------------------ */
/*  HTTP POST via W5100                                                */
/* ------------------------------------------------------------------ */

static char http_buf[768];

static int http_post(const char *host, unsigned int port,
                     const char *path, const char *body)
{
    unsigned int body_len;
    int rc;

    body_len = strlen(body);

    /* Build HTTP request */
    sprintf(http_buf,
        "POST %s HTTP/1.0\r\n"
        "Host: %s\r\n"
        "Content-Type: application/json\r\n"
        "Content-Length: %u\r\n"
        "Connection: close\r\n"
        "\r\n"
        "%s",
        path, host, body_len, body
    );

    /* Connect */
    rc = w5100_connect(host, port);
    if (rc != 0) {
        cputs("W5100: connect failed\r\n");
        return -1;
    }

    /* Send */
    rc = w5100_send((const unsigned char *)http_buf, strlen(http_buf));
    if (rc < 0) {
        cputs("W5100: send failed\r\n");
        w5100_close();
        return -2;
    }

    /* Receive response (just check status line) */
    memset(http_buf, 0, sizeof(http_buf));
    rc = w5100_recv((unsigned char *)http_buf, sizeof(http_buf) - 1);

    w5100_close();

    if (rc <= 0) {
        cputs("W5100: no response\r\n");
        return -3;
    }

    /* Check for "200" in status line */
    if (strstr(http_buf, "200") != NULL) {
        return 0;   /* success */
    }

    return -4;  /* non-200 */
}

/* ------------------------------------------------------------------ */
/*  Display                                                            */
/* ------------------------------------------------------------------ */

static unsigned int epoch_count = 0;

static void show_status(int result) {
    clrscr();

    cputs("================================\r\n");
    cputs("  RustChain PoA Miner - 6502\r\n");
    cputs("  Apple IIe @ 1.023 MHz\r\n");
    cputs("================================\r\n\r\n");

    cputs("Fingerprint:\r\n");
    cprintf("  Cycle count: %u\r\n", fp_cycle_count);
    cprintf("  RAM: %uKB", (unsigned int)fp_ram_banks);
    if (fp_aux_ram) cputs(" (aux)");
    cputs("\r\n\r\n");

    cprintf("Epochs: %u\r\n", epoch_count);
    cputs("Status: ");

    if (result == 0) {
        cputs("ATTESTED OK\r\n");
    } else {
        cprintf("ERROR %d\r\n", result);
    }

    cputs("\r\nPress Q to quit, any key for info\r\n");
}

/* ------------------------------------------------------------------ */
/*  Delay (busy wait, ~1 second per call)                              */
/* ------------------------------------------------------------------ */

static void delay_1s(void) {
    /* Apple IIe: ~1.023 MHz, this loop is roughly calibrated */
    unsigned int i;
    for (i = 0; i < 10000; i++) {
        /* Each iteration ~100 cycles at 1 MHz ≈ 1 second total */
        __asm__("nop");
        __asm__("nop");
        __asm__("nop");
    }
}

static void delay_seconds(unsigned char secs) {
    unsigned char i;
    for (i = 0; i < secs; i++) {
        delay_1s();
        /* Check for keypress */
        if (kbhit()) return;
    }
}

/* ------------------------------------------------------------------ */
/*  Main                                                               */
/* ------------------------------------------------------------------ */

int main(void) {
    int rc;

    clrscr();
    cputs("RustChain 6502 Miner v1.0\r\n");
    cputs("Initializing...\r\n\r\n");

    /* Init W5100 */
    cputs("W5100 init (slot 3)...\r\n");
    rc = w5100_init(UTHERNET_SLOT);
    if (rc != 0) {
        cputs("ERROR: Uthernet II not found!\r\n");
        cputs("Check slot 3 and try again.\r\n");
        cgetc();
        return 1;
    }
    cputs("Uthernet II ready.\r\n\r\n");

    /* Measure hardware fingerprint */
    cputs("Measuring fingerprint...\r\n");
    measure_fingerprint();
    cprintf("  Cycles: %u  RAM: %uKB\r\n",
            fp_cycle_count, (unsigned int)fp_ram_banks);
    cputs("\r\nStarting attestation loop...\r\n");

    /* Main attestation loop */
    for (;;) {
        /* Build JSON payload */
        build_payload();

        /* Submit attestation */
        rc = http_post(NODE_HOST, NODE_PORT, ATTEST_PATH, json_buf);

        if (rc == 0) {
            ++epoch_count;
        }

        show_status(rc);

        /* Wait, check for quit */
        delay_seconds(POLL_SECONDS);

        if (kbhit()) {
            char c = cgetc();
            if (c == 'q' || c == 'Q') {
                cputs("\r\nShutting down...\r\n");
                w5100_close();
                return 0;
            }
        }
    }

    /* Not reached */
    return 0;
}
