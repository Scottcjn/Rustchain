; amiga_fingerprint.asm
; Devpac assembler - Detect emulator traits on real Amiga 500
; Dumps ROM checksum and AttnFlags to serial or file

        SECTION code,CODE
        XDEF _start
        INCLUDE "exec/exec_lib.i"

_start:
        lea     message1,a1
        bsr     print_string

        ; --- Read ExecBase ---
        movea.l 4,a6
        move.l  a6,d0
        lea     exec_base_msg,a1
        bsr     print_string
        move.l  d0,d1
        bsr     print_hex

        ; --- Read AttnFlags ---
        move.l  34(a6),d2
        lea     attn_msg,a1
        bsr     print_string
        move.l  d2,d1
        bsr     print_hex

        ; --- ROM Checksum ---
        lea     romstart,a0
        move.l  #512*1024,d5
        clr.l   d3
.sumloop:
        move.b  (a0)+,d4
        and.l   #$FF,d4
        add.l   d4,d3
        subq.l  #1,d5
        bne     .sumloop

        lea     rom_msg,a1
        bsr     print_string
        move.l  d3,d1
        bsr     print_hex

        lea     done_msg,a1
        bsr     print_string

        rts

; --- Utilities: Print string and hex ---
print_string:
        move.b  (a1)+,d0
        beq     .done
        move.b  d0,$dff180
        bra     print_string
.done:
        rts

print_hex:
        moveq   #8-1,d7
.next:
        rol.l   #4,d1
        move.l  d1,d6
        and.l   #15,d6
        cmp.l   #10,d6
        blt     .digit
        add.l   #55,d6
        bra     .out
.digit:
        add.l   #48,d6
.out:
        move.b  d6,$dff180
        dbra    d7,.next
        rts

; --- Data Section ---
        SECTION data,DATA
message1:        dc.b "RustChain Amiga PoA Check",10,0
exec_base_msg:   dc.b "ExecBase: ",0
attn_msg:        dc.b 10,"AttnFlags: ",0
rom_msg:         dc.b 10,"ROM Checksum: ",0
done_msg:        dc.b 10,"Done.",10,0

romstart:        dc.l $F80000
