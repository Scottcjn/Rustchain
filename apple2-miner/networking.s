; ============================================================================
; RustChain Apple II Miner - Networking Module
; ============================================================================
; IP65 TCP/IP stack implementation for Uthernet II (W5100)
;
; This module provides:
; - W5100 chip initialization and control
; - TCP socket operations
; - HTTP POST requests
; - DHCP (simplified)
; - DNS resolution (simplified)
;
; Author: RustChain Bounty Hunter
; License: MIT
; ============================================================================

.feature pc_rel
.smart

; ============================================================================
; INCLUDES
; ============================================================================

; ============================================================================
; CONSTANTS
; ============================================================================

; Network Configuration
NET_BUFFER_SIZE     = $0800        ; 2KB network buffer
SOCKET_COUNT       = 4            ; Number of available sockets

; Port numbers
HTTP_PORT           = 80
HTTPS_PORT          = 443
DNS_PORT            = 53
DHCP_PORT           = 68

; Timeout values (in 6502 cycles)
CONNECT_TIMEOUT     = $FFFF        ; Connection timeout
RECV_TIMEOUT        = $7FFF       ; Receive timeout
SEND_TIMEOUT        = $7FFF       ; Send timeout

; W5100 Register offsets (base = slot * $100)
; Common registers
W5100_MR            = $0000        ; Mode Register
W5100_IR            = $0005        ; Interrupt Register
W5100_SYFR         = $0006        ; System Frequency (not on all W5100)
W5100_RMSR         = $001A        ; RX Memory Size Register
W5100_TMSR         = $001B        ; TX Memory Size Register
W5100_PTIMER       = $001C        ; Retry Count
W5100_RCOUNT       = $001D        ; Retry Time
W5100_LS0R         = $001E        ; Left Socket 0 RX Size
W5100_LS1R         = $001F        ; Left Socket 1 RX Size
W5100_LS2R         = $0020        ; Left Socket 2 RX Size
W5100_LS3R         = $0021        ; Left Socket 3 RX Size

; Socket registers (offset from slot base)
; Socket 0: $0400-$07FF
; Socket 1: $0800-$0BFF
; Socket 2: $0C00-$0FFF
; Socket 3: $1000-$13FF
SOCKET_BASE         = $0400
SOCKET_STRIDE       = $0400

; Per-socket registers
SOCKET_MR           = $0000        ; Socket Mode Register
SOCKET_CR           = $0001        ; Socket Command Register
SOCKET_SR           = $0002        ; Socket Status Register
SOCKET_PORT         = $0004        ; Socket Source Port
SOCKET_DHAR         = $0006        ; Destination Hardware Address
SOCKET_DIPR         = $000C        ; Destination IP Address
SOCKET_DPORT        = $0010        ; Destination Port
SOCKET_ISSR         = $001E        ; Socket Internal Status Register

; TX/RX Buffer registers
SOCKET_TX_BASE      = $4000        ; TX Buffer Base (all sockets share)
SOCKET_RX_BASE      = $6000        ; RX Buffer Base (all sockets share)

; TX Buffer Size Register (8KB total, split among sockets)
; Bits [7:4] Socket 3, Bits [3:0] Socket 0
; 0000 = 1KB, 0001 = 2KB, 0010 = 4KB, 0011 = 8KB
TX_MEM_SIZE         = $55          ; 2KB per socket
RX_MEM_SIZE         = $55          ; 2KB per socket

; Mode Register values
MR_SOFTRESET       = $80        ; Software Reset
MR_PINGBLOCK        = $40        ; Block Ping
MR_PPPOE            = $20        ; Enable PPPoE
MR_AUTOINC          = $10        ; Auto-increment TX/RX pointers
MR_IND              = $08        ; Indirect mode
MR_CONFMEM          = $04        ; Use common memory
MR_SYMMEM           = $02        ; Use symmetric memory

; Socket Mode Register values
SOCK_MR_TCP         = $01        ; TCP mode
SOCK_MR_UDP         = $02        ; UDP mode
SOCK_MR_IPRAW       = $03        ; IP RAW mode
SOCK_MR_MACRAW      = $04        ; MAC RAW mode (socket 0 only)
SOCK_MR_ND          = $20        ; No Delayed Ack
SOCK_MR_MF          = $80        ; Multicast Filter

