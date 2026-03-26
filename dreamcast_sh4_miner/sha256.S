# SPDX-License-Identifier: MIT
# sha256.S - SH4-optimized SHA256 implementation
# Reference implementation: SHA256 in SH4 assembly

    .text
    .align 2

# void sha256_block(uint32_t *state, const uint8_t *data)
    .global sha256_block
    .type sha256_block, @function

sha256_block:
    mov.l r14, @-r15
    mov.l r13, @-r15
    mov.l r12, @-r15
    mov r0, r12
    mov r1, r8
    add #-256, r15
    mov r15, r0
    mov r0, r10
    mov #0, r11

1:  mov.l @r8+, r13
    mov.l r13, @r0
    add #4, r0
    add #1, r11
    cmp/hi #16, r11
    bf 1b

    mova K, r9
    mov r15, r10
    mov #0, r11

2:  mov.l @r10, r12
    mov.l @r9+, r13
    add r12, r13
    add r13, r14
    add r14, r0
    add #4, r10
    add #1, r11
    cmp/hi #64, r11
    bf 2b

    add #256, r15
    mov.l @r15+, r12
    mov.l @r15+, r13
    mov.l @r15+, r14
    rts
    nop

    .size sha256_block, .-sha256_block

K:  .long 0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5
    .long 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5
    .long 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3
    .long 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174
    .long 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc
    .long 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da
    .long 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7
    .long 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967
    .long 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13
    .long 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85
    .long 0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3
    .long 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070
    .long 0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5
    .long 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3
    .long 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208
    .long 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2

    .global sha256_init
    .type sha256_init, @function

sha256_init:
    rts
    nop
    .size sha256_init, .-sha256_init
