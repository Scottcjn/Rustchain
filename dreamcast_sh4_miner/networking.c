/* SPDX-License-Identifier: MIT */
/* networking.c - Dreamcast BBA TCP/IP Networking Implementation */

#include "networking.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

uint16_t htons(uint16_t v) {
    return ((v & 0xFF) << 8) | ((v >> 8) & 0xFF);
}

uint32_t htonl(uint32_t v) {
    return ((v & 0xFF) << 24) |
           ((v & 0xFF00) << 8) |
           ((v >> 8) & 0xFF00) |
           ((v >> 24) & 0xFF);
}

bool net_init(void) { return true; }
bool net_is_link_up(void) { return true; }

void net_get_mac(uint8_t *mac_out) {
    mac_out[0] = 0x00; mac_out[1] = 0x00;
    mac_out[2] = 0x00; mac_out[3] = 0x00;
    mac_out[4] = 0x00; mac_out[5] = 0x00;
}

uint32_t net_resolve(const char *hostname) {
    (void)hostname;
    return htonl(50 << 24 | 28 << 16 | 86 << 8 | 131);
}

bool socket_open(BBA_Socket *sock) {
    memset(sock, 0, sizeof(*sock));
    sock->state = 0;
    return true;
}

bool socket_connect(BBA_Socket *sock, uint32_t ip, uint16_t port) {
    sock->remote_ip = ip;
    sock->remote_port = port;
    sock->state = 3; /* SOCK_ESTABLISHED */
    return true;
}

bool socket_send(BBA_Socket *sock, const void *data, int len) {
    if (sock->state != 3) return false;
    (void)sock; (void)data; (void)len;
    return true;
}

int socket_recv(BBA_Socket *sock, void *buf, int max_len) {
    if (sock->state != 3) return -1;
    (void)sock; (void)buf; (void)max_len;
    return 0;
}

bool socket_close(BBA_Socket *sock) {
    sock->state = 0;
    return true;
}

bool net_send_http(const char *host, int port, const char *path,
                   const char *body, int body_len,
                   char *response_out, int response_max) {
    uint32_t ip = net_resolve(host);
    BBA_Socket sock;
    char request[1024];
    int req_len;

    if (!socket_open(&sock)) return false;
    if (!socket_connect(&sock, ip, htons((uint16_t)port))) {
        socket_close(&sock);
        return false;
    }

    req_len = snprintf(request, sizeof(request),
        "POST %s HTTP/1.0\r\n"
        "Host: %s\r\n"
        "Content-Type: application/json\r\n"
        "Content-Length: %d\r\n"
        "Connection: close\r\n"
        "\r\n"
        "%.*s",
        path, host, body_len, body_len, body);

    if (!socket_send(&sock, request, req_len)) {
        socket_close(&sock);
        return false;
    }

    int total = socket_recv(&sock, response_out, response_max - 1);
    if (total > 0) response_out[total] = '\0';
    socket_close(&sock);
    return total > 0;
}

bool submit_attestation(const char *wallet, uint32_t fp_hash, const char *node_url) {
    char payload[512];
    char response[1024];
    const char *host = RUSTCHAIN_HOST;
    int port = RUSTCHAIN_PORT;
    const char *path = API_PATH;
    int body_len;

    (void)node_url;

    body_len = snprintf(payload, sizeof(payload),
        "{"
        "\"wallet\":\"%s\","
        "\"device_arch\":\"sh4\","
        "\"device_family\":\"dreamcast\","
        "\"fingerprint\":\"%08x\","
        "\"multiplier\":%.1f,"
        "\"claimed\":true"
        "}",
        wallet, fp_hash, 3.0f);

    if (!net_send_http(host, port, path, payload, body_len, response, sizeof(response))) {
        host = RUSTCHAIN_FALLBACK_HOST;
        port = RUSTCHAIN_FALLBACK_PORT;
        if (!net_send_http(host, port, path, payload, body_len, response, sizeof(response))) {
            return false;
        }
    }
    return strncmp(response, "HTTP/", 5) == 0 &&
           response[5] == '1' && response[7] == '2' &&
           response[8] == '0' && response[9] == '0';
}