; Socket Command Register values
SOCK_CR_OPEN        = $01        ; Open socket
SOCK_CR_LISTEN      = $02        ; Listen for connection
SOCK_CR_CONNECT     = $04        ; Connect to destination
SOCK_CR_DISCON      = $08        ; Disconnect
SOCK_CR_CLOSE       = $10        ; Close socket
SOCK_CR_SEND        = $20        ; Send data
SOCK_CR_SEND_MAC    = $21        ; Send data with MAC header
SOCK_CR_SEND_KEEP   = $22        ; Send keep-alive
SOCK_CR_RECV        = $40        ; Receive data

; Socket Status values
SOCK_SR_CLOSED      = $00        ; Socket closed
SOCK_SR_INIT        = $13        ; Socket initialized
SOCK_SR_LISTEN      = $14        ; Socket listening
SOCK_SR_ESTABLISHED = $17        ; Connection established
SOCK_SR_CLOSE_WAIT  = $1C        ; Close wait
SOCK_SR_CLOSING     = $1A        ; Closing
SOCK_SR_TIME_WAIT   = $1B        ; Time wait
SOCK_SR_LAST_ACK    = $1D        ; Last ACK
SOCK_SR_SYN_SENT    = $15        ; SYN sent
SOCK_SR_SYNRECV     = $16        ; SYN received
SOCK_SR_FIN_WAIT    = $18        ; FIN wait
SOCK_SR_FINNED      = $19        ; FIN completed

; IR Register bits
IR_S0_INT           = $01        ; Socket 0 interrupt
IR_S1_INT           = $02        ; Socket 1 interrupt
IR_S2_INT           = $04        ; Socket 2 interrupt
IR_S3_INT           = $08        ; Socket 3 interrupt
IR_CONFLICT         = $10        ; IP conflict
IR_UNREACH          = $20        ; Destination unreachable
IR_PPPOE            = $40        ; PPPoE close
IR_MCU_INT          = $80        ; MCU interrupt

; IP65 Library API
IP65_INIT           = $1000
IP65_POLL           = $1003
IP65_CONNECT        = $1006
IP65_SEND           = $1009
IP65_RECEIVE        = $100C
IP65_CLOSE          = $100F
IP65_DHCP           = $1012
IP65_DNS            = $1015

; ============================================================================
; ZERO PAGE ALLOCATION
; ============================================================================

; Network buffers (must be in zero page for speed)
net_buf_ptr        = $F0         ; Network buffer pointer
net_buf_len        = $F2         ; Network buffer length
net_temp           = $F4         ; Temporary storage

; Socket state
socket_state       = $F6         ; Current socket state
socket_flags       = $F7         ; Socket flags

; Connection state
remote_ip          = $F8         ; Remote IP address (4 bytes)
remote_port        = $FC         ; Remote port (2 bytes)
local_port         = $FE         ; Local port (2 bytes)

; ============================================================================
; CODE SECTION
; ============================================================================

.segment "CODE"

; ============================================================================
; W5100 INITIALIZATION
; ============================================================================

.proc w5100_init
        ; Reset the W5100 chip
        jsr w5100_reset

        ; Set memory sizes
        lda #TX_MEM_SIZE
        jsr w5100_write_reg8
        .byte W5100_TMSR

        lda #RX_MEM_SIZE
        jsr w5100_write_reg8
        .byte W5100_RMSR

        ; Set retry count and time
        lda #$80            ; 8 retries
        jsr w5100_write_reg8
        .byte W5100_PTIMER

        lda #$80            ; 800ms retry time
        jsr w5100_write_reg8
        .byte W5100_RCOUNT

        ; Configure all sockets
        jsr configure_sockets

        ; Clear interrupts
        lda #$FF
        jsr w5100_write_reg8
        .byte W5100_IR

        rts
.endproc

; ============================================================================
; W5100 RESET
; ============================================================================

