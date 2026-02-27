#include <stdint.h>
#include <stdio.h>

/*
 * Apple II / 6502-oriented miner scaffold.
 * Integer-only loop; no dynamic allocation.
 */

#define NONCE_START 0u
#define NONCE_LIMIT 10000u

static uint32_t simple_mix(uint32_t n) {
    n ^= (n << 7);
    n ^= (n >> 9);
    n ^= (n << 8);
    return n;
}

int main(void) {
    uint32_t nonce;
    uint32_t best = 0xffffffffu;

    puts("RustChain Apple II miner scaffold starting...");

    for (nonce = NONCE_START; nonce < NONCE_LIMIT; nonce++) {
        uint32_t score = simple_mix(nonce);
        if (score < best) {
            best = score;
            if ((nonce % 500u) == 0u) {
                printf("progress nonce=%lu best=%lu\n", (unsigned long)nonce, (unsigned long)best);
            }
        }
    }

    printf("done best=%lu\n", (unsigned long)best);
    return 0;
}
