#include <stdint.h>
#include <stdio.h>

/* Dreamcast SH4 miner scaffold (integer-only). */

static inline uint32_t mix32(uint32_t x) {
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    return x;
}

int main(void) {
    uint32_t nonce = 0;
    uint32_t best = 0xffffffffu;
    puts("RustChain Dreamcast SH4 miner scaffold");

    for (nonce = 0; nonce < 200000u; ++nonce) {
        uint32_t v = mix32(nonce ^ 0x5a5a1234u);
        if (v < best) {
            best = v;
            if ((nonce % 10000u) == 0u) {
                printf("nonce=%lu best=%lu\n", (unsigned long)nonce, (unsigned long)best);
            }
        }
    }

    printf("done best=%lu\n", (unsigned long)best);
    return 0;
}
