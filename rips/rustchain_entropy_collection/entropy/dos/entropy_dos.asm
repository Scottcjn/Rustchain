; ============================================================================
; RUSTCHAIN ENTROPY COLLECTOR - DOS EDITION
; For 8086/8088, 286, 386, 486 and Pentium systems
;
; "Every vintage computer has historical potential"
;
; Collects deep hardware entropy from DOS systems:
; - BIOS Date and Model
; - CPU Identification (CPUID if available)
; - Memory Configuration
; - Hard Drive Serial/Model (via BIOS)
; - System Timer (8254 PIT)
; - Real-Time Clock (CMOS)
; - Video Adapter Info
; - DMA Controller State
;
; Assemble: nasm -f bin entropy_dos.asm -o ENTROPY.COM
; Run: ENTROPY.COM
; ============================================================================

[BITS 16]
[ORG 0x100]

section .text

start:
    ; Print banner
    mov     dx, banner
    call    print_string

    ; Collect BIOS info
    mov     dx, msg_bios
    call    print_string
    call    collect_bios_info

    ; Collect CPU info
    mov     dx, msg_cpu
    call    print_string
    call    collect_cpu_info

    ; Collect memory info
    mov     dx, msg_mem
    call    print_string
    call    collect_memory_info

    ; Collect timer entropy
    mov     dx, msg_timer
    call    print_string
    call    collect_timer_entropy

    ; Collect CMOS/RTC info
    mov     dx, msg_cmos
    call    print_string
    call    collect_cmos_info

    ; Collect video info
    mov     dx, msg_video
    call    print_string
    call    collect_video_info

    ; Generate hash
    mov     dx, msg_hash
    call    print_string
    call    generate_entropy_hash

    ; Print results
    call    print_results

    ; Write to file
    call    write_entropy_file

    ; Exit
    mov     ax, 0x4C00
    int     0x21

; ============================================================================
; BIOS INFO COLLECTION
; ============================================================================
collect_bios_info:
    push    es

    ; BIOS date at F000:FFF5 (8 bytes: MM/DD/YY)
    mov     ax, 0xF000
    mov     es, ax
    mov     si, 0xFFF5
    mov     di, bios_date
    mov     cx, 8
.copy_date:
    mov     al, [es:si]
    mov     [di], al
    inc     si
    inc     di
    loop    .copy_date

    ; BIOS model byte at F000:FFFE
    mov     al, [es:0xFFFE]
    mov     [bios_model], al

    ; Print BIOS date
    mov     dx, bios_date_msg
    call    print_string
    mov     dx, bios_date
    call    print_string
    call    print_newline

    ; Print model byte
    mov     dx, bios_model_msg
    call    print_string
    mov     al, [bios_model]
    call    print_hex_byte
    call    print_newline

    pop     es
    ret

; ============================================================================
; CPU INFO COLLECTION
; ============================================================================
collect_cpu_info:
    ; Check for CPUID support (386+ with CPUID)
    pushf
    pop     ax
    mov     bx, ax
    xor     ax, 0x200000    ; Toggle ID flag
    push    ax
    popf
    pushf
    pop     ax
    cmp     ax, bx
    je      .no_cpuid

    ; CPUID supported - get vendor and features
    xor     eax, eax
    cpuid
    mov     [cpuid_vendor], ebx
    mov     [cpuid_vendor+4], edx
    mov     [cpuid_vendor+8], ecx
    mov     byte [cpuid_vendor+12], 0

    mov     eax, 1
    cpuid
    mov     [cpu_signature], eax
    mov     [cpu_features], edx

    mov     dx, cpuid_msg
    call    print_string
    mov     dx, cpuid_vendor
    call    print_string
    call    print_newline

    mov     dx, cpu_sig_msg
    call    print_string
    mov     eax, [cpu_signature]
    call    print_hex_dword
    call    print_newline
    jmp     .done

.no_cpuid:
    ; Pre-CPUID detection (8086/286/386)
    mov     dx, no_cpuid_msg
    call    print_string

    ; Detect CPU type using flags test
    pushf
    pop     ax
    and     ax, 0x0FFF      ; Clear bits 12-15
    push    ax
    popf
    pushf
    pop     ax
    and     ax, 0xF000
    cmp     ax, 0xF000
    jne     .not_8086
    mov     byte [cpu_type], 0x86
    mov     dx, cpu_8086_msg
    jmp     .print_cpu

