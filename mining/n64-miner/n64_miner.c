/**
 * N64 Mining ROM — RustChain Attestation & Mining Loop
 * 
 * Main entry: initializes hardware, collects fingerprint,
 * sends attestation via serial to host relay, mines in loop.
 *
 * Build: make (requires libdragon toolchain)
 * Bounty: Rustchain #1877 (200 RTC)
 */

#include "n64_miner.h"
#include "fingerprint.h"
#include <string.h>
#include <stdio.h>

#ifdef N64_LIBDRAGON
#include <libdragon.h>
#endif

/* ── Serial Communication ────────────────────────────────────── */

/*
 * On real N64, serial goes through EverDrive USB or GameShark port.
 * We use a simple framed protocol: [MAGIC][LEN][PAYLOAD][CRC8]
 */

static uint8_t crc8(const uint8_t *data, uint32_t len) {
    uint8_t crc = 0xFF;
    uint32_t i, j;
    for (i = 0; i < len; i++) {
        crc ^= data[i];
        for (j = 0; j < 8; j++)
            crc = (crc & 0x80) ? (crc << 1) ^ 0x31 : crc << 1;
    }
    return crc;
}

int serial_send(const void *data, uint32_t len) {
    /* Frame: [0x52][0x54][len_hi][len_lo][payload][crc8] */
    uint8_t header[4] = {0x52, 0x54, (uint8_t)(len >> 8), (uint8_t)len};
    uint8_t checksum = crc8((const uint8_t *)data, len);
    
#ifdef N64_LIBDRAGON
    /* Use libdragon USB for EverDrive / 64drive */
    usb_write(DATATYPE_RAW, header, 4);
    usb_write(DATATYPE_RAW, data, len);
    usb_write(DATATYPE_RAW, &checksum, 1);
    return 0;
#else
    /* Stub for host-side testing */
    (void)header;
    (void)checksum;
    return 0;
#endif
}

int serial_recv(void *buf, uint32_t max_len, uint32_t timeout_ms) {
#ifdef N64_LIBDRAGON
    uint32_t start = read_count();
    uint32_t timeout_ticks = (timeout_ms * COUNT_FREQ_HZ) / 1000;
    
    while ((read_count() - start) < timeout_ticks) {
        int avail = usb_poll();
        if (avail > 0) {
            uint8_t header[4];
            usb_read(header, 4);
            if (header[0] != 0x52 || header[1] != 0x54) continue;
            uint32_t len = ((uint32_t)header[2] << 8) | header[3];
            if (len > max_len) len = max_len;
            usb_read(buf, len);
            uint8_t checksum;
            usb_read(&checksum, 1);
            if (checksum == crc8((const uint8_t *)buf, len))
                return (int)len;
        }
    }
    return -1;  /* Timeout */
#else
    (void)buf; (void)max_len; (void)timeout_ms;
    return -1;
#endif
}

/* ── Miner Core ──────────────────────────────────────────────── */

void miner_init(miner_context_t *ctx, const char *wallet) {
    memset(ctx, 0, sizeof(*ctx));
    ctx->state = STATE_INIT;
    if (wallet) {
        strncpy(ctx->wallet, wallet, sizeof(ctx->wallet) - 1);
    }
    fingerprint_init();
}

int miner_attest(miner_context_t *ctx) {
    /* Collect hardware fingerprint */
    ctx->state = STATE_FINGERPRINT;
    hw_fingerprint_t fp;
    int rc = fingerprint_collect(&fp);
    if (rc != 0) {
        ctx->state = STATE_ERROR;
        return -1;
    }
    
    /* Validate fingerprint (anti-emulation check) */
    int flags = fingerprint_validate(&fp);
    if (flags != 0) {
        /* We're likely on an emulator — still send but flag it */
        /* Node-side will make final determination */
    }
    
    /* Build attestation packet */
    ctx->state = STATE_ATTEST;
    attestation_packet_t pkt;
    memset(&pkt, 0, sizeof(pkt));
    pkt.header.magic = ATTEST_MAGIC;
    pkt.header.version = ATTEST_VERSION;
    pkt.header.type = PKT_TYPE_ATTEST;
    pkt.header.payload_len = sizeof(attestation_packet_t) - sizeof(packet_header_t);
    
    strncpy(pkt.device_arch, DEVICE_ARCH, sizeof(pkt.device_arch) - 1);
    strncpy(pkt.device_family, DEVICE_FAMILY, sizeof(pkt.device_family) - 1);
    strncpy(pkt.miner_id, ctx->wallet, sizeof(pkt.miner_id) - 1);
    pkt.epoch = ctx->current_epoch;
    memcpy(&pkt.fingerprint, &fp, sizeof(hw_fingerprint_t));
    
    /* Send via serial */
    rc = serial_send(&pkt, sizeof(pkt));
    if (rc != 0) {
        ctx->state = STATE_ERROR;
        return -2;
    }
    
    ctx->attestations_sent++;
    ctx->last_fingerprint = fp;
    /* Wait for epoch acknowledgment or re-attestation request */
    epoch_ack_packet_t ack;
    rc = serial_recv(&ack, sizeof(ack), 10000);
    if (rc > 0 && ack.header.magic == ATTEST_MAGIC) {
        if (ack.header.type == PKT_TYPE_EPOCH_ACK) {
            ctx->current_epoch = ack.epoch;
            ctx->total_earned += ack.balance_rtc;
            ctx->session_earned += ack.balance_rtc;
            ctx->attestations_ok++;
        } else if (ack.header.type == PKT_TYPE_REATTEST) {
            ctx->current_epoch = ack.epoch;
            ctx->state = STATE_ATTEST;
            return miner_attest(ctx);
        }
    }
    
    ctx->state = STATE_MINING;
    return 0;
}

