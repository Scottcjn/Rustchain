/*
 * SHA-256 Header for MIPS R3000A
 */

#ifndef SHA256_H
#define SHA256_H

#include <stdint.h>
#include <stddef.h>

/* SHA-256 context structure */
typedef struct {
    uint32_t state[8];      /* Hash state */
    uint64_t count;         /* Total bytes processed */
    uint8_t buffer[64];     /* 512-bit block buffer */
    size_t buflen;          /* Bytes in buffer */
} SHA256_CTX;

/* Initialize SHA-256 context */
void sha256_init(SHA256_CTX* ctx);

/* Update hash with data */
void sha256_update(SHA256_CTX* ctx, const uint8_t* data, size_t len);

/* Finalize and output hash (32 bytes) */
void sha256_final(SHA256_CTX* ctx, uint8_t* hash);

/* Convenience function: hash a single buffer */
void sha256(const uint8_t* data, size_t len, uint8_t* hash);

/* Test vector verification (returns 1 if pass) */
int sha256_test(void);

#endif /* SHA256_H */
