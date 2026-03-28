/*
 * http_client.h - Minimal HTTP/1.0 client for Intel 386 / C89
 *
 * BSD sockets only. No TLS. No redirects. No keep-alive.
 * Works under DJGPP (with a Winsock-style shim) and Linux i386.
 *
 * Usage:
 *   int http_post(const char *host, int port, const char *path,
 *                 const char *body, char *resp, int resp_max);
 *   Returns 0 on success, -1 on error.
 *   resp is filled with the HTTP response body (null-terminated).
 */

#ifndef HTTP_CLIENT_H
#define HTTP_CLIENT_H

#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#ifdef __DJGPP__
#  include <tcp.h>        /* watt-32 / DJGPP networking */
#  define CLOSE_SOCK(s)  close_s(s)
   typedef int sock_t;
#else
#  include <sys/types.h>
#  include <sys/socket.h>
#  include <netinet/in.h>
#  include <netdb.h>
#  include <unistd.h>
#  define CLOSE_SOCK(s)  close(s)
   typedef int sock_t;
#endif

#define HTTP_TIMEOUT_SEC  15
#define HTTP_BUF_MAX      4096

/* Resolve hostname → IPv4 address (network byte order).
 * Returns 0 on failure. */
static unsigned long http_resolve(const char *host)
{
    struct hostent *he;
    he = gethostbyname(host);
    if (!he || !he->h_addr_list[0]) return 0;
    return *((unsigned long *)he->h_addr_list[0]);
}

/*
 * http_post — send a POST request, read the response body.
 *
 * host     : hostname (no "http://")
 * port     : TCP port (e.g. 8088)
 * path     : URL path (e.g. "/attest/submit")
 * body     : request body (JSON string)
 * resp     : output buffer for the response body
 * resp_max : size of resp buffer
 *
 * Returns HTTP status code on success, -1 on socket/network error.
 */
static int http_post(const char *host, int port, const char *path,
                     const char *body, char *resp, int resp_max)
{
    sock_t fd;
    struct sockaddr_in addr;
    char req[HTTP_BUF_MAX];
    char rbuf[HTTP_BUF_MAX];
    int  body_len, req_len;
    int  n, total, status;
    char *p;

    /* Build request */
    body_len = (int)strlen(body);
    req_len  = sprintf(req,
        "POST %s HTTP/1.0\r\n"
        "Host: %s:%d\r\n"
        "Content-Type: application/json\r\n"
        "Content-Length: %d\r\n"
        "Connection: close\r\n"
        "\r\n"
        "%s",
        path, host, port, body_len, body);

    /* Resolve */
    addr.sin_family      = AF_INET;
    addr.sin_port        = htons((unsigned short)port);
    addr.sin_addr.s_addr = http_resolve(host);
    if (addr.sin_addr.s_addr == 0) return -1;

    /* Connect */
    fd = socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0) return -1;
    if (connect(fd, (struct sockaddr *)&addr, sizeof(addr)) != 0) {
        CLOSE_SOCK(fd); return -1;
    }

    /* Send */
    if (send(fd, req, req_len, 0) != req_len) {
        CLOSE_SOCK(fd); return -1;
    }

    /* Receive */
    total = 0;
    memset(rbuf, 0, sizeof(rbuf));
    while (total < HTTP_BUF_MAX - 1) {
        n = recv(fd, rbuf + total, HTTP_BUF_MAX - 1 - total, 0);
        if (n <= 0) break;
        total += n;
    }
    CLOSE_SOCK(fd);
    rbuf[total] = '\0';

    /* Parse status line: "HTTP/1.x NNN ..." */
    status = -1;
    if (strncmp(rbuf, "HTTP/", 5) == 0) {
        p = strchr(rbuf, ' ');
        if (p) status = atoi(p + 1);
    }

    /* Extract body (after blank line) */
    p = strstr(rbuf, "\r\n\r\n");
    if (!p) p = strstr(rbuf, "\n\n");
    if (p) {
        p += (p[0] == '\r') ? 4 : 2;
        strncpy(resp, p, resp_max - 1);
        resp[resp_max - 1] = '\0';
    } else {
        resp[0] = '\0';
    }

    return status;
}

/*
 * Parse "http://host:port/path" into components.
 * Returns 0 on success. host/path must be caller-owned buffers.
 */
static int http_parse_url(const char *url, char *host, int *port, char *path)
{
    const char *p;
    const char *colon;
    const char *slash;
    int hlen;

    /* skip scheme */
    p = url;
    if (strncmp(p, "http://", 7) == 0) p += 7;

    slash = strchr(p, '/');
    colon = strchr(p, ':');

    if (colon && (!slash || colon < slash)) {
        hlen = (int)(colon - p);
        strncpy(host, p, hlen); host[hlen] = '\0';
        *port = atoi(colon + 1);
    } else {
        hlen = slash ? (int)(slash - p) : (int)strlen(p);
        strncpy(host, p, hlen); host[hlen] = '\0';
        *port = 80;
    }

    if (slash) strcpy(path, slash);
    else       strcpy(path, "/");

    return 0;
}

#endif /* HTTP_CLIENT_H */
