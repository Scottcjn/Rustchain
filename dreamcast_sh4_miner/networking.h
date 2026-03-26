/* SPDX-License-Identifier: MIT */
/* networking.h - Dreamcast BBA (Broadband Adapter) Networking Interface */

#ifndef NETWORKING_H
#define NETWORKING_H

#include <stdint.h>
#include <stdbool.h>

#define RUSTCHAIN_HOST     "rustchain.org"
#define RUSTCHAIN_PORT     80
#define RUSTCHAIN_FALLBACK_HOST  "50.28.86.131"
#define RUSTCHAIN_FALLBACK_PORT  80
#define API_PATH           "/api/miners"

typedef struct {
    int         state;
    uint32_t    remote_ip;
    uint16_t    remote_port;
    uint16_t    local_port;
    uint8_t     mac[6];
    uint32_t    ip;
    uint8_t     recv_buf[2048];
    int         recv_len;
} BBA_Socket;

bool        net_init(void);
bool        net_is_link_up(void);
void        net_get_mac(uint8_t *mac_out);
uint32_t    net_resolve(const char *hostname);
bool        net_send_http(const char *host, int port, const char *path,
                          const char *body, int body_len,
                          char *response_out, int response_max);
bool        socket_open(BBA_Socket *sock);
bool        socket_connect(BBA_Socket *sock, uint32_t ip, uint16_t port);
bool        socket_send(BBA_Socket *sock, const void *data, int len);
int         socket_recv(BBA_Socket *sock, void *buf, int max_len);
bool        socket_close(BBA_Socket *sock);
bool        submit_attestation(const char *wallet, uint32_t fp_hash, const char *node_url);
uint16_t    htons(uint16_t v);
uint32_t    htonl(uint32_t v);
#define     ntohs(v)  htons(v)
#define     ntohl(v)  htonl(v)

#endif /* NETWORKING_H */
