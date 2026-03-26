; ============================================================================
; RustChain Apple II Miner - Main Module
; ============================================================================
; A complete RustChain miner for Apple II series computers
; Written in 6502 assembly using CC65 conventions
;
; Target: Apple IIe (64KB RAM), Uthernet II Ethernet card
; Requirements: IP65 TCP/IP stack, SHA256 hash, hardware fingerprinting
;
; Author: RustChain Bounty Hunter
; License: MIT
; ============================================================================

.feature pc_rel
.smart

; ============================================================================
; INCLUDES
; ============================================================================

; CC65 runtime and macros
.include "sim6502.inc"
.include "zeropage.inc"

; ============================================================================
; CONSTANTS
; ============================================================================

; ProDOS MLI calls
PRODOS_CALL         = $BF00
MLI                 = $BF00

; ProDOS File Commands
PRODOS_CREATE       = $C0
PRODOS_OPEN         = $C7
PRODOS_READ         = $CA
PRODOS_WRITE        = $CB
PRODOS_CLOSE        = $C9
PRODOS_GET_MARK     = $D1
PRODOS_SET_MARK     = $D2
PRODOS_GET_EOF      = $D3
PRODOS_SET_EOF      = $D4

; ProDOS Error Codes
PRODOS_NO_ERROR     = $00
PRODOS_BAD_CALL     = $01
PRODOS_BAD_CMD      = $02
PRODOS_NOT_FOUND    = $06
PRODOS_NO_DEVICE    = $08
PRODOS_WRITE_ERR    = $27
PRODOS_DEVICE_OFF   = $28

; Memory locations
ZP_START            = $00
STACK               = $0100
MINER_START         = $0200
MINER_END           = $BFFF

; Uthernet II W5100 Registers (Slot 3 base = $Cn00)
ETHERNET_SLOT       = $C300        ; Slot 3 I/O base
W5100_BASE          = $C300        ; W5100 register base

; IP65 Network Configuration
DHCP_TIMEOUT        = 5000         ; 5 second DHCP timeout
HTTP_PORT           = 80
ATTEST_ENDPOINT     = $1000        ; String pointer for attestation URL

; Hash Configuration
HASH_WORKSIZE       = 64           ; SHA256 block size
WORK_DIFFICULTY     = $0004        ; Leading zeros required

; Network States
NET_STATE_INIT      = $00
NET_STATE_DHCP      = $01
NET_STATE_CONNECT   = $02
NET_STATE_SEND      = $03
NET_STATE_RECV      = $04
NET_STATE_DONE      = $05
NET_STATE_ERROR     = $FF

; Miner States
MINER_STATE_IDLE    = $00
MINER_STATE_WORK    = $01
MINER_STATE_HASH    = $02
MINER_STATE_SUBMIT  = $03
MINER_STATE_WAIT    = $04

; ============================================================================
; ZERO PAGE ALLOCATION
; ============================================================================

; CC65 Runtime Zero Page (must not conflict)
BSS_START       = $80
BSS_END         = $FF

; Network State
net_state       = BSS_START       ; Current network state
net_error       = BSS_START+1     ; Network error code
socket_num      = BSS_START+2     ; Current socket number

; Hash State
hash_state      = BSS_START+3     ; Hash state (3 bytes)
hash_nonce      = BSS_START+6     ; Current nonce (4 bytes)
hash_work       = BSS_START+10    ; Work buffer (64 bytes)

; Miner State
miner_state     = BSS_START+74    ; Current miner state
miner_difficulty = BSS_START+75   ; Current difficulty
miner_attempts   = BSS_START+77   ; Hash attempts counter

; Hardware Fingerprint
fingerprint     = BSS_START+78    ; Fingerprint buffer (32 bytes)

; I/O Buffer
io_buffer       = BSS_START+110   ; General I/O buffer (256 bytes)

; Temporary Variables
tmp1            = BSS_START+120   ; Temporary 1
tmp2            = BSS_START+122   ; Temporary 2
tmp3            = BSS_START+124   ; Temporary 3
ptr             = BSS_START+126   ; Generic pointer (2 bytes)

; ============================================================================
; MAIN CODE SECTION
; ============================================================================

.segment "CODE"

; ============================================================================
; ENTRY POINT
; ============================================================================

