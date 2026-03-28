/*
 * sha256.h - Minimal SHA-256 for Intel 386 / C89
 *
 * No 64-bit types. Uses only sha256_u32 (four bytes).
 * Counts message length as two 32-bit words (lo/hi) to stay FPU-free.
 *
 * Usage:
 *   SHA256_CTX ctx;
 *   sha256_init(&ctx);
 *   sha256_update(&ctx, data, len);
 *   sha256_final(&ctx, digest);  // digest[32]
 *
 * Public domain — no warranty.
 */

#ifndef SHA256_H
#define SHA256_H

#include <string.h>

/*
 * Private type aliases with sha256_ prefix to avoid conflicts with
 * system <stdint.h> on modern hosts.  All internal to this header.
 */
typedef unsigned char  sha256_u8;
typedef unsigned short sha256_u16;
typedef unsigned long  sha256_u32;

typedef struct {
    sha256_u32 state[8];
    sha256_u32 count_lo;   /* bit count, low 32 bits  */
    sha256_u32 count_hi;   /* bit count, high 32 bits */
    sha256_u8  buf[64];
    unsigned int buflen;
} SHA256_CTX;

/* ---- internal helpers ------------------------------------------ */

#define ROR32(x, n) (((x) >> (n)) | ((x) << (32 - (n))))
#define CH(x,y,z)   (((x) & (y)) ^ (~(x) & (z)))
#define MAJ(x,y,z)  (((x) & (y)) ^ ((x) & (z)) ^ ((y) & (z)))
#define EP0(x)      (ROR32(x,2)  ^ ROR32(x,13) ^ ROR32(x,22))
#define EP1(x)      (ROR32(x,6)  ^ ROR32(x,11) ^ ROR32(x,25))
#define SIG0(x)     (ROR32(x,7)  ^ ROR32(x,18) ^ ((x) >> 3))
#define SIG1(x)     (ROR32(x,17) ^ ROR32(x,19) ^ ((x) >> 10))

static const sha256_u32 sha256_k[64] = {
    0x428a2f98UL, 0x71374491UL, 0xb5c0fbcfUL, 0xe9b5dba5UL,
    0x3956c25bUL, 0x59f111f1UL, 0x923f82a4UL, 0xab1c5ed5UL,
    0xd807aa98UL, 0x12835b01UL, 0x243185beUL, 0x550c7dc3UL,
    0x72be5d74UL, 0x80deb1feUL, 0x9bdc06a7UL, 0xc19bf174UL,
    0xe49b69c1UL, 0xefbe4786UL, 0x0fc19dc6UL, 0x240ca1ccUL,
    0x2de92c6fUL, 0x4a7484aaUL, 0x5cb0a9dcUL, 0x76f988daUL,
    0x983e5152UL, 0xa831c66dUL, 0xb00327c8UL, 0xbf597fc7UL,
    0xc6e00bf3UL, 0xd5a79147UL, 0x06ca6351UL, 0x14292967UL,
    0x27b70a85UL, 0x2e1b2138UL, 0x4d2c6dfcUL, 0x53380d13UL,
    0x650a7354UL, 0x766a0abbUL, 0x81c2c92eUL, 0x92722c85UL,
    0xa2bfe8a1UL, 0xa81a664bUL, 0xc24b8b70UL, 0xc76c51a3UL,
    0xd192e819UL, 0xd6990624UL, 0xf40e3585UL, 0x106aa070UL,
    0x19a4c116UL, 0x1e376c08UL, 0x2748774cUL, 0x34b0bcb5UL,
    0x391c0cb3UL, 0x4ed8aa4aUL, 0x5b9cca4fUL, 0x682e6ff3UL,
    0x748f82eeUL, 0x78a5636fUL, 0x84c87814UL, 0x8cc70208UL,
    0x90befffaUL, 0xa4506cebUL, 0xbef9a3f7UL, 0xc67178f2UL
};

