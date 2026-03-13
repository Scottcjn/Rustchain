/*
 * SHA-256 Implementation for MIPS R3000A
 * Optimized for PS1 (no FPU, 32-bit only)
 * 
 * Based on FIPS 180-4 specification
 */

#include "sha256.h"
#include <stdint.h>
#include <string.h>

/* SHA-256 constants */
static const uint32_t K[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5,
    0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
    0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
    0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
    0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
    0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3,
    0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5,
    0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
};

/* Rotate right */
#define ROTR(x, n) (((x) >> (n)) | ((x) << (32 - (n))))

/* SHA-256 functions */
#define CH(x, y, z)  (((x) & (y)) ^ (~(x) & (z)))
#define MAJ(x, y, z) (((x) & (y)) ^ ((x) & (z)) ^ ((y) & (z)))
#define EP0(x)       (ROTR(x, 2)  ^ ROTR(x, 13) ^ ROTR(x, 22))
#define EP1(x)       (ROTR(x, 6)  ^ ROTR(x, 11) ^ ROTR(x, 25))
#define SIG0(x)      (ROTR(x, 7)  ^ ROTR(x, 18) ^ ((x) >> 3))
#define SIG1(x)      (ROTR(x, 17) ^ ROTR(x, 19) ^ ((x) >> 10))

/* Initialize SHA-256 context */
void sha256_init(SHA256_CTX* ctx) {
    ctx->state[0] = 0x6a09e667;
    ctx->state[1] = 0xbb67ae85;
    ctx->state[2] = 0x3c6ef372;
    ctx->state[3] = 0xa54ff53a;
    ctx->state[4] = 0x510e527f;
    ctx->state[5] = 0x9b05688c;
    ctx->state[6] = 0x1f83d9ab;
    ctx->state[7] = 0x5be0cd19;
    
    ctx->count = 0;
    ctx->buflen = 0;
}

/* Transform a 512-bit block */
static void sha256_transform(uint32_t* state, const uint8_t* block) {
    uint32_t a, b, c, d, e, f, g, h;
    uint32_t W[64];
    uint32_t t1, t2;
    int i;
    
    /* Unpack the block into 16 32-bit words (big-endian) */
    for (i = 0; i < 16; i++) {
        W[i] = ((uint32_t)block[i * 4] << 24) |
               ((uint32_t)block[i * 4 + 1] << 16) |
               ((uint32_t)block[i * 4 + 2] << 8) |
               ((uint32_t)block[i * 4 + 3]);
    }
    
    /* Extend the 16 words into 64 words */
    for (i = 16; i < 64; i++) {
        uint32_t s0 = SIG0(W[i - 15]);
        uint32_t s1 = SIG1(W[i - 2]);
        W[i] = W[i - 16] + s0 + W[i - 7] + s1;
    }
    
    /* Initialize working variables */
    a = state[0];
    b = state[1];
    c = state[2];
    d = state[3];
    e = state[4];
    f = state[5];
    g = state[6];
    h = state[7];
    
    /* Main loop - 64 rounds */
    for (i = 0; i < 64; i++) {
        t1 = h + EP1(e) + CH(e, f, g) + K[i] + W[i];
        t2 = EP0(a) + MAJ(a, b, c);
        
        h = g;
        g = f;
        f = e;
        e = d + t1;
        d = c;
        c = b;
        b = a;
        a = t1 + t2;
    }
    
    /* Add compressed chunk to current hash value */
    state[0] += a;
    state[1] += b;
    state[2] += c;
    state[3] += d;
    state[4] += e;
    state[5] += f;
    state[6] += g;
    state[7] += h;
}

/* Update hash with data */
void sha256_update(SHA256_CTX* ctx, const uint8_t* data, size_t len) {
    size_t i;
    
    /* Process remaining data from previous call */
    if (ctx->buflen > 0) {
        size_t to_copy = 64 - ctx->buflen;
        if (len < to_copy) {
            to_copy = len;
        }
        
        memcpy(ctx->buffer + ctx->buflen, data, to_copy);
        ctx->buflen += to_copy;
        data += to_copy;
        len -= to_copy;
        
        if (len > 0 && ctx->buflen < 64) {
            return;
        }
        
        sha256_transform(ctx->state, ctx->buffer);
        ctx->count += 64;
    }
    
    /* Process full blocks */
    while (len >= 64) {
        sha256_transform(ctx->state, data);
        ctx->count += 64;
        data += 64;
        len -= 64;
    }
    
    /* Save remaining data */
    if (len > 0) {
        memcpy(ctx->buffer, data, len);
        ctx->buflen = len;
    }
}

/* Pad and finalize hash */
void sha256_final(SHA256_CTX* ctx, uint8_t* hash) {
    uint8_t pad[64];
    uint8_t len_bytes[8];
    uint64_t total_bits;
    int i;
    
    /* Calculate total bits */
    total_bits = (ctx->count * 8) + (ctx->buflen * 8);
    
    /* Convert to big-endian */
    for (i = 0; i < 8; i++) {
        len_bytes[i] = (total_bits >> (56 - i * 8)) & 0xFF;
    }
    
    /* Pad with 0x80 followed by zeros */
    pad[0] = 0x80;
    memset(pad + 1, 0, 63);
    
    /* Add padding */
    if (ctx->buflen < 56) {
        sha256_update(ctx, pad, 56 - ctx->buflen);
    } else {
        sha256_update(ctx, pad, 64 - ctx->buflen);
        sha256_update(ctx, pad, 56);
    }
    
    /* Add length */
    sha256_update(ctx, len_bytes, 8);
    
    /* Output hash (big-endian) */
    for (i = 0; i < 8; i++) {
        hash[i * 4 + 0] = (ctx->state[i] >> 24) & 0xFF;
        hash[i * 4 + 1] = (ctx->state[i] >> 16) & 0xFF;
        hash[i * 4 + 2] = (ctx->state[i] >> 8) & 0xFF;
        hash[i * 4 + 3] = ctx->state[i] & 0xFF;
    }
}

/* Convenience function: hash a single buffer */
void sha256(const uint8_t* data, size_t len, uint8_t* hash) {
    SHA256_CTX ctx;
    sha256_init(&ctx);
    sha256_update(&ctx, data, len);
    sha256_final(&ctx, hash);
}

/* Test vector verification */
int sha256_test(void) {
    /* Test vector: "abc" */
    static const uint8_t test_data[] = "abc";
    static const uint8_t expected[] = {
        0xba, 0x78, 0x16, 0xbf, 0x8f, 0x01, 0xcf, 0xea,
        0x41, 0x41, 0x40, 0xde, 0x5d, 0xae, 0x22, 0x23,
        0xb0, 0x03, 0x61, 0xa3, 0x96, 0x17, 0x7a, 0x9c,
        0xb4, 0x10, 0xff, 0x61, 0xf2, 0x00, 0x15, 0xad
    };
    
    uint8_t hash[32];
    sha256(test_data, 3, hash);
    
    return (memcmp(hash, expected, 32) == 0) ? 1 : 0;
}
