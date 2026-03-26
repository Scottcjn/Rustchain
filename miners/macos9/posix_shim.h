/*
 * posix_shim.h - POSIX Compatibility Shim for Mac OS 9.2 (PowerPC)
 * 
 * Provides BSD-compatible socket I/O and time functions for Mac OS 9
 * using GUSI 2.x (Grand Unified Socket Interface) and Mac Toolbox.
 * 
 * Target: Mac OS 9.2.2 on PowerPC G3/G4
 * Compiler: Metrowerks CodeWarrior Pro 8 or Retro68
 * 
 * This shim enables portable network code to run on vintage Mac OS
 * without modification, bridging POSIX to Mac Toolbox APIs.
 */

#ifndef POSIX_SHIM_H
#define POSIX_SHIM_H

#include <stdint.h>
#include <stddef.h>

/*errno.h replacement - Mac OS 9 error codes */
#define POSIX_EPERM       1
#define POSIX_ENOENT      2
#define POSIX_EIO         5
#define POSIX_EBADF       9
#define POSIX_EAGAIN      11
#define POSIX_ENOMEM      12
#define POSIX_EACCES      13
#define POSIX_EFAULT      14
#define POSIX_EINVAL      22
#define POSIX_ENOSPC      28
#define POSIX_EPROTO      71
#define POSIX_ENOTSOCK     88
#define POSIX_EISCONN      89
#define POSIX_ECONNRESET  104

extern int errno;

/* Socket address families (BSD-compatible) */
#define AF_INET       2
#define AF_UNSPEC     0

/* Socket types */
#define SOCK_STREAM   1
#define SOCK_DGRAM    2

/* Socket protocols */
#define IPPROTO_TCP   6
#define IPPROTO_UDP   17

/* Address structure - BSD-compatible */
struct sockaddr_in {
    uint16_t    sin_family;   /* AF_INET */
    uint16_t    sin_port;     /* Port number (network byte order) */
    uint32_t    sin_addr;     /* IP address (network byte order) */
    char        sin_zero[8];  /* Padding */
};

struct sockaddr {
    uint16_t    sa_family;
    char        sa_data[14];
};

/* Host entry structure */
struct hostent {
    char    *h_name;       /* Official name */
    char   **h_aliases;   /* Alias list */
    int      h_addrtype;   /* Address type */
    int      h_length;     /* Address length */
    char   **h_addr_list;  /* List of addresses */
};
#define h_addr h_addr_list[0]

/* Time structures - BSD-compatible */
struct timeval {
    long    tv_sec;   /* Seconds */
    long    tv_usec;  /* Microseconds */
};

struct timezone {
    int     tz_minuteswest;  /* Minutes west of GMT */
    int     tz_dsttime;      /* DST correction type */
};

/* Socket descriptor - wraps Mac OS file reference */
typedef int socket_t;
#define INVALID_SOCKET (-1)
#define SOCKET_ERROR   (-1)

/* Network API - BSD-compatible names */
socket_t socket(int domain, int type, int protocol);
int      connect(socket_t s, const struct sockaddr *addr, size_t addrlen);
int      send(socket_t s, const void *buf, size_t len, int flags);
int      recv(socket_t s, void *buf, size_t len, int flags);
int      closesocket(socket_t s);
struct hostent *gethostbyname(const char *name);

/* Time API - BSD-compatible */
int      gettimeofday(struct timeval *tv, struct timezone *tz);
time_t   time(time_t *t);

/* Memory API - CW/MPW compatible */
void    *malloc(size_t size);
void     free(void *ptr);
void    *memcpy(void *dest, const void *src, size_t n);
void    *memset(void *s, int c, size_t n);
int      memcmp(const void *s1, const void *s2, size_t n);

/* String API */
size_t   strlen(const char *s);
char    *strcpy(char *dest, const char *src);
char    *strncpy(char *dest, const char *src, size_t n);
int      strcmp(const char *s1, const char *s2);
int      strncmp(const char *s1, const char *s2, size_t n);
char    *strchr(const char *s, int c);
void    *memmove(void *dest, const void *src, size_t n);

/* Utility */
uint16_t htons(uint16_t hostshort);
uint32_t htonl(uint32_t hostlong);
uint16_t ntohs(uint16_t netshort);
uint32_t ntohl(uint32_t netlong);

/* Initialization */
int  posix_shim_init(void);
void posix_shim_cleanup(void);

#endif /* POSIX_SHIM_H */
