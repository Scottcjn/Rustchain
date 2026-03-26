#ifndef SHA256_H
#define SHA256_H

#include <stdint.h>
#include <stddef.h>

typedef struct {
    uint32_t state[8];
    uint64_t bitcount;
    uint8_t buffer[64];
} sha256_context;

void sha256_init(sha256_context *ctx);
void sha256_update(sha256_context *ctx, const uint8_t *data, size_t len);
void sha256_final(sha256_context *ctx, uint8_t *hash);
void sha256_hash(const uint8_t *data, size_t len, uint8_t *hash);
void sha256_hash_string(const char *str, size_t len, uint8_t *hash);

#endif