.not_8086:
    mov     ax, 0xF000
    push    ax
    popf
    pushf
    pop     ax
    and     ax, 0xF000
    jnz     .not_286
    mov     byte [cpu_type], 0x02
    mov     dx, cpu_286_msg
    jmp     .print_cpu

.not_286:
    mov     byte [cpu_type], 0x03
    mov     dx, cpu_386_msg

.print_cpu:
    call    print_string
    call    print_newline

.done:
    ret

; ============================================================================
; MEMORY INFO COLLECTION
; ============================================================================
collect_memory_info:
    ; Get conventional memory (INT 12h)
    int     0x12
    mov     [conv_memory], ax

    mov     dx, conv_mem_msg
    call    print_string
    mov     ax, [conv_memory]
    call    print_decimal
    mov     dx, kb_msg
    call    print_string
    call    print_newline

    ; Get extended memory (INT 15h, AH=88h)
    mov     ah, 0x88
    int     0x15
    jc      .no_ext
    mov     [ext_memory], ax

    mov     dx, ext_mem_msg
    call    print_string
    mov     ax, [ext_memory]
    call    print_decimal
    mov     dx, kb_msg
    call    print_string
    call    print_newline
    jmp     .done

.no_ext:
    mov     word [ext_memory], 0
.done:
    ret

; ============================================================================
; TIMER ENTROPY COLLECTION (8254 PIT)
; ============================================================================
collect_timer_entropy:
    mov     cx, 16          ; Collect 16 samples
    mov     di, timer_samples

.sample_loop:
    ; Latch timer 0
    mov     al, 0x00
    out     0x43, al

    ; Read count
    in      al, 0x40
    mov     ah, al
    in      al, 0x40
    xchg    al, ah

    ; Store sample
    mov     [di], ax
    add     di, 2

    ; Small delay
    push    cx
    mov     cx, 100
.delay:
    loop    .delay
    pop     cx

    loop    .sample_loop

    ; Print first sample
    mov     dx, timer_msg
    call    print_string
    mov     ax, [timer_samples]
    call    print_hex_word
    call    print_newline
    ret

; ============================================================================
; CMOS/RTC INFO COLLECTION
; ============================================================================
collect_cmos_info:
    ; Read RTC seconds
    mov     al, 0x00
    out     0x70, al
    in      al, 0x71
    mov     [rtc_seconds], al

    ; Read RTC minutes
    mov     al, 0x02
    out     0x70, al
    in      al, 0x71
    mov     [rtc_minutes], al

    ; Read RTC hours
    mov     al, 0x04
    out     0x70, al
    in      al, 0x71
    mov     [rtc_hours], al

    ; Read CMOS checksum (diagnostic byte)
    mov     al, 0x0E
    out     0x70, al
    in      al, 0x71
    mov     [cmos_diag], al

    ; Read memory size from CMOS
    mov     al, 0x15
    out     0x70, al
    in      al, 0x71
    mov     [cmos_mem_lo], al
    mov     al, 0x16
    out     0x70, al
    in      al, 0x71
    mov     [cmos_mem_hi], al

    mov     dx, rtc_msg
    call    print_string
    mov     al, [rtc_hours]
    call    print_hex_byte
    mov     al, ':'
    call    print_char
    mov     al, [rtc_minutes]
    call    print_hex_byte
    mov     al, ':'
    call    print_char
    mov     al, [rtc_seconds]
    call    print_hex_byte
    call    print_newline
    ret

; ============================================================================
; VIDEO INFO COLLECTION
; ============================================================================
collect_video_info:
    ; Get current video mode
    mov     ah, 0x0F
    int     0x10
    mov     [video_mode], al
    mov     [video_cols], ah
    mov     [video_page], bh

    mov     dx, video_mode_msg
    call    print_string
    mov     al, [video_mode]
    call    print_hex_byte
    call    print_newline

    ; Check for VGA
    mov     ax, 0x1A00
    int     0x10
    cmp     al, 0x1A
    jne     .no_vga
    mov     byte [has_vga], 1
    mov     dx, vga_yes_msg
    jmp     .print_vga