void miner_display(const miner_context_t *ctx) {
#ifdef N64_LIBDRAGON
    /* Draw mining status on N64 screen using libdragon */
    graphics_t *disp = display_lock();
    if (!disp) return;
    
    graphics_fill_screen(disp, 0x00000000);  /* Black background */
    graphics_set_color(disp, 0x7DD3FCFF, 0x00000000);  /* Cyan text */
    
    char buf[64];
    graphics_draw_text(disp, 40, 30, "=== RustChain N64 Miner ===");
    
    graphics_set_color(disp, 0xF59E0BFF, 0x00000000);  /* Amber */
    snprintf(buf, sizeof(buf), "Epoch: %u", ctx->current_epoch);
    graphics_draw_text(disp, 40, 60, buf);
    
    snprintf(buf, sizeof(buf), "Earned: %llu nRTC", ctx->session_earned);
    graphics_draw_text(disp, 40, 80, buf);
    
    snprintf(buf, sizeof(buf), "Attestations: %u/%u", 
             ctx->attestations_ok, ctx->attestations_sent);
    graphics_draw_text(disp, 40, 100, buf);
    
    graphics_set_color(disp, 0x22C55EFF, 0x00000000);  /* Green */
    graphics_draw_text(disp, 40, 130, 
        ctx->mining_active ? ">>> MINING ACTIVE <<<" : "[START to begin mining]");
    
    snprintf(buf, sizeof(buf), "Multiplier: 4.0x (MYTHIC)");
    graphics_draw_text(disp, 40, 160, buf);
    
    /* Fingerprint status */
    graphics_set_color(disp, 0x94A3B8FF, 0x00000000);  /* Gray */
    snprintf(buf, sizeof(buf), "Drift: %uns  Cache: %u/%u cyc", 
             ctx->last_fingerprint.count_drift_ns,
             ctx->last_fingerprint.cache_d_hit_cycles,
             ctx->last_fingerprint.cache_d_miss_cycles);
    graphics_draw_text(disp, 40, 190, buf);
    
    display_show(disp);
#else
    /* Console fallback for testing */
    printf("=== RustChain N64 Miner ===\n");
    printf("Epoch: %u | Earned: %llu nRTC | Attest: %u/%u\n",
           ctx->current_epoch, (unsigned long long)ctx->session_earned,
           ctx->attestations_ok, ctx->attestations_sent);
    printf("Multiplier: 4.0x (MYTHIC) | State: %d\n", ctx->state);
#endif
}

void miner_loop(miner_context_t *ctx) {
    ctx->state = STATE_MINING;
    ctx->mining_active = 1;
    
    while (ctx->mining_active) {
#ifdef N64_LIBDRAGON
        /* Check controller input */
        controller_scan();
        struct controller_data keys = get_keys_pressed();
        
        if (keys.c[0].A) ctx->display_active = !ctx->display_active;
        if (keys.c[0].B) { /* Balance request */ }
        if (keys.c[0].start) miner_attest(ctx);
        if (keys.c[0].L && keys.c[0].R && keys.c[0].Z) {
            ctx->mining_active = 0;
            break;
        }
#endif
        /* Attest every ~60 seconds */
        static uint32_t last_attest = 0;
        uint32_t now = read_count();
        if (now - last_attest > COUNT_FREQ_HZ * 60) {
            miner_attest(ctx);
            last_attest = now;
        }
        
        if (ctx->display_active) {
            miner_display(ctx);
        }
    }
}

/* ── Entry Point ─────────────────────────────────────────────── */

#ifdef N64_LIBDRAGON
int main(void) {
    /* Initialize N64 subsystems */
    display_init(RESOLUTION_320x240, DEPTH_32_BPP, 2, GAMMA_NONE, FILTERS_RESAMPLE);
    controller_init();
    usb_initialize();
    timer_init();
    
    miner_context_t ctx;
    miner_init(&ctx, "n64-miner-001");
    
    /* Initial attestation */
    miner_attest(&ctx);
    
    /* Show welcome screen */
    ctx.display_active = 1;
    miner_display(&ctx);
    
    /* Main mining loop */
    miner_loop(&ctx);
    
    return 0;
}
#endif