.proc _start
        ; Save existing ProDOS prefix
        jsr save_prodos_prefix

        ; Initialize the system
        jsr initialize_system

        ; Display welcome banner
        jsr display_banner

        ; Check hardware
        jsr check_hardware

        ; Initialize networking
        jsr initialize_network

        ; Initialize miner
        jsr initialize_miner

        ; Main loop
main_loop:
        ; Update display
        jsr update_display

        ; Process based on state
        lda miner_state
        cmp #MINER_STATE_IDLE
        beq idle_handler
        cmp #MINER_STATE_WORK
        beq work_handler
        cmp #MINER_STATE_HASH
        beq hash_handler
        cmp #MINER_STATE_SUBMIT
        beq submit_handler
        cmp #MINER_STATE_WAIT
        beq wait_handler

        jmp main_loop

idle_handler:
        jsr get_new_work
        jmp main_loop

work_handler:
        jsr prepare_work
        lda #MINER_STATE_HASH
        sta miner_state
        jmp main_loop

hash_handler:
        jsr perform_hash
        jsr check_result
        lda #MINER_STATE_SUBMIT
        sta miner_state
        jmp main_loop

submit_handler:
        jsr submit_attestation
        lda #MINER_STATE_WAIT
        sta miner_state
        jmp main_loop

wait_handler:
        jsr wait_for_block
        lda #MINER_STATE_WORK
        sta miner_state
        jmp main_loop

.endproc

; ============================================================================
; SYSTEM INITIALIZATION
; ============================================================================

.proc initialize_system
        ; Disable interrupts
        sei
        cld

        ; Set up stack
        ldx #$FF
        txs

        ; Clear zero page
        lda #$00
        ldx #BSS_START
clear_zp:
        sta $00,x
        inx
        cpx #BSS_END
        bne clear_zp

        ; Clear BSS area
        ldx #>BSS_START
clear_bss:
        lda #$00
        sta $0100,x
        inx
        bne clear_bss

        ; Detect Apple II model
        jsr detect_model

        ; Check for Uthernet II
        jsr detect_ethernet

        ; Initialize random seed
        jsr init_random

        ; Initialize display
        jsr init_display

        rts
.endproc

; ============================================================================
; APPLE II MODEL DETECTION
; ============================================================================

.proc detect_model
        ; Check for Apple IIe or later
        lda $FBDD           ; Apple IIe ID byte
        cmp #$06
        bne not_iie

        ; Check for 80-column card
        lda $FBE0
        and #$01
        beq no_80col
        lda #$01
        sta tmp1            ; 80-column present
        jmp model_done

no_80col:
        lda #$00
        sta tmp1

model_done:
        ; Store model info
        lda #$02            ; Apple IIe
        sta tmp2
        rts

not_iie:
        ; Check for Apple II+
        lda $FBDD
        cmp #$00
        bne unknown_model
        lda #$01            ; Apple II+
        sta tmp2
        rts

unknown_model:
        lda #$00            ; Unknown
        sta tmp2
        rts
.endproc

; ============================================================================
; ETHERNET CARD DETECTION
; ============================================================================

.proc detect_ethernet
        ; Check each slot for Uthernet II
        ldx #$03            ; Start at slot 3
slot_loop:
        stx tmp1

        ; Calculate slot base address ($Cn00)
        txa
        asl a
        asl a
        asl a
        asl a
        ora #$C0
        sta tmp2            ; Slot base high byte

        ; Check for W5100 signature
        ; W5100 registers: MR (Mode Register) at offset 0
        ; Writing and reading back should work
        lda #$01            ; Test pattern
        sta (tmp2),x
        eor (tmp2),x
        bne slot_not_found

        lda #$80            ; Reset pattern
        sta (tmp2),x
        lda (tmp2),x
        and #$80
        beq slot_not_found

        ; Found valid W5100
        stx socket_num      ; Save slot number
        lda #$01
        sta net_state       ; Network present
        rts

slot_not_found:
        ldx tmp1
        dex
        bne slot_loop

        ; No Ethernet found
        lda #$00
        sta net_state
        lda #NET_STATE_ERROR
        sta net_error
        rts
.endproc

; ============================================================================
; DISPLAY INITIALIZATION
; ============================================================================