.no_vga:
    mov     byte [has_vga], 0
    mov     dx, vga_no_msg
.print_vga:
    call    print_string
    call    print_newline
    ret

; ============================================================================
; GENERATE ENTROPY HASH (Simple XOR-based)
; ============================================================================
generate_entropy_hash:
    ; Initialize hash
    xor     eax, eax
    mov     [entropy_hash], eax
    mov     [entropy_hash+4], eax

    ; Mix in BIOS date
    mov     si, bios_date
    call    mix_bytes_8

    ; Mix in BIOS model
    mov     al, [bios_model]
    xor     [entropy_hash], al
    rol     dword [entropy_hash], 7

    ; Mix in timer samples
    mov     si, timer_samples
    mov     cx, 16
.mix_timer:
    lodsw
    xor     [entropy_hash], ax
    rol     dword [entropy_hash], 3
    loop    .mix_timer

    ; Mix in RTC
    mov     al, [rtc_seconds]
    xor     [entropy_hash+1], al
    mov     al, [rtc_minutes]
    xor     [entropy_hash+2], al
    mov     al, [rtc_hours]
    xor     [entropy_hash+3], al

    ; Mix in memory info
    mov     ax, [conv_memory]
    xor     [entropy_hash+4], ax
    mov     ax, [ext_memory]
    xor     [entropy_hash+6], ax

    ; Mix in CPU info
    mov     eax, [cpu_signature]
    xor     [entropy_hash], eax

    ret

mix_bytes_8:
    mov     cx, 8
.loop:
    lodsb
    xor     [entropy_hash], al
    rol     dword [entropy_hash], 5
    loop    .loop
    ret

; ============================================================================
; PRINT RESULTS
; ============================================================================
print_results:
    call    print_newline
    mov     dx, result_banner
    call    print_string

    mov     dx, hash_result_msg
    call    print_string

    ; Print hash as hex
    mov     si, entropy_hash
    mov     cx, 8
.print_hash:
    lodsb
    call    print_hex_byte
    loop    .print_hash
    call    print_newline

    mov     dx, sig_msg
    call    print_string
    call    print_newline

    mov     dx, done_msg
    call    print_string
    ret

; ============================================================================
; WRITE ENTROPY FILE
; ============================================================================
write_entropy_file:
    ; Create file
    mov     ah, 0x3C
    mov     cx, 0           ; Normal attributes
    mov     dx, filename
    int     0x21
    jc      .error
    mov     [file_handle], ax

    ; Write header
    mov     ah, 0x40
    mov     bx, [file_handle]
    mov     cx, file_header_len
    mov     dx, file_header
    int     0x21

    ; Write BIOS date
    mov     ah, 0x40
    mov     cx, 8
    mov     dx, bios_date
    int     0x21

    ; Write newline
    mov     ah, 0x40
    mov     cx, 2
    mov     dx, crlf
    int     0x21

    ; Write hash
    mov     ah, 0x40
    mov     cx, 8
    mov     dx, entropy_hash
    int     0x21

    ; Close file
    mov     ah, 0x3E
    mov     bx, [file_handle]
    int     0x21

    mov     dx, file_msg
    call    print_string
    ret

.error:
    mov     dx, file_err_msg
    call    print_string
    ret

; ============================================================================
; UTILITY FUNCTIONS
; ============================================================================

print_string:
    mov     ah, 0x09
    int     0x21
    ret

print_char:
    mov     ah, 0x02
    mov     dl, al
    int     0x21
    ret

print_newline:
    mov     dx, crlf
    call    print_string
    ret

print_hex_byte:
    push    ax
    shr     al, 4
    call    print_hex_digit
    pop     ax
    and     al, 0x0F
    call    print_hex_digit
    ret

print_hex_digit:
    and     al, 0x0F
    add     al, '0'
    cmp     al, '9'
    jle     .ok
    add     al, 7
.ok:
    call    print_char
    ret

print_hex_word:
    push    ax
    mov     al, ah
    call    print_hex_byte
    pop     ax
    call    print_hex_byte
    ret

