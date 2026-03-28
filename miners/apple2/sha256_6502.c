/*
 * sha256_6502.c — SHA-256 implementation for the 6502 / CC65
 *
 * Constraints:
 *   - No floats, no 64-bit types.
 *   - uint8_t / uint16_t only for inner loops; uint32_t for the state
 *     words (CC65 emulates 32-bit arithmetic with 4×8-bit operations).
 *   - Fit comfortably in ~4 KB of code + 512 bytes of RAM.
 *   - Lookup tables for the round constants and initial hash values
 *     (placed in ROM-friendly const arrays).
 *
 * Usage:
 *   void sha256_init(SHA256_CTX *ctx);
 *   void sha256_update(SHA256_CTX *ctx, const uint8_t *data, uint16_t len);
 *   void sha256_final(SHA256_CTX *ctx, uint8_t digest[32]);
 *
 * The digest is 32 bytes (256 bits) in big-endian order.
 *
 * CC65 / Apple IIe target.
 */

#include "sha256_6502.h"
#include <string.h>   /* memcpy, memset */

/* ------------------------------------------------------------------ */
/* Round constants K[0..63] — first 32 bits of fractional parts of     */
/* cube roots of first 64 primes.                                       */
/* ------------------------------------------------------------------ */
static const uint32_t K[64] = {
    0x428A2F98UL, 0x71374491UL, 0xB5C0FBCFUL, 0xE9B5DBA5UL,
    0x3956C25BUL, 0x59F111F1UL, 0x923F82A4UL, 0xAB1C5ED5UL,
    0xD807AA98UL, 0x12835B01UL, 0x243185BEUL, 0x550C7DC3UL,
    0x72BE5D74UL, 0x80DEB1FEUL, 0x9BDC06A7UL, 0xC19BF174UL,
    0xE49B69C1UL, 0xEFBE4786UL, 0x0FC19DC6UL, 0x240CA1CCUL,
    0x2DE92C6FUL, 0x4A7484AAUL, 0x5CB0A9DCUL, 0x76F988DAUL,
    0x983E5152UL, 0xA831C66DUL, 0xB00327C8UL, 0xBF597FC7UL,
    0xC6E00BF3UL, 0xD5A79147UL, 0x06CA6351UL, 0x14292967UL,
    0x27B70A85UL, 0x2E1B2138UL, 0x4D2C6DFCUL, 0x53380D13UL,
    0x650A7354UL, 0x766A0ABBUL, 0x81C2C92EUL, 0x92722C85UL,
    0xA2BFE8A1UL, 0xA81A664BUL, 0xC24B8B70UL, 0xC76C51A3UL,
    0xD192E819UL, 0xD6990624UL, 0xF40E3585UL, 0x106AA070UL,
    0x19A4C116UL, 0x1E376C08UL, 0x2748774CUL, 0x34B0BCB5UL,
    0x391C0CB3UL, 0x4ED8AA4AUL, 0x5B9CCA4FUL, 0x682E6FF3UL,
    0x748F82EEUL, 0x78A5636FUL, 0x84C87814UL, 0x8CC70208UL,
    0x90BEFFFAUL, 0xA4506CEBUL, 0xBEF9A3F7UL, 0xC67178F2UL
};

/* Initial hash values H[0..7] */
static const uint32_t H_INIT[8] = {
    0x6A09E667UL, 0xBB67AE85UL, 0x3C6EF372UL, 0xA54FF53AUL,
    0x510E527FUL, 0x9B05688CUL, 0x1F83D9ABUL, 0x5BE0CD19UL
};

/* ------------------------------------------------------------------ */
/* 32-bit rotate right — implemented as 4×8-bit shifts for 6502        */
/* CC65 will generate reasonably efficient code for these.              */
/* ------------------------------------------------------------------ */
#define ROTR32(x, n)  (((x) >> (n)) | ((x) << (32u - (n))))

/* SHA-256 functions */
#define CH(e,f,g)   (((e) & (f)) ^ (~(e) & (g)))
#define MAJ(a,b,c)  (((a) & (b)) ^ ((a) & (c)) ^ ((b) & (c)))
#define EP0(a)      (ROTR32(a, 2)  ^ ROTR32(a, 13) ^ ROTR32(a, 22))
#define EP1(e)      (ROTR32(e, 6)  ^ ROTR32(e, 11) ^ ROTR32(e, 25))
#define SIG0(x)     (ROTR32(x, 7)  ^ ROTR32(x, 18) ^ ((x) >> 3))
#define SIG1(x)     (ROTR32(x, 17) ^ ROTR32(x, 19) ^ ((x) >> 10))