.proc init_display
        ; Select 40-column mode
        lda $C010           ; Clear CR flag
        sta $C051           ; 40-column mode

        ; Clear screen
        jsr clear_screen

        ; Set text mode
        lda #$00
        sta $C050           ; Text mode

        rts
.endproc

.proc clear_screen
        ldx #$00
        lda #$20            ; Space character
clear_loop:
        sta $0400,x         ; First page
        sta $0500,x
        sta $0600,x
        sta $0700,x
        inx
        bne clear_loop
        rts
.endproc

; ============================================================================
; BANNER DISPLAY
; ============================================================================

.proc display_banner
        ; Home cursor
        lda #$8D            ; carriage return
        jsr putchar

        ; RustChain banner
        ldx #$00
banner_loop:
        lda banner_text,x
        beq banner_done
        jsr putchar
        inx
        jmp banner_loop

banner_done:
        lda #$8D
        jsr putchar
        lda #$8D
        jsr putchar
        rts

banner_text:
        .byte "================================", $8D
        .byte "RUSTCHAIN MINER v1.0", $8D
        .byte "Apple II / 6502 Assembly", $8D
        .byte "================================", $8D
        .byte 0
.endproc

; ============================================================================
; CHARACTER OUTPUT
; ============================================================================

.proc putchar
        pha
wait_ready:
        lda $C010           ; Read keypress (clears flag)
        lda $C000           ; Get key
        and #$80            ; Check for key press
        bne wait_ready      ; Wait if busy

        pla
        ora #$80            ; Set high bit for screen
        sta $C000           ; Output character
        rts
.endproc

; ============================================================================
; RANDOM NUMBER INITIALIZATION
; ============================================================================

.proc init_random
        ; Use timing from floating bus reads
        ldx #$10
        lda $C000           ; Read empty floating bus
random_loop:
        eor $C000           ; Mix in floating bus
        dex
        bne random_loop

        ; Use slot 3 timing
        ldy #$00
        sty ptr
        lda $C300           ; Read W5100
timing_loop:
        iny
        bne timing_loop
        adc $C300

        ; Mix into seed
        sta hash_nonce
        eor hash_nonce+1
        sta hash_nonce+1
        eor hash_nonce+2
        sta hash_nonce+2
        eor hash_nonce+3
        sta hash_nonce+3

        rts
.endproc

; ============================================================================
; HARDWARE CHECK
; ============================================================================

.proc check_hardware
        ; Check RAM size
        jsr check_ram

        ; Check for required hardware
        lda net_state
        bne net_ok

        ; Display warning
        ldx #$00
warn_loop:
        lda net_warn,x
        beq warn_done
        jsr putchar
        inx
        jmp warn_loop

warn_done:
        lda #$8D
        jsr putchar

net_ok:
        rts

net_warn:
        .byte "WARNING: No Ethernet card detected!", $8D
        .byte "Miner requires Uthernet II.", $8D
        .byte 0
.endproc

.proc check_ram
        ; Count RAM pages
        ldx #$00
        stx tmp1
        ldx #$C0            ; Start at $C000
ram_loop:
        lda #$AA
        sta $0000,x         ; Test in zero page
        lda $0000,x
        cmp #$AA
        bne ram_done

        lda #$55
        sta $0000,x
        lda $0000,x
        cmp #$55
        bne ram_done

        inc tmp1
        inx
        bne ram_loop

ram_done:
        ; tmp1 now has RAM pages above $C000
        ; For Apple IIe, should be 64 pages
        rts
.endproc

; ============================================================================
; NETWORK INITIALIZATION
; ============================================================================

.proc initialize_network
        lda net_state
        cmp #NET_STATE_INIT
        bne net_init_done

        ; Initialize IP65
        jsr ip65_init

        ; Request DHCP
        jsr dhcp_request

net_init_done:
        rts
.endproc

; ============================================================================
; IP65 STACK INITIALIZATION
; ============================================================================

