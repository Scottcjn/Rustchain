#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#ifndef ITERS
#define ITERS 2000000UL
#endif

static inline uint64_t nsec_now(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}

static void scalar_perm(const uint8_t *a, const uint8_t *b, const uint8_t *mask, uint8_t *out) {
    for (int i = 0; i < 16; i++) {
        uint8_t m = mask[i] & 0x1f;
        out[i] = (m < 16) ? a[m] : b[m - 16];
    }
}

#if defined(__ALTIVEC__)
#include <altivec.h>
typedef __vector unsigned char v16u8;

static inline void vecperm_once(const uint8_t *a, const uint8_t *b, const uint8_t *mask, uint8_t *out) {
    v16u8 va = vec_vsx_ld(0, a);
    v16u8 vb = vec_vsx_ld(0, b);
    v16u8 vm = vec_vsx_ld(0, mask);
    v16u8 vo = vec_perm(va, vb, vm);
    vec_vsx_st(vo, 0, out);
}
#endif

int main(int argc, char **argv) {
    unsigned long iters = ITERS;
    if (argc > 1) iters = strtoul(argv[1], NULL, 10);

    uint8_t a[16], b[16], mask[16], out[16];
    for (int i = 0; i < 16; i++) {
        a[i] = (uint8_t)i;
        b[i] = (uint8_t)(i + 16);
        mask[i] = (uint8_t)((i * 7) & 0x1f);
    }

    uint64_t t0 = nsec_now();
    for (unsigned long i = 0; i < iters; i++) {
        scalar_perm(a, b, mask, out);
        mask[i & 15] ^= (uint8_t)(out[(i + 3) & 15] & 1);
    }
    uint64_t t1 = nsec_now();

#if defined(__ALTIVEC__)
    uint64_t t2 = nsec_now();
    for (unsigned long i = 0; i < iters; i++) {
        vecperm_once(a, b, mask, out);
        mask[i & 15] ^= (uint8_t)(out[(i + 3) & 15] & 1);
    }
    uint64_t t3 = nsec_now();
#else
    uint64_t t2 = 0, t3 = 0;
#endif

    double scalar_ns = (double)(t1 - t0) / (double)iters;
#if defined(__ALTIVEC__)
    double vec_ns = (double)(t3 - t2) / (double)iters;
    double speedup = (vec_ns > 0.0) ? (scalar_ns / vec_ns) : 0.0;
#else
    double vec_ns = -1.0;
    double speedup = 0.0;
#endif

    printf("{\"iters\":%lu,\"scalar_ns\":%.4f,\"vecperm_ns\":%.4f,\"speedup\":%.4f,\"altivec\":%s}\n",
           iters, scalar_ns, vec_ns, speedup,
#if defined(__ALTIVEC__)
           "true"
#else
           "false"
#endif
    );
    return 0;
}
