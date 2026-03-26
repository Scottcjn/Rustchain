/*
 * sha256.h - SHA-256 Hash Implementation
 * 
 * Public domain SHA-256 implementation.
 * No OpenSSL or external dependencies required.
 * Compatible with C89/CodeWarrior/MPW.
 */

#ifndef SHA256_H
#define SHA256_H

#include <stdint.h>
#include <stddef.h>

#define SHA256_BLOCK_SIZE  64   /* 512 bits = 64 bytes */
#define SHA256_DIGEST_SIZE 32   /* 256 bits = 32 bytes */

typedef struct {
    uint32_t state[8];        /* Hash state (A-H) */
    uint64_t bitcount;        /* Total bits hashed */
    uint8_t  buffer[SHA256_BLOCK_SIZE];
    size_t   buflen;          /* Bytes in buffer */
} SHA256_CTX;

void SHA256_Init(SHA256_CTX *ctx);
void SHA256_Update(SHA256_CTX *ctx, const void *data, size_t len);
void SHA256_Final(uint8_t digest[SHA256_DIGEST_SIZE], SHA256_CTX *ctx);

/* One-shot convenience function */
void sha256(const void *data, size_t len, uint8_t digest[SHA256_DIGEST_SIZE]);

/* Hex string convenience (caller provides 65-byte buffer) */
void sha256_hex(const void *data, size_t len, char *hex_out);

#endif /* SHA256_H */