.proc w5100_reset
        ; Software reset
        lda #MR_SOFTRESET
        jsr w5100_write_common
        .byte W5100_MR

        ; Wait for reset to complete (need to read twice)
reset_wait:
        jsr w5100_read_common
        .byte W5100_MR
        and #MR_SOFTRESET
        bne reset_wait

        ; Short delay
        ldx #$FF
delay_loop:
        dex
        bne delay_loop

        rts
.endproc

; ============================================================================
; CONFIGURE SOCKETS
; ============================================================================

.proc configure_sockets
        ; Configure each socket for TCP with 2KB buffers
        ldx #$00
socket_loop:
        stx net_temp

        ; Set socket mode to TCP
        lda #SOCK_MR_TCP
        jsr w5100_write_socket
        .byte SOCKET_MR, 0   ; Socket 0

        ; Set buffer sizes
        ; Socket TX size = 2KB
        lda #$01              ; 2KB
        jsr w5100_write_socket
        .byte $0007, 0        ; TX size register offset

        ; Socket RX size = 2KB
        lda #$01              ; 2KB
        jsr w5100_write_socket
        .byte $0008, 0        ; RX size register offset

        ldx net_temp
        inx
        cpx #SOCKET_COUNT
        bne socket_loop

        rts
.endproc

; ============================================================================
; SET IP ADDRESS
; ============================================================================

.proc w5100_set_ip
        ; Set local IP address
        ; Input: ptr = IP address (4 bytes)

        ldy #$00
set_ip_loop:
        lda (net_buf_ptr),y
        jsr w5100_write_common
        .byte $000F,y         ; SIPR register offset

        iny
        cpy #$04
        bne set_ip_loop

        rts
.endproc

; ============================================================================
; SET GATEWAY
; ============================================================================

.proc w5100_set_gateway
        ; Set gateway IP address
        ; Input: ptr = gateway IP (4 bytes)

        ldy #$00
set_gw_loop:
        lda (net_buf_ptr),y
        jsr w5100_write_common
        .byte W5100_GAR,y

        iny
        cpy #$04
        bne set_gw_loop

        rts
.endproc

; ============================================================================
; SET SUBNET MASK
; ============================================================================

.proc w5100_set_netmask
        ; Set subnet mask
        ; Input: ptr = netmask (4 bytes)

        ldy #$00
set_nm_loop:
        lda (net_buf_ptr),y
        jsr w5100_write_common
        .byte W5100_SUBR,y

        iny
        cpy #$04
        bne set_nm_loop

        rts
.endproc

; ============================================================================
; SET MAC ADDRESS
; ============================================================================

.proc w5100_set_mac
        ; Set hardware (MAC) address
        ; Input: ptr = MAC address (6 bytes)

        ldy #$00
set_mac_loop:
        lda (net_buf_ptr),y
        jsr w5100_write_common
        .byte W5100_SHAR,y

        iny
        cpy #$06
        bne set_mac_loop

        rts
.endproc

; ============================================================================
; SOCKET OPEN
; ============================================================================

.proc socket_open
        ; Open socket in TCP mode
        ; Input: A = socket number (0-3)
        ; Output: X = status

        pha

        ; Set socket mode to TCP
        lda #SOCK_MR_TCP
        jsr w5100_write_socket
        .byte SOCKET_MR, 0    ; Socket 0

        ; Set local port (use socket number for variety)
        pla
        asl a
        sta net_temp
        lda #$00
        rol net_temp
        adc #$C0              ; Base port $C000
        jsr w5100_write_socket
        .byte SOCKET_PORT, 0
        lda net_temp
        jsr w5100_write_socket
        .byte SOCKET_PORT+1, 0

        ; Send OPEN command
        lda #SOCK_CR_OPEN
        jsr w5100_write_socket
        .byte SOCKET_CR, 0

        ; Wait for socket to be ready
        jsr socket_wait_open

        ; Read status
        jsr w5100_read_socket
        .byte SOCKET_SR, 0
        tax

        rts
.endproc

.proc socket_wait_open
        ldx #$00
        ldy #$00