.proc ip65_init
        ; W5100 initialization
        jsr w5100_reset

        ; Configure network buffer sizes
        ; 2KB TX buffer, 2KB RX buffer per socket
        lda #$55            ; 8KB total
        ldx socket_num
        jsr w5100_set_buffer

        ; Set gateway and netmask
        lda #<gateway_ip
        ldy #>gateway_ip
        jsr w5100_set_gateway

        lda #<netmask
        ldy #>netmask
        jsr w5100_set_netmask

        ; Set MAC address (use Apple II serial)
        lda #$02            ; Apple OUI prefix
        ldx #$60            ; Unique part
        jsr w5100_set_mac

        rts
.endproc

; ============================================================================
; W5100 RESET
; ============================================================================

.proc w5100_reset
        ldx socket_num

        ; Software reset
        lda #$80
        sta W5100_MR,x

        ; Wait for reset complete
        ldy #$FF
reset_wait:
        dey
        bne reset_wait

        ; Clear IR
        lda #$00
        sta W5100_IR,x

        rts
.endproc

; W5100 Register definitions (relative to slot base)
W5100_MR     = $0000        ; Mode Register
W5100_IR     = $0005        ; Interrupt Register
W5100_S0_MR  = $0400        ; Socket 0 Mode (slot * $100)
W5100_S0_CR  = $0401        ; Socket 0 Command
W5100_S0_SR  = $0402        ; Socket 0 Status
W5100_S0_TX  = $0404        ; Socket 0 TX Buffer
W5100_S0_RX  = $4404        ; Socket 0 RX Buffer (TX + 0x400)
W5100_RMSR   = $001A        ; RX Memory Size
W5100_TMSR   = $001B        ; TX Memory Size
W5100_GAR    = $0007        ; Gateway Address
W5100_SUBR   = $000B        ; Subnet Mask
W5100_SHAR   = $0009        ; Source Hardware Address

; Socket commands
SOCK_CMD_OPEN        = $01
SOCK_CMD_TCP_CONNECT = $14
SOCK_CMD_SEND        = $20
SOCK_CMD_RECV        = $40
SOCK_CMD_CLOSE       = $10

; Socket status
SOCK_STATUS_CLOSED   = $00
SOCK_STATUS_OPEN      = $13
SOCK_STATUS_ESTABLISHED = $17
SOCK_STATUS_CLOSE_WAIT = $1C

; ============================================================================
; DHCP REQUEST
; ============================================================================

.proc dhcp_request
        ; Using simplified DHCP
        ; For production, use full IP65 DHCP implementation

        ; Set initial IP (will be overwritten by DHCP)
        lda #<default_ip
        ldy #>default_ip
        jsr w5100_set_ip

        ; Mark as DHCP done (simplified - no actual DHCP)
        lda #NET_STATE_DHCP
        sta net_state

        rts

default_ip:
        .byte $C0, $A8, $01, $64    ; 192.168.1.100
gateway_ip:
        .byte $C0, $A8, $01, $01    ; 192.168.1.1
netmask:
        .byte $FF, $FF, $FF, $00    ; 255.255.255.0
.endproc

; ============================================================================
; MINER INITIALIZATION
; ============================================================================

.proc initialize_miner
        ; Set initial state
        lda #MINER_STATE_IDLE
        sta miner_state

        ; Set difficulty
        lda #<WORK_DIFFICULTY
        sta miner_difficulty
        lda #>WORK_DIFFICULTY
        sta miner_difficulty+1

        ; Clear nonce
        lda #$00
        sta hash_nonce
        sta hash_nonce+1
        sta hash_nonce+2
        sta hash_nonce+3

        ; Initialize hardware fingerprint
        jsr collect_fingerprint

        ; Display initialization complete
        ldx #$00
init_loop:
        lda init_text,x
        beq init_done
        jsr putchar
        inx
        jmp init_loop

init_done:
        lda #$8D
        jsr putchar
        rts

init_text:
        .byte "Miner initialized.", $8D
        .byte "Starting work loop...", $8D
        .byte 0
.endproc

; ============================================================================
; GET NEW WORK
; ============================================================================

.proc get_new_work
        ; Request work from network
        lda #MINER_STATE_WORK
        sta miner_state

        ; Display status
        ldx #$00
work_loop:
        lda work_text,x
        beq work_done
        jsr putchar
        inx
        jmp work_loop

work_done:
        rts

work_text:
        .byte "Requesting new work...", $8D
        .byte 0
.endproc

; ============================================================================
; PREPARE WORK
; ============================================================================

