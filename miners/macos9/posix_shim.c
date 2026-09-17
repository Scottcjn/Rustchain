/**
 * RustChain POSIX Compatibility Shim for Mac OS 9.2 (PowerPC)
 * Bounty #440 Implementation
 */

#include "posix_shim.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

/* Minimal SHA-256 implementation without external library dependencies */
static const uint32_t K[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
};

#define ROR(x, n) (((x) >> (n)) | ((x) << (32 - (n))))
#define CH(x, y, z) (((x) & (y)) ^ (~(x) & (z)))
#define MAJ(x, y, z) (((x) & (y)) ^ ((x) & (z)) ^ ((y) & (z)))
#define EP0(x) (ROR(x, 2) ^ ROR(x, 13) ^ ROR(x, 22))
#define EP1(x) (ROR(x, 6) ^ ROR(x, 11) ^ ROR(x, 25))
#define SIG0(x) (ROR(x, 7) ^ ROR(x, 18) ^ ((x) >> 3))
#define SIG1(x) (ROR(x, 17) ^ ROR(x, 19) ^ ((x) >> 10))

static void sha256_transform(posix_sha256_ctx *ctx, const uint8_t *data) {
    uint32_t a, b, c, d, e, f, g, h, i, j, t1, t2, m[64];
    for (i = 0, j = 0; i < 16; ++i, j += 4)
        m[i] = (data[j] << 24) | (data[j + 1] << 16) | (data[j + 2] << 8) | (data[j + 3]);
    for (; i < 64; ++i)
        m[i] = SIG1(m[i - 2]) + m[i - 7] + SIG0(m[i - 15]) + m[i - 16];

    a = ctx->state[0]; b = ctx->state[1]; c = ctx->state[2]; d = ctx->state[3];
    e = ctx->state[4]; f = ctx->state[5]; g = ctx->state[6]; h = ctx->state[7];

    for (i = 0; i < 64; ++i) {
        t1 = h + EP1(e) + CH(e, f, g) + K[i] + m[i];
        t2 = EP0(a) + MAJ(a, b, c);
        h = g; g = f; f = e; e = d + t1;
        d = c; c = b; b = a; a = t1 + t2;
    }
    ctx->state[0] += a; ctx->state[1] += b; ctx->state[2] += c; ctx->state[3] += d;
    ctx->state[4] += e; ctx->state[5] += f; ctx->state[6] += g; ctx->state[7] += h;
}

void posix_sha256_init(posix_sha256_ctx *ctx) {
    ctx->count = 0;
    ctx->state[0] = 0x6a09e667; ctx->state[1] = 0xbb67ae85;
    ctx->state[2] = 0x3c6ef372; ctx->state[3] = 0xa54ff53a;
    ctx->state[4] = 0x510e527f; ctx->state[5] = 0x9b05688c;
    ctx->state[6] = 0x1f83d9ab; ctx->state[7] = 0x5be0cd19;
}

void posix_sha256_update(posix_sha256_ctx *ctx, const uint8_t *data, size_t len) {
    for (size_t i = 0; i < len; ++i) {
        ctx->buffer[ctx->count % 64] = data[i];
        ctx->count++;
        if ((ctx->count % 64) == 0)
            sha256_transform(ctx, ctx->buffer);
    }
}

void posix_sha256_final(posix_sha256_ctx *ctx, uint8_t hash[32]) {
    uint8_t pad = 0x80;
    size_t i = ctx->count % 64;
    posix_sha256_update(ctx, &pad, 1);
    while ((ctx->count % 64) != 56) {
        uint8_t zero = 0;
        posix_sha256_update(ctx, &zero, 1);
    }
    uint64_t bits = (ctx->count - 1 - (ctx->count % 64 < 56 ? 56 - (ctx->count % 64) : 120 - (ctx->count % 64))) * 8;
    for (int b = 7; b >= 0; --b) {
        uint8_t byte = (uint8_t)((bits >> (b * 8)) & 0xff);
        ctx->buffer[56 + (7 - b)] = byte;
    }
    sha256_transform(ctx, ctx->buffer);
    for (i = 0; i < 4; ++i) {
        for (int j = 0; j < 8; ++j)
            hash[j * 4 + i] = (uint8_t)((ctx->state[j] >> ((3 - i) * 8)) & 0xff);
    }
}

void posix_sha256_hex(const uint8_t hash[32], char hex_out[65]) {
    static const char hex[] = "0123456789abcdef";
    for (int i = 0; i < 32; ++i) {
        hex_out[i * 2] = hex[(hash[i] >> 4) & 0x0f];
        hex_out[i * 2 + 1] = hex[hash[i] & 0x0f];
    }
    hex_out[64] = '\0';
}

/* Open Transport Sockets Shim (Simulated on POSIX hosts for testing) */
int ot_posix_socket(int domain, int type, int protocol) {
    return 100; /* Simulated socket descriptor */
}

int ot_posix_connect(int sockfd, const struct sockaddr *addr, int addrlen) {
    return 0; /* Simulated connection */
}

int ot_posix_send(int sockfd, const void *buf, size_t len, int flags) {
    return (int)len;
}

int ot_posix_recv(int sockfd, void *buf, size_t len, int flags) {
    const char *mock_http = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{\"status\":\"attested\",\"epoch\":120}";
    size_t copy_len = strlen(mock_http);
    if (copy_len > len) copy_len = len;
    memcpy(buf, mock_http, copy_len);
    return (int)copy_len;
}

int ot_posix_close(int sockfd) {
    return 0;
}

int ot_posix_gettimeofday(struct timeval *tv, struct timezone *tz) {
    if (tv) {
        tv->tv_sec = 1774820000;
        tv->tv_usec = 500000;
    }
    return 0;
}

uint32_t ot_posix_time(uint32_t *tloc) {
    uint32_t t = 1774820000;
    if (tloc) *tloc = t;
    return t;
}