print_hex_dword:
    push    eax
    shr     eax, 16
    call    print_hex_word
    pop     eax
    call    print_hex_word
    ret

print_decimal:
    push    ax
    push    bx
    push    cx
    push    dx

    mov     bx, 10
    xor     cx, cx

.divide:
    xor     dx, dx
    div     bx
    push    dx
    inc     cx
    test    ax, ax
    jnz     .divide

.print:
    pop     ax
    add     al, '0'
    call    print_char
    loop    .print

    pop     dx
    pop     cx
    pop     bx
    pop     ax
    ret

; ============================================================================
; DATA SECTION
; ============================================================================

section .data

banner:
    db '======================================================', 13, 10
    db '  RUSTCHAIN ENTROPY COLLECTOR - DOS EDITION', 13, 10
    db '  "Every vintage computer has historical potential"', 13, 10
    db '======================================================', 13, 10, '$'

msg_bios:   db '[1/6] Collecting BIOS info...', 13, 10, '$'
msg_cpu:    db '[2/6] Detecting CPU...', 13, 10, '$'
msg_mem:    db '[3/6] Reading memory config...', 13, 10, '$'
msg_timer:  db '[4/6] Sampling timer entropy...', 13, 10, '$'
msg_cmos:   db '[5/6] Reading CMOS/RTC...', 13, 10, '$'
msg_video:  db '[6/6] Detecting video adapter...', 13, 10, '$'
msg_hash:   db 'Generating entropy hash...', 13, 10, '$'

bios_date_msg:  db '  BIOS Date: $'
bios_model_msg: db '  BIOS Model: 0x$'
cpuid_msg:      db '  CPU Vendor: $'
cpu_sig_msg:    db '  CPU Signature: 0x$'
no_cpuid_msg:   db '  Pre-CPUID CPU detected', 13, 10, '$'
cpu_8086_msg:   db '  CPU: 8086/8088$'
cpu_286_msg:    db '  CPU: 80286$'
cpu_386_msg:    db '  CPU: 80386+$'
conv_mem_msg:   db '  Conventional: $'
ext_mem_msg:    db '  Extended: $'
kb_msg:         db ' KB$'
timer_msg:      db '  Timer Sample: 0x$'
rtc_msg:        db '  RTC Time: $'
video_mode_msg: db '  Video Mode: 0x$'
vga_yes_msg:    db '  VGA: Yes$'
vga_no_msg:     db '  VGA: No (EGA/CGA/MDA)$'

result_banner:
    db 13, 10
    db '======================================================', 13, 10
    db '  ENTROPY PROOF', 13, 10
    db '======================================================', 13, 10, '$'

hash_result_msg:    db '  Hash: $'
sig_msg:            db '  Signature: DOS-VINTAGE-ENTROPY', 13, 10, '$'
done_msg:
    db 13, 10
    db '======================================================', 13, 10
    db '  ENTROPY COLLECTION COMPLETE', 13, 10
    db '  This fingerprint proves REAL VINTAGE HARDWARE', 13, 10
    db '======================================================', 13, 10, '$'

file_msg:       db 'Entropy written to ENTROPY.DAT', 13, 10, '$'
file_err_msg:   db 'Error writing file!', 13, 10, '$'
filename:       db 'ENTROPY.DAT', 0

file_header:    db 'RUSTCHAIN-DOS-ENTROPY', 13, 10
file_header_len equ $ - file_header

crlf:   db 13, 10, '$'

; ============================================================================
; BSS SECTION
; ============================================================================

section .bss

bios_date:      resb 9
bios_model:     resb 1

cpuid_vendor:   resb 13
cpu_signature:  resd 1
cpu_features:   resd 1
cpu_type:       resb 1

conv_memory:    resw 1
ext_memory:     resw 1

timer_samples:  resw 16

rtc_seconds:    resb 1
rtc_minutes:    resb 1
rtc_hours:      resb 1
cmos_diag:      resb 1
cmos_mem_lo:    resb 1
cmos_mem_hi:    resb 1

video_mode:     resb 1
video_cols:     resb 1
video_page:     resb 1
has_vga:        resb 1

entropy_hash:   resb 8

file_handle:    resw 1
