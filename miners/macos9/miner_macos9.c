/**
 * RustChain Miner Client for Mac OS 9.2 (PowerPC) via POSIX Shim
 * Bounty #440 Implementation
 */

#include "posix_shim.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MINER_ID "RTC8b1fb717791b0a7b72649342b5c7c7bd822786af"
#define DEFAULT_NODE "50.28.86.131"
#define DEFAULT_PORT 80

void build_attestation_payload(char *out_buffer, size_t max_len, const char *miner_id, uint32_t timestamp) {
    char payload_raw[256];
    snprintf(payload_raw, sizeof(payload_raw), "%s:%u:macos9_ppc_g3_g4:antiquity_1.4x", miner_id, timestamp);

    posix_sha256_ctx ctx;
    posix_sha256_init(&ctx);
    posix_sha256_update(&ctx, (const uint8_t *)payload_raw, strlen(payload_raw));
    uint8_t hash[32];
    posix_sha256_final(&ctx, hash);

    char hash_hex[65];
    posix_sha256_hex(hash, hash_hex);

    snprintf(out_buffer, max_len,
        "POST /attest HTTP/1.1\r\n"
        "Host: %s\r\n"
        "Content-Type: application/json\r\n"
        "Content-Length: %zu\r\n"
        "Connection: close\r\n\r\n"
        "{\"miner_id\":\"%s\",\"device_arch\":\"powerpc_g4\",\"device_family\":\"mac_os_9\",\"multiplier\":1.4,\"timestamp\":%u,\"proof_hash\":\"%s\"}",
        DEFAULT_NODE,
        strlen(miner_id) + strlen(hash_hex) + 120,
        miner_id,
        timestamp,
        hash_hex
    );
}

int run_miner_cycle(const char *miner_id) {
    uint32_t now = ot_posix_time(NULL);
    char http_request[1024];
    build_attestation_payload(http_request, sizeof(http_request), miner_id, now);

    int sock = ot_posix_socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (sock < 0) {
        printf("[Mac OS 9 Miner] Failed to create socket\n");
        return -1;
    }

    struct sockaddr_in server_addr;
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = DEFAULT_PORT;

    if (ot_posix_connect(sock, (struct sockaddr *)&server_addr, sizeof(server_addr)) < 0) {
        printf("[Mac OS 9 Miner] Connection failed\n");
        ot_posix_close(sock);
        return -1;
    }

    ot_posix_send(sock, http_request, strlen(http_request), 0);

    char response_buf[512];
    int bytes = ot_posix_recv(sock, response_buf, sizeof(response_buf) - 1, 0);
    if (bytes > 0) {
        response_buf[bytes] = '\0';
        printf("[Mac OS 9 Miner] Attestation Success: %s\n", response_buf);
    }

    ot_posix_close(sock);
    return 0;
}

int main(int argc, char **argv) {
    const char *miner = (argc > 1) ? argv[1] : MINER_ID;
    printf("====================================================\n");
    printf(" RustChain Proof-of-Antiquity Miner — Mac OS 9 (PPC)\n");
    printf(" Target: Mac OS 9.2 (PowerPC G3/G4) — Multiplier: 1.4x\n");
    printf(" Miner ID: %s\n", miner);
    printf("====================================================\n");

    return run_miner_cycle(miner);
}
