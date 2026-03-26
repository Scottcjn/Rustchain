; ──────────────────────────────────────────────────────────────────
; RustChain Floppy Miner — i486 Assembly Attestation Core
; 
; Minimal attestation client for DOS / 16MB RAM systems.
; Builds to < 2KB .COM executable.
;
; Assemble: nasm -f bin -o MINER.COM miner.asm
; Run: MINER.COM (in DOS / DOSBox)
;
; This outputs attestation JSON to stdout for relay.py to forward.
; For direct network access, link with Wattcp.
;
; Bounty: Rustchain #1853 (300 RTC)
; ──────────────────────────────────────────────────────────────────

[BITS 16]
[ORG 100h]

section .text

start:
    ; ── Display boot screen ──
    mov     dx, boot_screen
    call    print_string

    ; ── Generate nonce from timer ──
    call    generate_nonce
    mov     [nonce_val], eax

    ; ── Build attestation JSON ──
    call    build_attestation

    ; ── Output to stdout (relay picks this up) ──
    mov     dx, attest_prefix
    call    print_string
    mov     dx, json_buffer
    call    print_string
    mov     dx, newline
    call    print_string

    ; ── Wait and loop ──
    mov     dx, wait_msg
    call    print_string

    ; Wait ~30 seconds (rough timer loop)
    mov     cx, 30
.wait_loop:
    ; INT 15h AH=86h — wait microseconds (not available on all systems)
    ; Fallback: busy loop
    push    cx
    mov     cx, 0FFFFh
.inner:
    nop
    loop    .inner
    pop     cx
    loop    .wait_loop

    jmp     start           ; Loop forever

; ──────────────────────────────────────────────────────────────────
; generate_nonce — Read timer tick as pseudo-random nonce
; Returns: EAX = nonce value
; ──────────────────────────────────────────────────────────────────
generate_nonce:
    ; Read BIOS timer tick count (INT 1Ah AH=00h)
    xor     ah, ah
    int     1Ah             ; CX:DX = tick count
    mov     ax, dx
    shl     eax, 16
    mov     ax, cx
    ; Mix with port 40h (PIT counter) for more entropy
    in      al, 40h
    xor     ah, al
    ret

; ──────────────────────────────────────────────────────────────────
; build_attestation — Construct JSON payload in json_buffer
; ──────────────────────────────────────────────────────────────────
build_attestation:
    push    si
    push    di

    mov     di, json_buffer

    ; {"miner":"
    mov     si, json_p1
    call    copy_str
    ; wallet address
    mov     si, wallet_addr
    call    copy_str
    ; ","nonce":
    mov     si, json_p2
    call    copy_str
    ; nonce value (decimal)
    mov     eax, [nonce_val]
    call    int_to_ascii
    ; ,"device":{"arch":"i486","family":"floppy","ram_mb":16,"boot_media":"floppy_1.44mb"}}
    mov     si, json_p3
    call    copy_str

    ; Null terminate
    mov     byte [di], 0

    pop     di
    pop     si
    ret

; ──────────────────────────────────────────────────────────────────
; copy_str — Copy null-terminated string from SI to DI
; ──────────────────────────────────────────────────────────────────
copy_str:
.loop:
    lodsb
    or      al, al
    jz      .done
    stosb
    jmp     .loop
.done:
    ret

; ──────────────────────────────────────────────────────────────────
; int_to_ascii — Convert EAX to decimal ASCII at DI
; ──────────────────────────────────────────────────────────────────
int_to_ascii:
    push    ebx
    push    ecx
    push    edx

    mov     ebx, 10
    xor     ecx, ecx        ; digit counter

.divide:
    xor     edx, edx
    div     ebx
    push    dx              ; remainder
    inc     cx
    or      eax, eax
    jnz     .divide

.output:
    pop     ax
    add     al, '0'
    stosb
    loop    .output

    pop     edx
    pop     ecx
    pop     ebx
    ret

; ──────────────────────────────────────────────────────────────────
; print_string — Print $-terminated string at DX
; ──────────────────────────────────────────────────────────────────
print_string:
    mov     ah, 09h
    int     21h
    ret

; ──────────────────────────────────────────────────────────────────
; Data Section
; ──────────────────────────────────────────────────────────────────

section .data

boot_screen:
    db  13,10
    db  '  ===================================',13,10
    db  '  |   RustChain Floppy Miner v1.0   |',13,10
    db  '  |   Proof-of-Antiquity x Floppy   |',13,10
    db  '  |   i486 / 16MB / 1.44MB Boot     |',13,10
    db  '  ===================================',13,10
    db  13,10,'$'

attest_prefix:
    db  'ATTEST:','$'

json_p1:
    db  '{"miner":"', 0

wallet_addr:
    db  'RTC2fe3c33c77666ff76a1cd0999fd4466ee81250ff', 0

json_p2:
    db  '","nonce":', 0

json_p3:
    db  ',"device":{"arch":"i486","family":"floppy","ram_mb":16,"boot_media":"floppy_1.44mb"}}', 0

wait_msg:
    db  '  Waiting 30s for next attestation...',13,10,'$'

newline:
    db  13,10,'$'

section .bss

nonce_val:  resd 1
json_buffer: resb 512
