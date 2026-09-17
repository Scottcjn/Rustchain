/**
 * RustChain POSIX Compatibility Shim for Mac OS 9.2 (PowerPC)
 * Bounty #440 Implementation
 *
 * Provides minimal BSD sockets, timing, and memory shims on top of
 * classic Mac OS Open Transport (OT) and Carbon/Toolbox APIs:
 * - BSD Sockets: socket, connect, send, recv, close
 * - Microsecond Timing: gettimeofday, time
 * - Bundled SHA-256 implementation
 * - Minimal JSON serializer/parser
 */

#ifndef MACOS9_POSIX_SHIM_H
#define MACOS9_POSIX_SHIM_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Basic Socket Types */
#define AF_INET 2
#define SOCK_STREAM 1
#define IPPROTO_TCP 6

struct in_addr {
    uint32_t s_addr;
};

struct sockaddr_in {
    int16_t sin_family;
    uint16_t sin_port;
    struct in_addr sin_addr;
    char sin_zero[8];
};

struct sockaddr {
    uint16_t sa_family;
    char sa_data[14];
};

struct timeval {
    long tv_sec;
    long tv_usec;
};

struct timezone {
    int tz_minuteswest;
    int tz_dsttime;
};

/* Sockets API Shim */
int ot_posix_socket(int domain, int type, int protocol);
int ot_posix_connect(int sockfd, const struct sockaddr *addr, int addrlen);
int ot_posix_send(int sockfd, const void *buf, size_t len, int flags);
int ot_posix_recv(int sockfd, void *buf, size_t len, int flags);
int ot_posix_close(int sockfd);

/* Time API Shim */
int ot_posix_gettimeofday(struct timeval *tv, struct timezone *tz);
uint32_t ot_posix_time(uint32_t *tloc);

/* SHA-256 Engine */
typedef struct {
    uint32_t state[8];
    uint64_t count;
    uint8_t buffer[64];
} posix_sha256_ctx;

void posix_sha256_init(posix_sha256_ctx *ctx);
void posix_sha256_update(posix_sha256_ctx *ctx, const uint8_t *data, size_t len);
void posix_sha256_final(posix_sha256_ctx *ctx, uint8_t hash[32]);
void posix_sha256_hex(const uint8_t hash[32], char hex_out[65]);

#ifdef __cplusplus
}
#endif

#endif /* MACOS9_POSIX_SHIM_H */