/* ------------------------------------------------------------------ */
/* Internal: process a single 64-byte (512-bit) block                   */
/* ------------------------------------------------------------------ */
static void sha256_transform(SHA256_CTX *ctx, const uint8_t *block)
{
    uint32_t w[64];
    uint32_t a, b, c, d, e, f, g, h;
    uint32_t t1, t2;
    uint8_t  i;

    /* Prepare message schedule W[0..63] */
    for (i = 0; i < 16u; i++) {
        uint8_t base = (uint8_t)(i << 2);
        w[i] = ((uint32_t)block[base    ] << 24)
             | ((uint32_t)block[base + 1] << 16)
             | ((uint32_t)block[base + 2] <<  8)
             | ((uint32_t)block[base + 3]      );
    }
    for (i = 16u; i < 64u; i++) {
        w[i] = SIG1(w[i-2]) + w[i-7] + SIG0(w[i-15]) + w[i-16];
    }

    /* Load working variables */
    a = ctx->state[0]; b = ctx->state[1];
    c = ctx->state[2]; d = ctx->state[3];
    e = ctx->state[4]; f = ctx->state[5];
    g = ctx->state[6]; h = ctx->state[7];

    /* 64 compression rounds */
    for (i = 0; i < 64u; i++) {
        t1 = h + EP1(e) + CH(e,f,g) + K[i] + w[i];
        t2 = EP0(a) + MAJ(a,b,c);
        h = g;  g = f;  f = e;  e = d + t1;
        d = c;  c = b;  b = a;  a = t1 + t2;
    }

    /* Add compressed chunk to current hash state */
    ctx->state[0] += a; ctx->state[1] += b;
    ctx->state[2] += c; ctx->state[3] += d;
    ctx->state[4] += e; ctx->state[5] += f;
    ctx->state[6] += g; ctx->state[7] += h;
}

/* ------------------------------------------------------------------ */
/* Public API                                                           */
/* ------------------------------------------------------------------ */

void sha256_init(SHA256_CTX *ctx)
{
    uint8_t i;
    ctx->bit_len  = 0;
    ctx->data_len = 0;
    for (i = 0; i < 8u; i++) {
        ctx->state[i] = H_INIT[i];
    }
}

void sha256_update(SHA256_CTX *ctx, const uint8_t *data, uint16_t len)
{
    uint16_t i;
    for (i = 0; i < len; i++) {
        ctx->data[ctx->data_len] = data[i];
        ctx->data_len++;
        if (ctx->data_len == 64u) {
            sha256_transform(ctx, ctx->data);
            ctx->bit_len  += 512u;
            ctx->data_len  = 0;
        }
    }
}

void sha256_final(SHA256_CTX *ctx, uint8_t digest[32])
{
    uint16_t i;
    uint16_t pad_start;

    /* Save data_len before padding; bit_len will include final partial block */
    pad_start = ctx->data_len;

    /* Append the 0x80 byte */
    ctx->data[ctx->data_len++] = 0x80u;

    /* Pad to 56 bytes (leaving 8 bytes for length) */
    if (ctx->data_len > 56u) {
        /* Need an extra block */
        while (ctx->data_len < 64u) ctx->data[ctx->data_len++] = 0x00u;
        sha256_transform(ctx, ctx->data);
        ctx->data_len = 0;
    }
    while (ctx->data_len < 56u) ctx->data[ctx->data_len++] = 0x00u;

    /* Append original message length in bits (64-bit big-endian)
     * We only support messages up to 2^16 bytes — the upper 4 bytes
     * are always zero on the 6502. */
    ctx->bit_len += (uint32_t)pad_start * 8u;

    /* Bytes 56-59: high 32 bits of bit_len (zero for short messages) */
    ctx->data[56] = 0x00u;
    ctx->data[57] = 0x00u;
    ctx->data[58] = 0x00u;
    ctx->data[59] = 0x00u;
    /* Bytes 60-63: low 32 bits of bit_len */
    ctx->data[60] = (uint8_t)((ctx->bit_len >> 24) & 0xFFu);
    ctx->data[61] = (uint8_t)((ctx->bit_len >> 16) & 0xFFu);
    ctx->data[62] = (uint8_t)((ctx->bit_len >>  8) & 0xFFu);
    ctx->data[63] = (uint8_t)( ctx->bit_len        & 0xFFu);

    sha256_transform(ctx, ctx->data);

    /* Output digest in big-endian byte order */
    for (i = 0; i < 8u; i++) {
        uint8_t base = (uint8_t)(i << 2);
        digest[base    ] = (uint8_t)((ctx->state[i] >> 24) & 0xFFu);
        digest[base + 1] = (uint8_t)((ctx->state[i] >> 16) & 0xFFu);
        digest[base + 2] = (uint8_t)((ctx->state[i] >>  8) & 0xFFu);
        digest[base + 3] = (uint8_t)( ctx->state[i]        & 0xFFu);
    }
}

/* ------------------------------------------------------------------ */
/* Convenience: SHA-256 a single buffer, output hex string             */
/* hex_out must be at least 65 bytes.                                   */
/* ------------------------------------------------------------------ */
void sha256_hex(const uint8_t *data, uint16_t len, char *hex_out)
{
    SHA256_CTX ctx;
    uint8_t    digest[32];
    uint8_t    i;
    static const char HEX[] = "0123456789abcdef";

    sha256_init(&ctx);
    sha256_update(&ctx, data, len);
    sha256_final(&ctx, digest);

    for (i = 0; i < 32u; i++) {
        hex_out[i*2    ] = HEX[digest[i] >> 4];
        hex_out[i*2 + 1] = HEX[digest[i] & 0x0Fu];
    }
    hex_out[64] = '\0';
}
