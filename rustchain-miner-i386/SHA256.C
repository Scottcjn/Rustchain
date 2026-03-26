#include "sha256.h"

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

static const uint32_t H0[8] = {
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
    0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19
};

static inline uint32_t rotr(uint32_t x, unsigned n) {
    return (x >> n) | ((x << (32 - n)) & 0xFFFFFFFF);
}

static inline uint32_t Ch(uint32_t x, uint32_t y, uint32_t z) {
    return (x & y) ^ ((~x) & z);
}

static inline uint32_t Maj(uint32_t x, uint32_t y, uint32_t z) {
    return (x & y) ^ (x & z) ^ (y & z);
}

static inline uint32_t Sigma0(uint32_t x) { return rotr(x, 2) ^ rotr(x, 13) ^ rotr(x, 22); }
static inline uint32_t Sigma1(uint32_t x) { return rotr(x, 6) ^ rotr(x, 11) ^ rotr(x, 25); }
static inline uint32_t sigma0(uint32_t x) { return rotr(x, 7) ^ rotr(x, 18) ^ (x >> 3); }
static inline uint32_t sigma1(uint32_t x) { return rotr(x, 17) ^ rotr(x, 19) ^ (x >> 10); }

void sha256_init(sha256_context *ctx) {
    int i;
    for (i = 0; i < 8; i++) ctx->state[i] = H0[i];
    ctx->bitcount = 0;
}

static void sha256_process_block(sha256_context *ctx, const uint8_t *block) {
    uint32_t W[64], a, b, c, d, e, f, g, h, t1, t2;
    int i;
    
    for (i = 0; i < 16; i++) {
        W[i] = ((uint32_t)block[i*4] << 24) |
               ((uint32_t)block[i*4+1] << 16) |
               ((uint32_t)block[i*4+2] << 8) |
               ((uint32_t)block[i*4+3]);
    }
    for (i = 16; i < 64; i++) {
        W[i] = (sigma1(W[i-2]) + W[i-7] + sigma0(W[i-15]) + W[i-16]) & 0xFFFFFFFF;
    }
    
    a = ctx->state[0]; b = ctx->state[1]; c = ctx->state[2]; d = ctx->state[3];
    e = ctx->state[4]; f = ctx->state[5]; g = ctx->state[6]; h = ctx->state[7];
    
    for (i = 0; i < 64; i++) {
        t1 = (h + Sigma1(e) + Ch(e, f, g) + K[i] + W[i]) & 0xFFFFFFFF;
        t2 = (Sigma0(a) + Maj(a, b, c)) & 0xFFFFFFFF;
        h = g; g = f; f = e; e = (d + t1) & 0xFFFFFFFF;
        d = c; c = b; b = a; a = (t1 + t2) & 0xFFFFFFFF;
    }
    
    ctx->state[0] = (ctx->state[0] + a) & 0xFFFFFFFF;
    ctx->state[1] = (ctx->state[1] + b) & 0xFFFFFFFF;
    ctx->state[2] = (ctx->state[2] + c) & 0xFFFFFFFF;
    ctx->state[3] = (ctx->state[3] + d) & 0xFFFFFFFF;
    ctx->state[4] = (ctx->state[4] + e) & 0xFFFFFFFF;
    ctx->state[5] = (ctx->state[5] + f) & 0xFFFFFFFF;
    ctx->state[6] = (ctx->state[6] + g) & 0xFFFFFFFF;
    ctx->state[7] = (ctx->state[7] + h) & 0xFFFFFFFF;
}

void sha256_update(sha256_context *ctx, const uint8_t *data, size_t len) {
    size_t buffer_len = (size_t)((ctx->bitcount >> 3) % 64);
    size_t i;
    
    for (i = 0; i < len; i++) {
        ctx->buffer[buffer_len++] = data[i];
        if (buffer_len == 64) {
            sha256_process_block(ctx, ctx->buffer);
            buffer_len = 0;
        }
        ctx->bitcount += 8;
    }
}

void sha256_final(sha256_context *ctx, uint8_t *hash) {
    uint32_t i;
    size_t buffer_len = (size_t)((ctx->bitcount >> 3) % 64);
    uint8_t pad = 0x80;
    
    sha256_update(ctx, &pad, 1);
    pad = 0x00;
    while (buffer_len != 56) {
        sha256_update(ctx, &pad, 1);
        buffer_len = (size_t)((ctx->bitcount >> 3) % 64);
    }
    
    {
        uint8_t len_bytes[8];
        uint64_t bitlen = ctx->bitcount;
        for (i = 0; i < 8; i++) {
            len_bytes[i] = (uint8_t)((bitlen >> (56 - i * 8)) & 0xFF);
        }
        sha256_update(ctx, len_bytes, 8);
    }
    
    for (i = 0; i < 8; i++) {
        hash[i*4]     = (uint8_t)(ctx->state[i] >> 24);
        hash[i*4 + 1] = (uint8_t)(ctx->state[i] >> 16);
        hash[i*4 + 2] = (uint8_t)(ctx->state[i] >> 8);
        hash[i*4 + 3] = (uint8_t)(ctx->state[i]);
    }
}

void sha256_hash(const uint8_t *data, size_t len, uint8_t *hash) {
    sha256_context ctx;
    sha256_init(&ctx);
    sha256_update(&ctx, data, len);
    sha256_final(&ctx, hash);
}

void sha256_hash_string(const char *str, size_t len, uint8_t *hash) {
    sha256_hash((const uint8_t *)str, len, hash);
}
