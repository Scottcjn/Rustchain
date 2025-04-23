; validator_push.asm
; Devpac-style Amiga 500 assembly to send JSON PoA packet over TCP
; Requires bsdsocket.library and TCP/IP stack (e.g., Roadshow, AmiTCP)

        SECTION code,CODE
        XREF _LVOsocket, _LVOconnect, _LVOsend, _LVOclose, _LVOOpenLibrary
        XREF _LVOWrite
        XDEF _start

        INCLUDE "exec/exec_lib.i"
        INCLUDE "bsdsocket.i"

_start:
        lea     socketname,a1
        move.l  #4,d0
        jsr     _LVOOpenLibrary(a6)
        move.l  d0,socketbase
        beq     exit

        move.l  socketbase,a6
        move.l  #2,d0          ; AF_INET
        move.l  #1,d1          ; SOCK_STREAM
        move.l  #6,d2          ; IPPROTO_TCP
        jsr     _LVOsocket(a6)
        move.l  d0,sockfd
        cmp.l   #-1,d0
        beq     exit

        ; Setup sockaddr_in
        lea     sockaddr,a0
        move.b  #2,(a0)        ; AF_INET
        move.b  #0,1(a0)       ; zero padding
        move.w  port,2(a0)     ; port in network byte order
        move.l  ipaddr,4(a0)   ; IP address

        move.l  sockfd,d0
        move.l  a0,d1
        move.l  #16,d2
        jsr     _LVOconnect(a6)
        cmp.l   #-1,d0
        beq     exit

        ; Send the payload
        lea     payload,a0
        move.l  sockfd,d0
        move.l  a0,d1
        move.l  #payload_end - payload,d2
        move.l  #0,d3
        jsr     _LVOsend(a6)

exit:
        move.l  sockfd,d0
        jsr     _LVOclose(a6)

        rts

; --- Data Section ---
        SECTION data,DATA
socketname:
        dc.b    "bsdsocket.library",0
        even

sockfd:     dc.l    -1
socketbase: dc.l    0

; Example sockaddr_in
sockaddr:
        dc.b    2,0                ; AF_INET + padding
port:   dc.w    $1388              ; Port 5000 (0x1388)
ipaddr: dc.l    $C0A80164          ; 192.168.1.100 in hex (change as needed)

payload:
        dc.b "POST /validate HTTP/1.1",10
        dc.b "Host: 192.168.1.100:5000",10
        dc.b "Content-Type: application/json",10
        dc.b "Content-Length: 122",10,10
        dc.b "{"
        dc.b '"device":"Amiga 500","rom":"Kickstart 1.3",'
        dc.b '"message":"disk clicked once",'
        dc.b '"fingerprint":"B64-SHA"}',10
payload_end:
        dc.b 0