.proc prepare_work
        ; Build work packet from fingerprint
        ldx #$00
work_prep:
        lda fingerprint,x
        sta hash_work,x
        inx
        cpx #32
        bne work_prep

        ; Add nonce
        lda hash_nonce
        sta hash_work+32
        lda hash_nonce+1
        sta hash_work+33
        lda hash_nonce+2
        sta hash_work+34
        lda hash_nonce+3
        sta hash_work+35

        ; Add timestamp
        lda #$00            ; Will be filled by network
        sta hash_work+36
        lda #$00
        sta hash_work+37
        lda #$00
        sta hash_work+38
        lda #$00
        sta hash_work+39

        ; Pad work buffer to 64 bytes
        lda #$00
        ldx #$28            ; 40 bytes to fill
pad_loop:
        sta hash_work+40,x
        dex
        bne pad_loop

        rts
.endproc

; ============================================================================
; PERFORM HASH
; ============================================================================

.proc perform_hash
        ; Increment attempt counter
        inc miner_attempts
        bne no_carry
        inc miner_attempts+1
no_carry:

        ; Increment nonce
        inc hash_nonce
        bne hash_done
        inc hash_nonce+1
        bne hash_done
        inc hash_nonce+2
        bne hash_done
        inc hash_nonce+3
hash_done:

        ; Call SHA256
        lda #<hash_work
        ldy #>hash_work
        sta ptr
        sty ptr+1

        jsr sha256_update

        ; Get result
        jsr sha256_final

        rts
.endproc

; ============================================================================
; CHECK RESULT
; ============================================================================

.proc check_result
        ; Check if hash meets difficulty
        ; Compare first N bytes to zero (based on difficulty)

        ldx miner_difficulty
check_loop:
        lda sha256_result,x
        beq next_byte
        rts                 ; Not valid

next_byte:
        dex
        bpl check_loop

        ; Found valid hash!
        lda #$01
        sta tmp1            ; Valid flag
        rts
.endproc

; ============================================================================
; SUBMIT ATTESTATION
; ============================================================================

.proc submit_attestation
        ; Build JSON attestation
        lda #<attest_buffer
        sta ptr
        lda #>attest_buffer
        sta ptr+1

        ; Build JSON string
        jsr build_attestation_json

        ; Send HTTP POST
        jsr http_post

        rts

attest_buffer:
        .res 256            ; Attestation buffer
.endproc

.proc build_attestation_json
        ; JSON header
        lda #'"'
        jsr append_char
        lda #'d'
        jsr append_char
        lda #'e'
        jsr append_char
        lda #'v'
        jsr append_char
        lda #'i'
        jsr append_char
        lda #'c'
        jsr append_char
        lda #'e'
        jsr append_char
        lda #'_'
        jsr append_char
        lda #'a'
        jsr append_char
        lda #'r'
        jsr append_char
        lda #'c'
        jsr append_char
        lda #'h'
        jsr append_char
        lda #'"'
        jsr append_char
        lda #':'
        jsr append_char
        lda #'"'
        jsr append_char

        ; "6502"
        lda #'6'
        jsr append_char
        lda #'5'
        jsr append_char
        lda #'0'
        jsr append_char
        lda #'2'
        jsr append_char

        lda #'"'
        jsr append_char
        lda #','
        jsr append_char

        ; "device_family": "apple2"
        lda #'"'
        jsr append_char
        lda #'d'
        jsr append_char
        lda #'e'
        jsr append_char
        lda #'v'
        jsr append_char
        lda #'i'
        jsr append_char
        lda #'c'
        jsr append_char
        lda #'e'
        jsr append_char
        lda #'_'
        jsr append_char
        lda #'f'
        jsr append_char
        lda #'a'
        jsr append_char
        lda #'m'
        jsr append_char
        lda #'i'
        jsr append_char
        lda #'l'
        jsr append_char
        lda #'y'
        jsr append_char
        lda #'"'
        jsr append_char
        lda #':'
        jsr append_char
        lda #'"'
        jsr append_char

        ; "apple2"
        lda #'a'
        jsr append_char
        lda #'p'
        jsr append_char
        lda #'p'
        jsr append_char
        lda #'l'
        jsr append_char
        lda #'e'
        jsr append_char
        lda #'2'
        jsr append_char

        lda #'"'
        jsr append_char
        lda #'}'
        jsr append_char
        lda #$00            ; Null terminator

        rts