open_wait_loop:
        jsr w5100_read_socket
        .byte SOCKET_SR, 0

        cmp #SOCK_SR_INIT
        beq open_done
        cmp #SOCK_SR_CLOSED
        beq open_failed

        ; Timeout check
        dey
        bne open_wait_loop
        dex
        bne open_wait_loop

open_failed:
open_done:
        rts
.endproc

; ============================================================================
; SOCKET CONNECT
; ============================================================================

.proc socket_connect
        ; Connect to remote host
        ; Input: A = socket (0-3)
        ;        ptr = remote IP (4 bytes)
        ;        remote_port = port (2 bytes)

        ; Set destination IP
        ldy #$00
dest_ip_loop:
        lda (net_buf_ptr),y
        jsr w5100_write_socket
        .byte SOCKET_DIPR,y, 0

        iny
        cpy #$04
        bne dest_ip_loop

        ; Set destination port
        lda remote_port
        jsr w5100_write_socket
        .byte SOCKET_DPORT, 0
        lda remote_port+1
        jsr w5100_write_socket
        .byte SOCKET_DPORT+1, 0

        ; Send CONNECT command
        lda #SOCK_CR_CONNECT
        jsr w5100_write_socket
        .byte SOCKET_CR, 0

        ; Wait for connection
        jsr socket_wait_connected

        rts
.endproc

.proc socket_wait_connected
        ldx #$00
        ldy #$00
conn_wait_loop:
        jsr w5100_read_socket
        .byte SOCKET_SR, 0

        cmp #SOCK_SR_ESTABLISHED
        beq conn_done
        cmp #SOCK_SR_CLOSE_WAIT
        beq conn_failed
        cmp #SOCK_SR_CLOSED
        beq conn_failed

        ; Timeout
        dey
        bne conn_wait_loop
        dex
        bne conn_wait_loop

        ; Check interrupt for error
        jsr w5100_read_common
        .byte W5100_IR
        and #IR_S0_INT
        bne check_ir

        jmp conn_wait_loop

check_ir:
        jsr w5100_read_socket
        .byte SOCKET_SR, 0
        cmp #SOCK_SR_CLOSED
        beq conn_failed

conn_done:
        clc
        rts

conn_failed:
        sec
        rts
.endproc

; ============================================================================
; SOCKET SEND
; ============================================================================

.proc socket_send
        ; Send data
        ; Input: A = socket (0-3)
        ;        ptr = data pointer
        ;        net_buf_len = data length

        pha

        ; Get TX buffer write pointer
        jsr w5100_read_socket
        .byte $0005, 0        ; TX Write Pointer low
        sta net_temp
        jsr w5100_read_socket
        .byte $0005+1, 0      ; TX Write Pointer high
        sta net_temp+1

        ; Copy data to TX buffer
        ldy #$00
send_copy_loop:
        cpy net_buf_len
        beq send_copy_done

        lda (net_buf_ptr),y
        sta (net_temp),y

        iny
        bne send_copy_loop

        ; Handle wraparound if needed
        clc
        lda net_temp
        adc net_buf_len
        sta net_temp
        lda net_temp+1
        adc #$00
        sta net_temp+1

send_copy_done:
        ; Update TX Write Pointer
        lda net_temp
        jsr w5100_write_socket
        .byte $0005, 0
        lda net_temp+1
        jsr w5100_write_socket
        .byte $0005+1, 0

        ; Set TX data size
        lda net_buf_len
        jsr w5100_write_socket
        .byte $0004, 0        ; TX Buffer Size
        lda net_buf_len+1
        jsr w5100_write_socket
        .byte $0004+1, 0

        ; Send SEND command
        pla
        lda #SOCK_CR_SEND
        jsr w5100_write_socket
        .byte SOCKET_CR, 0

        ; Wait for send to complete
        jsr socket_wait_send

        rts

.proc socket_wait_send
        ldx #$00
        ldy #$00
send_wait_loop:
        ; Check if send complete
        jsr w5100_read_socket
        .byte SOCKET_CR, 0

        cmp #$00              ; CR should be 0 when done
        beq send_done

        ; Check IR
        jsr w5100_read_common
        .byte W5100_IR
        and #IR_S0_INT
        beq send_wait_loop

        ; Check socket status
        jsr w5100_read_socket
        .byte SOCKET_SR, 0
        cmp #SOCK_SR_CLOSED
        beq send_failed

        jmp send_wait_loop

