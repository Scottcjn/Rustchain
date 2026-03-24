/* poa_dos.c - DOS PoA validator TCP pusher using WATTCP */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <dos.h>
#include "tcp.h"    /* WATTCP sockets */

void main() {
    sock_init();

    tcp_Socket sock;
    char json[512], http[1024];
    int port = 5000;
    char *host = "192.168.1.100";  /* change to match your server */

    /* Simulated fingerprint data */
    sprintf(json, "{\"device\":\"DOSBox\",\"cpu\":\"386DX\",\"bios\":\"AMI 1994\",\"fingerprint\":\"DOS-LEGIT-1\"}");

    /* Build HTTP POST request */
    sprintf(http,
        "POST /validate HTTP/1.0\r\n"
        "Host: %s\r\n"
        "Content-Type: application/json\r\n"
        "Content-Length: %d\r\n\r\n"
        "%s", host, strlen(json), json);

    if (!tcp_open(&sock, 0, host, port, NULL)) {
        printf("Error: Could not connect to %s:%d\n", host, port);
        exit(1);
    }

    sock_mode(&sock, TCP_MODE_ASCII);
    outs(http, &sock);

    while (sock_bytesready(&sock) > 0) {
        putchar(sock_getc(&sock));
    }

    sock_close(&sock);
    printf("\nPoA payload sent!\n");
}
