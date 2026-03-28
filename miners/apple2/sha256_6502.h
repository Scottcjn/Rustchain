/*
 * sha256_6502.h — SHA-256 for 8-bit 6502 / CC65
 */

#ifndef SHA256_6502_H
#define SHA256_6502_H

#include <stdint.h>

typedef struct {
    uint8_t  data[64];
    uint8_t  data_len;
    uint32_t bit_len;
    uint32_t state[8];
} SHA256_CTX;

void sha256_init(SHA256_CTX *ctx);
void sha256_update(SHA256_CTX *ctx, const uint8_t *data, uint16_t len);
void sha256_final(SHA256_CTX *ctx, uint8_t digest[32]);
void sha256_hex(const uint8_t *data, uint16_t len, char *hex_out);

#endif /* SHA256_6502_H */