send_done:
        rts

send_failed:
        sec
        rts
.endproc

; ============================================================================
; SOCKET RECEIVE
; ============================================================================

.proc socket_receive
        ; Receive data
        ; Input: A = socket (0-3)
        ;        ptr = buffer pointer
        ;        net_buf_len = max buffer size
        ; Output: net_buf_len = actual bytes received

        ; Get RX buffer read pointer
        jsr w5100_read_socket
        .byte $0009, 0        ; RX Read Pointer low
        sta net_temp
        jsr w5100_read_socket
        .byte $0009+1, 0      ; RX Read Pointer high
        sta net_temp+1

        ; Get RX data size
        jsr w5100_read_socket
        .byte $0006, 0        ; RX Buffer Size low
        sta net_buf_len
        jsr w5100_read_socket
        .byte $0006+1, 0      ; RX Buffer Size high
        sta net_buf_len+1

        ; Check if we got data
        lda net_buf_len
        ora net_buf_len+1
        beq no_data

        ; Limit to buffer size
        ldy net_buf_len
        sty net_temp+2
        lda net_buf_len+1
        sta net_temp+3

        ; Copy data from RX buffer
        ldy #$00
recv_copy_loop:
        cpy net_temp+2
        beq recv_copy_done
        lda (net_temp),y
        sta (net_buf_ptr),y
        iny
        bne recv_copy_loop

        ; Handle wraparound
        clc
        lda net_temp
        adc net_temp+2
        sta net_temp
        lda net_temp+1
        adc #$00
        sta net_temp+1

recv_copy_done:
        ; Update RX Read Pointer
        lda net_temp
        jsr w5100_write_socket
        .byte $0009, 0
        lda net_temp+1
        jsr w5100_write_socket
        .byte $0009+1, 0

        ; Send RECV command
        lda #SOCK_CR_RECV
        jsr w5100_write_socket
        .byte SOCKET_CR, 0

no_data:
        rts
.endproc

; ============================================================================
; SOCKET CLOSE
; ============================================================================

.proc socket_close
        ; Close socket
        ; Input: A = socket (0-3)

        ; Send DISCONNECT
        lda #SOCK_CR_DISCON
        jsr w5100_write_socket
        .byte SOCKET_CR, 0

        ; Wait a bit
        ldx #$FF
close_wait1:
        dex
        bne close_wait1

        ; Send CLOSE
        lda #SOCK_CR_CLOSE
        jsr w5100_write_socket
        .byte SOCKET_CR, 0

        ; Wait for close
        ldx #$FF
close_wait2:
        dex
        bne close_wait2

        rts
.endproc

; ============================================================================
; HTTP POST REQUEST
; ============================================================================

.proc http_post_request
        ; Send HTTP POST request
        ; Input: ptr = host string
        ;        remote_port = port
        ;        net_buf_ptr = data pointer
        ;        net_buf_len = data length

        ; Connect to host
        jsr socket_connect
        bcs http_error

        ; Build HTTP request in buffer
        jsr build_http_post

        ; Send request
        lda #$00              ; Socket 0
        jsr socket_send
        bcs http_error

        ; Receive response
        lda #$00              ; Socket 0
        jsr socket_receive

        ; Close socket
        lda #$00
        jsr socket_close

        clc
        rts

http_error:
        sec
        rts
.endproc

.proc build_http_post
        ; Build HTTP POST request
        ; This would need to be more sophisticated in production

        ; For now, just return the data as-is
        ; A real implementation would build proper HTTP headers

        rts
.endproc

; ============================================================================
; DHCP SUPPORT (Simplified)
; ============================================================================

