/*
 * sha256.c - SHA-256 Hash Implementation (Public Domain)
 * 
 * Pure C implementation - no dependencies beyond standard C.
 * Tested against NIST test vectors.
 * Compatible with: CodeWarrior, MPW, GCC, MSVC, Turbo C.
 * 
 * Target: Mac OS 9 PowerPC (limited stack - use minimal recursion)
 */

#include "sha256.h"
#include <string.h>

/* ============================================================
 * SHA-256 CONSTANTS
 * ============================================================ */

/* Initial hash values (first 32 bits of fractional parts of sqrt(2..9)) */
static const uint32_t K[64] = {
    0x428a2f98u, 0x71374491u, 0xb5c0fbcfu, 0xe9b5dba5u,
    0x3956c25bu, 0x59f111f1u, 0x923f82a4u, 0xab1c5ed5u,
    0xd807aa98u, 0x12835b01u, 0x243185beu, 0x550c7dc3u,
    0x72be5d74u, 0x80deb1feu, 0x9bdc06a7u, 0xc19bf174u,
    0xe49b69c1u, 0xefbe4786u, 0x0fc19dc6u, 0x240ca1ccu,
    0x2de92c6fu, 0x4a7484aau, 0x5cb0a9dcu, 0x76f988dau,
    0x983e5152u, 0xa831c66du, 0xb00327c8u, 0xbf597fc7u,
    0xc6e00bf3u, 0xd5a79147u, 0x06ca6351u, 0x14292967u,
    0x27b70a85u, 0x2e1b2138u, 0x4d2c6dfcu, 0x53380d13u,
    0x650a7354u, 0x766a0abbu, 0x81c2c92eu, 0x92722c85u,
    0xa2bfe8a1u, 0xa81a664bu, 0xc24b8b70u, 0xc76c51a3u,
    0xd192e819u, 0xd6990624u, 0xf40e3585u, 0x106aa070u,
    0x19a4c116u, 0x1e376c08u, 0x2748774cu, 0x34b0bcb5u,
    0x391c0cb3u, 0x4ed8aa4au, 0x5b9cca4fu, 0x682e6ff3u,
    0x748f82eeu, 0x78a5636fu, 0x84c87814u, 0x8cc70208u,
    0x90befffau, 0xa4506cebu, 0xbef9a3f7u, 0xc67178f2u
};

/* Initial state values H0-H7 (same as SHA-256 standard) */
#define H0 0x6a09e667u
#define H1 0xbb67ae85u
#define H2 0x3c6ef372u
#define H3 0xa54ff53au
#define H4 0x510e527fu
#define H5 0x9b05688cu
#define H6 0x1f83d9abu
#define H7 0x5be0cd19u

/* ============================================================
 * INTERNAL MACROS
 * ============================================================ */

/* Right rotate (unlike >>, bits shifted out re-enter on the left) */
#define ROTR(x, n) (((x) >> (n)) | ((x) << (32 - (n))))

/* SHA-256 sigma0, sigma1, Sigma0, Sigma1, Ch, Maj - per FIPS 180-4 */
#define SIGMA0(x) (ROTR((x), 7)  ^ ROTR((x), 18) ^ ((x) >> 3))
#define SIGMA1(x) (ROTR((x), 17) ^ ROTR((x), 19) ^ ((x) >> 10))
#define SIGMA0BIG(x) (ROTR((x), 2)  ^ ROTR((x), 13) ^ ROTR((x), 22))
#define SIGMA1BIG(x) (ROTR((x), 6)  ^ ROTR((x), 11) ^ ROTR((x), 25))
#define CH(x,y,z)   (((x) & (y)) ^ (~(x) & (z)))
#define MAJ(x,y,z) (((x) & (y)) ^ ((x) & (z)) ^ ((y) & (z)))

/* ============================================================
 * CORE SHA-256 TRANSFORM
 * ============================================================ */

static void sha256_transform(SHA256_CTX *ctx)
{
    uint32_t a, b, c, d, e, f, g, h, t1, t2, m[64];
    int i, j;

    /* Expand message schedule from 16 words to 64 words */
    for (i = 0; i < 16; i++) {
        j = i * 4;
        m[i] = ((uint32_t)ctx->buffer[j]     << 24) |
               ((uint32_t)ctx->buffer[j + 1] << 16) |
               ((uint32_t)ctx->buffer[j + 2] <<  8) |
               ((uint32_t)ctx->buffer[j + 3]);
    }
    for (i = 16; i < 64; i++) {
        m[i] = SIGMA1(m[i-2]) + m[i-7] + SIGMA0(m[i-15]) + m[i-16];
    }

    /* Initialize working variables from state */
    a = ctx->state[0];
    b = ctx->state[1];
    c = ctx->state[2];
    d = ctx->state[3];
    e = ctx->state[4];
    f = ctx->state[5];
    g = ctx->state[6];
    h = ctx->state[7];

    /* 64 rounds of compression */
    for (i = 0; i < 64; i++) {
        t1 = h + SIGMA1BIG(e) + CH(e, f, g) + K[i] + m[i];
        t2 = SIGMA0BIG(a) + MAJ(a, b, c);
        h = g;
        g = f;
        f = e;
        e = d + t1;
        d = c;
        c = b;
        b = a;
        a = t1 + t2;
    }

    /* Update state */
    ctx->state[0] += a;
    ctx->state[1] += b;
    ctx->state[2] += c;
    ctx->state[3] += d;
    ctx->state[4] += e;
    ctx->state[5] += f;
    ctx->state[6] += g;
    ctx->state[7] += h;
}