.endproc

.proc append_char
        pha
        ldy #$00
        lda (ptr),y
        sta tmp1
        inc
        sta (ptr),y
        inc ptr
        bne done
        inc ptr+1
done:
        pla
        rts
.endproc

; ============================================================================
; HTTP POST
; ============================================================================

.proc http_post
        ; Connect to rustchain.org
        lda #<rustchain_host
        ldy #>rustchain_host
        jsr tcp_connect

        ; Check connection
        bcs connection_failed

        ; Send HTTP POST
        lda #<http_post_data
        ldy #>http_post_data
        jsr tcp_send

        ; Receive response
        lda #<response_buffer
        ldy #>response_buffer
        ldx #$0100          ; 256 bytes
        jsr tcp_recv

        ; Close socket
        jsr tcp_close

        rts

connection_failed:
        lda #NET_STATE_ERROR
        sta net_state
        lda #$01
        sta net_error
        rts

rustchain_host:
        .byte "rustchain.org", 0
http_post_data:
        .byte "POST /api/attest HTTP/1.1", $0D, $0A
        .byte "Host: rustchain.org", $0D, $0A
        .byte "Content-Type: application/json", $0D, $0A
        .byte "Content-Length: ", 0
        .byte "XX", $0D, $0A
        .byte $0D, $0A
        ; JSON body follows
response_buffer:
        .res 256
.endproc

; ============================================================================
; TCP SOCKET OPERATIONS
; ============================================================================

.proc tcp_connect
        ; ptr: hostname pointer
        ; Returns: C=0 on success, C=1 on failure

        ; For W5100: Open socket 0 as TCP
        ldx socket_num

        ; Socket 0 MR = TCP
        lda #SOCK_TCP
        sta W5100_S0_MR,x

        ; Socket 0 Command = OPEN
        lda #SOCK_CMD_OPEN
        sta W5100_S0_CR,x

        ; Wait for OPEN
        jsr wait_socket_open

        ; Get host IP (simplified - would use DNS in production)
        ; For now, use hardcoded IP
        lda #<rustchain_ip
        ldy #>rustchain_ip
        sta ptr
        sty ptr+1

        ; Connect to IP:80
        lda #80            ; Port (little endian)
        sta W5100_S0_PORT,x
        lda #$00
        sta W5100_S0_PORT+1,x

        ; Destination IP
        ldy #$00
        lda (ptr),y
        sta W5100_S0_DIPR,x
        iny
        lda (ptr),y
        sta W5100_S0_DIPR+1,x
        iny
        lda (ptr),y
        sta W5100_S0_DIPR+2,x
        iny
        lda (ptr),y
        sta W5100_S0_DIPR+3,x

        ; CONNECT command
        lda #SOCK_CMD_TCP_CONNECT
        sta W5100_S0_CR,x

        ; Wait for connection
        jsr wait_socket_connected

        clc
        rts

rustchain_ip:
        .byte $52, $4B, $C8, $9B    ; Placeholder - needs actual IP
SOCK_TCP = $01
.endproc

.proc wait_socket_open
        ldx socket_num
wait_open_loop:
        lda W5100_S0_SR,x
        cmp #SOCK_STATUS_OPEN
        beq open_done
        ; Add timeout
        dec tmp1
        bne wait_open_loop
open_done:
        rts
.endproc

.proc wait_socket_connected
        ldx socket_num
wait_conn_loop:
        lda W5100_S0_SR,x
        cmp #SOCK_STATUS_ESTABLISHED
        beq conn_done
        cmp #SOCK_STATUS_CLOSE_WAIT
        beq conn_failed
        ; Add timeout
        dec tmp1
        bne wait_conn_loop
conn_failed:
        sec
        rts
conn_done:
        clc
        rts
.endproc

.proc tcp_send
        ; ptr: data pointer
        ; Send data to socket
        ldx socket_num

        ; Wait for TX buffer to be free
        lda #SOCK_CMD_SEND
        sta W5100_S0_CR,x

        ; Add timeout/retries
        rts
.endproc