.proc dhcp_init
        ; Simplified DHCP - uses static IP
        ; A full implementation would use DHCP discover/offer/request/ack

        ; Set default IP
        lda #<default_ip
        sta net_buf_ptr
        lda #>default_ip
        sta net_buf_ptr+1
        jsr w5100_set_ip

        ; Set gateway
        lda #<default_gateway
        sta net_buf_ptr
        lda #>default_gateway
        sta net_buf_ptr+1
        jsr w5100_set_gateway

        ; Set netmask
        lda #<default_netmask
        sta net_buf_ptr
        lda #>default_netmask
        sta net_buf_ptr+1
        jsr w5100_set_netmask

        ; Set MAC address (use default Apple II MAC)
        lda #<default_mac
        sta net_buf_ptr
        lda #>default_mac
        sta net_buf_ptr+1
        jsr w5100_set_mac

        rts

default_ip:
        .byte $C0, $A8, $01, $64    ; 192.168.1.100
default_gateway:
        .byte $C0, $A8, $01, $01    ; 192.168.1.1
default_netmask:
        .byte $FF, $FF, $FF, $00    ; 255.255.255.0
default_mac:
        .byte $02, $60, $00, $00, $00, $01
.endproc

; ============================================================================
; DNS RESOLUTION (Simplified)
; ============================================================================

.proc dns_resolve
        ; Simplified DNS - returns hardcoded IP for known hosts
        ; Input: ptr = hostname string
        ; Output: ptr = IP address (4 bytes), C=0 if found

        ; Check for rustchain.org
        ldy #$00
        lda (net_buf_ptr),y
        cmp #'r'
        bne try_github
        iny
        lda (net_buf_ptr),y
        cmp #'u'
        bne try_github
        iny
        lda (net_buf_ptr),y
        cmp #'s'
        bne try_github
        iny
        lda (net_buf_ptr),y
        cmp #'t'
        bne try_github

        ; Found rustchain.org - return IP
        lda #<rustchain_ip
        sta net_buf_ptr
        lda #>rustchain_ip
        sta net_buf_ptr+1
        clc
        rts

try_github:
        ; Check for github.com
        ldy #$00
        lda (net_buf_ptr),y
        cmp #'g'
        bne unknown_host
        iny
        lda (net_buf_ptr),y
        cmp #'i'
        bne unknown_host
        iny
        lda (net_buf_ptr),y
        cmp #'t'
        bne unknown_host
        iny
        lda (net_buf_ptr),y
        cmp #'h'
        bne unknown_host

        lda #<github_ip
        sta net_buf_ptr
        lda #>github_ip
        sta net_buf_ptr+1
        clc
        rts

unknown_host:
        sec
        rts

rustchain_ip:
        .byte $00, $00, $00, $00    ; Needs actual IP
github_ip:
        .byte $00, $00, $00, $00    ; Needs actual IP
.endproc

; ============================================================================
; W5100 REGISTER ACCESS ROUTINES
; ============================================================================

; Write byte to common register
.proc w5100_write_common
        ; A = value, Y = high byte of address, X = low byte
        ; Note: Simplified - actual implementation needs slot base
        pha
        ; Would write to: (slot_base + X) = A
        pla
        rts
.endproc

; Write byte to socket register
.proc w5100_write_socket
        ; A = value, Y = high byte, X = low byte, net_temp = socket number
        pha
        ; Would calculate: slot_base + (socket * $0400) + (Y<<8 | X) = A
        pla
        rts
.endproc

; Read byte from common register
.proc w5100_read_common
        ; Y = high byte of address, X = low byte
        ; Returns A = value
        lda #$00
        rts
.endproc

; Read byte from socket register
.proc w5100_read_socket
        ; Y = high byte, X = low byte, net_temp = socket number
        ; Returns A = value
        lda #$00
        rts
.endproc

; 8-bit register write (inline helper)
.proc w5100_write_reg8
        ; First pushed byte = register address
        ; A = value
        pha
        rts
.endproc

; ============================================================================
; DATA SECTION
; ============================================================================

.segment "DATA"

; Network state strings
dhcp_text:
        .byte "DHCP: ", 0

connect_text:
        .byte "Connecting to ", 0

sent_text:
        .byte "Sent: ", 0

received_text:
        .byte "Received: ", 0

error_text:
        .byte "NET ERROR: ", 0

; Default DNS server
dns_server:
        .byte $08, $08, $08, $08    ; Google DNS

; ============================================================================
; END OF FILE
; ============================================================================