/* ============================================================
 * PUBLIC API
 * ============================================================ */

void SHA256_Init(SHA256_CTX *ctx)
{
    ctx->state[0] = H0;
    ctx->state[1] = H1;
    ctx->state[2] = H2;
    ctx->state[3] = H3;
    ctx->state[4] = H4;
    ctx->state[5] = H5;
    ctx->state[6] = H6;
    ctx->state[7] = H7;
    ctx->bitcount = 0;
    ctx->buflen = 0;
}

void SHA256_Update(SHA256_CTX *ctx, const void *data, size_t len)
{
    const uint8_t *p = (const uint8_t *)data;
    size_t i, fill;

    /* Process any buffered data first */
    if (ctx->buflen > 0) {
        fill = SHA256_BLOCK_SIZE - ctx->buflen;
        if (len < fill) {
            /* Still filling the buffer */
            for (i = 0; i < len; i++) {
                ctx->buffer[ctx->buflen + i] = p[i];
            }
            ctx->buflen += (uint32_t)len;
            ctx->bitcount += (uint64_t)len * 8;
            return;
        } else {
            /* Complete the buffer and transform */
            for (i = 0; i < fill; i++) {
                ctx->buffer[ctx->buflen + i] = p[i];
            }
            sha256_transform(ctx);
            ctx->bitcount += (uint64_t)fill * 8;
            p += fill;
            len -= fill;
            ctx->buflen = 0;
        }
    }

    /* Process complete blocks */
    while (len >= SHA256_BLOCK_SIZE) {
        /* Copy directly into state buffer to avoid extra memcpy */
        for (i = 0; i < SHA256_BLOCK_SIZE; i++) {
            ctx->buffer[i] = p[i];
        }
        sha256_transform(ctx);
        ctx->bitcount += (uint64_t)SHA256_BLOCK_SIZE * 8;
        p += SHA256_BLOCK_SIZE;
        len -= SHA256_BLOCK_SIZE;
    }

    /* Buffer remaining bytes */
    if (len > 0) {
        for (i = 0; i < len; i++) {
            ctx->buffer[i] = p[i];
        }
        ctx->buflen = (uint32_t)len;
        ctx->bitcount += (uint64_t)len * 8;
    }
}

void SHA256_Final(uint8_t digest[SHA256_DIGEST_SIZE], SHA256_CTX *ctx)
{
    uint32_t i;
    uint8_t  pad;
    uint64_t bits_hi, bits_lo;

    /* Compute total bit count (big-endian) */
    bits_hi = (ctx->bitcount >> 32);
    bits_lo = (ctx->bitcount & 0xFFFFFFFFu);

    /* Pad: 0x80, then zeros, then 64-bit BE bit count */
    pad = 0x80;
    SHA256_Update(ctx, &pad, 1);

    pad = 0x00;
    while (ctx->buflen != 56) {
        if (ctx->buflen > 56) {
            /* Need 2 passes */
            SHA256_Update(ctx, &pad, 1);
        } else {
            SHA256_Update(ctx, &pad, (size_t)(56 - ctx->buflen));
            break;
        }
    }

    /* Append bit count (big-endian 64-bit) */
    {
        uint8_t bitcount_be[8];
        bitcount_be[0] = (uint8_t)(bits_hi >> 24);
        bitcount_be[1] = (uint8_t)(bits_hi >> 16);
        bitcount_be[2] = (uint8_t)(bits_hi >>  8);
        bitcount_be[3] = (uint8_t)(bits_hi);
        bitcount_be[4] = (uint8_t)(bits_lo >> 24);
        bitcount_be[5] = (uint8_t)(bits_lo >> 16);
        bitcount_be[6] = (uint8_t)(bits_lo >>  8);
        bitcount_be[7] = (uint8_t)(bits_lo);
        SHA256_Update(ctx, bitcount_be, 8);
    }

    /* Output digest (big-endian) */
    for (i = 0; i < 8; i++) {
        digest[i * 4 + 0] = (uint8_t)(ctx->state[i] >> 24);
        digest[i * 4 + 1] = (uint8_t)(ctx->state[i] >> 16);
        digest[i * 4 + 2] = (uint8_t)(ctx->state[i] >>  8);
        digest[i * 4 + 3] = (uint8_t)(ctx->state[i]);
    }
}

/* One-shot convenience */
void sha256(const void *data, size_t len, uint8_t digest[SHA256_DIGEST_SIZE])
{
    SHA256_CTX ctx;
    SHA256_Init(&ctx);
    SHA256_Update(&ctx, data, len);
    SHA256_Final(digest, &ctx);
}

/* Hex string output (caller provides 65-byte buffer) */
void sha256_hex(const void *data, size_t len, char *hex_out)
{
    uint8_t digest[SHA256_DIGEST_SIZE];
    static const char hexchars[] = "0123456789abcdef";
    size_t i;
    sha256(data, len, digest);
    for (i = 0; i < SHA256_DIGEST_SIZE; i++) {
        hex_out[i * 2 + 0] = hexchars[digest[i] >> 4];
        hex_out[i * 2 + 1] = hexchars[digest[i] & 0x0F];
    }
    hex_out[64] = '\0';
}