static void sha256_transform(SHA256_CTX *ctx, const sha256_u8 *block)
{
    sha256_u32 w[64];
    sha256_u32 a, b, c, d, e, f, g, h;
    sha256_u32 t1, t2;
    int i;

    for (i = 0; i < 16; i++) {
        w[i] = ((sha256_u32)block[i*4  ] << 24)
             | ((sha256_u32)block[i*4+1] << 16)
             | ((sha256_u32)block[i*4+2] <<  8)
             | ((sha256_u32)block[i*4+3]);
    }
    for (i = 16; i < 64; i++)
        w[i] = SIG1(w[i-2]) + w[i-7] + SIG0(w[i-15]) + w[i-16];

    a = ctx->state[0]; b = ctx->state[1];
    c = ctx->state[2]; d = ctx->state[3];
    e = ctx->state[4]; f = ctx->state[5];
    g = ctx->state[6]; h = ctx->state[7];

    for (i = 0; i < 64; i++) {
        t1 = h + EP1(e) + CH(e,f,g) + sha256_k[i] + w[i];
        t2 = EP0(a) + MAJ(a,b,c);
        h = g; g = f; f = e; e = d + t1;
        d = c; c = b; b = a; a = t1 + t2;
    }

    ctx->state[0] += a; ctx->state[1] += b;
    ctx->state[2] += c; ctx->state[3] += d;
    ctx->state[4] += e; ctx->state[5] += f;
    ctx->state[6] += g; ctx->state[7] += h;
}

static void sha256_init(SHA256_CTX *ctx)
{
    ctx->state[0] = 0x6a09e667UL; ctx->state[1] = 0xbb67ae85UL;
    ctx->state[2] = 0x3c6ef372UL; ctx->state[3] = 0xa54ff53aUL;
    ctx->state[4] = 0x510e527fUL; ctx->state[5] = 0x9b05688cUL;
    ctx->state[6] = 0x1f83d9abUL; ctx->state[7] = 0x5be0cd19UL;
    ctx->count_lo = 0;
    ctx->count_hi = 0;
    ctx->buflen   = 0;
}

static void sha256_update(SHA256_CTX *ctx, const sha256_u8 *data, unsigned int len)
{
    sha256_u32 old_lo;
    unsigned int fill, left;

    if (len == 0) return;

    old_lo = ctx->count_lo;
    ctx->count_lo += (sha256_u32)len << 3;
    if (ctx->count_lo < old_lo) ctx->count_hi++;
    ctx->count_hi += (sha256_u32)len >> 29;

    left = ctx->buflen;
    fill = 64 - left;

    if (left && len >= fill) {
        memcpy(ctx->buf + left, data, fill);
        sha256_transform(ctx, ctx->buf);
        data += fill; len -= fill; left = 0;
    }
    while (len >= 64) {
        sha256_transform(ctx, data);
        data += 64; len -= 64;
    }
    if (len > 0) memcpy(ctx->buf + left, data, len);
    ctx->buflen = left + len;
}

static void sha256_final(SHA256_CTX *ctx, sha256_u8 digest[32])
{
    sha256_u8 pad[64];
    sha256_u8 msglen[8];
    sha256_u32 hi, lo;
    unsigned int last, padn;
    int i;

    hi = ctx->count_hi;
    lo = ctx->count_lo;

    msglen[0] = (sha256_u8)(hi >> 24); msglen[1] = (sha256_u8)(hi >> 16);
    msglen[2] = (sha256_u8)(hi >>  8); msglen[3] = (sha256_u8)(hi      );
    msglen[4] = (sha256_u8)(lo >> 24); msglen[5] = (sha256_u8)(lo >> 16);
    msglen[6] = (sha256_u8)(lo >>  8); msglen[7] = (sha256_u8)(lo      );

    last = ctx->buflen;
    padn = (last < 56) ? (56 - last) : (120 - last);

    memset(pad, 0, sizeof(pad));
    pad[0] = 0x80;
    sha256_update(ctx, pad, padn);
    sha256_update(ctx, msglen, 8);

    for (i = 0; i < 8; i++) {
        digest[i*4  ] = (sha256_u8)(ctx->state[i] >> 24);
        digest[i*4+1] = (sha256_u8)(ctx->state[i] >> 16);
        digest[i*4+2] = (sha256_u8)(ctx->state[i] >>  8);
        digest[i*4+3] = (sha256_u8)(ctx->state[i]      );
    }
}

/* Convenience: hash bytes → lowercase hex string (buf must be >= 65 bytes) */
static void sha256_hex(const sha256_u8 *data, unsigned int len, char *out)
{
    SHA256_CTX ctx;
    sha256_u8 digest[32];
    int i;
    const char *hex = "0123456789abcdef";

    sha256_init(&ctx);
    sha256_update(&ctx, (const sha256_u8 *)data, len);
    sha256_final(&ctx, digest);

    for (i = 0; i < 32; i++) {
        out[i*2  ] = hex[(digest[i] >> 4) & 0xf];
        out[i*2+1] = hex[ digest[i]       & 0xf];
    }
    out[64] = '\0';
}

#endif /* SHA256_H */