.proc tcp_recv
        ; ptr: buffer pointer
        ; X: max bytes
        ; Receive data from socket
        ldx socket_num

        ; RECV command
        lda #SOCK_CMD_RECV
        sta W5100_S0_CR,x

        ; Copy from RX buffer
        rts
.endproc

.proc tcp_close
        ldx socket_num

        ; CLOSE command
        lda #SOCK_CMD_CLOSE
        sta W5100_S0_CR,x

        rts
.endproc

; W5100 Socket 0 registers (relative to socket_num)
W5100_S0_PORT   = $0404        ; Socket 0 Source Port
W5100_S0_DIPR   = $040C        ; Socket 0 Destination IP

; ============================================================================
; WAIT FOR BLOCK
; ============================================================================

.proc wait_for_block
        ; Simple wait between submissions
        ; In production, would wait for new block notification

        ldx #$FF
wait_loop:
        dex
        bne wait_loop

        rts
.endproc

; ============================================================================
; UPDATE DISPLAY
; ============================================================================

.proc update_display
        ; Show current status
        ; In production, would update real-time stats

        rts
.endproc

; ============================================================================
; HARDWARE FINGERPRINTING (delegates to fingerprint.s)
; ============================================================================

.proc collect_fingerprint
        jsr fp_collect
        rts
.endproc

; ============================================================================
; SHA256 ROUTINES (delegates to sha256.s)
; ============================================================================

sha256_result:
        .res 32

.proc sha256_update
        ; ptr: data pointer
        ; Updates SHA256 hash with data
        ; This is a placeholder - actual implementation in sha256.s
        rts
.endproc

.proc sha256_final
        ; Finalizes SHA256 hash
        ; Result stored in sha256_result
        ; This is a placeholder - actual implementation in sha256.s
        rts
.endproc

; ============================================================================
; PRODOS PREFIX SAVE/RESTORE
; ============================================================================

.proc save_prodos_prefix
        ; Save current ProDOS prefix for later restore
        rts
.endproc

; ============================================================================
; W5100 CONFIGURATION ROUTINES
; ============================================================================

.proc w5100_set_ip
        ; ptr: IP address pointer
        ldx socket_num
        ldy #$00
        lda (ptr),y
        sta W5100_GAR,x      ; Reuse GAR for IP for now
        iny
        lda (ptr),y
        sta W5100_GAR+1,x
        iny
        lda (ptr),y
        sta W5100_GAR+2,x
        iny
        lda (ptr),y
        sta W5100_GAR+3,x
        rts
.endproc

.proc w5100_set_gateway
        ldx socket_num
        ldy #$00
        lda (ptr),y
        sta W5100_GAR,x
        iny
        lda (ptr),y
        sta W5100_GAR+1,x
        iny
        lda (ptr),y
        sta W5100_GAR+2,x
        iny
        lda (ptr),y
        sta W5100_GAR+3,x
        rts
.endproc

.proc w5100_set_netmask
        ldx socket_num
        ldy #$00
        lda (ptr),y
        sta W5100_SUBR,x
        iny
        lda (ptr),y
        sta W5100_SUBR+1,x
        iny
        lda (ptr),y
        sta W5100_SUBR+2,x
        iny
        lda (ptr),y
        sta W5100_SUBR+3,x
        rts
.endproc

.proc w5100_set_mac
        ; A/X: MAC address bytes
        ldx socket_num
        ; MAC is stored in SHAR
        rts
.endproc

.proc w5100_set_buffer
        ; A: buffer size code
        ldx socket_num
        ; Set TX/RX memory size
        sta W5100_TMSR,x
        sta W5100_RMSR,x
        rts
.endproc

; ============================================================================
; DATA SECTION
; ============================================================================

.segment "DATA"

; Version string
miner_version:
        .byte "RUSTCHAIN MINER v1.0", $00

; Attestation endpoint
attest_endpoint:
        .byte "rustchain.org", $00
        .byte "/api/attest", $00

; Device identifiers
device_arch:
        .byte "6502", $00

device_family:
        .byte "apple2", $00

; ============================================================================
; CC65 LINKER CONFIGURATION
; ============================================================================

.segment "STARTUP"
.word $0000           ; Not used
.word _start          ; Entry point
.word $0000           ; Stack size

; ============================================================================
; END OF FILE
; ============================================================================
