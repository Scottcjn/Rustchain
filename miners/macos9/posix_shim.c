/*
 * posix_shim.c - POSIX Compatibility Shim Implementation for Mac OS 9.2 (PowerPC)
 * 
 * Uses GUSI 2.x (Grand Unified Socket Interface) for BSD socket emulation
 * and Microseconds Toolbox trap for high-resolution timing.
 * 
 * Target: Mac OS 9.2.2 on PowerPC G3/G4
 * Compiler: Metrowerks CodeWarrior Pro 8 or Retro68
 * 
 * BUILD WITH GUSI 2.x:
 *   CodeWarrior: Add GUSI.lib to linker inputs
 *   Retro68:      #include <GUSI.h> and link with -lGUSI
 */

#include "posix_shim.h"
#include <MacTypes.h>
#include <MacTCP.h>
#include <OpenTransport.h>
#include <OpenTransportProviders.h>
#include <GUSI.h>
#include <Events.h>
#include <Timer.h>
#include <Resources.h>
#include <TextUtils.h>
#include <StringCompare.h>

#include <stdlib.h>
#include <string.h>

/* Global errno */
int errno = 0;

/* GUSI context */
static Boolean gGUSIInitialized = false;

/* Socket mapping table - Mac OS 9 uses RefNum, we simulate fd */
#define MAX_SOCKETS 32
static struct {
    Boolean    in_use;
    OTCopyableSocket  refnum;  /* MacTCP socket reference */
    Boolean    is_connected;
    Boolean    is_server;
} socket_table[MAX_SOCKETS];

/* Microseconds trap address - cached at init */
static ProcPtr gMicrosecondsTrap = NULL;
static UnsignedWide gLastMicroseconds = {0, 0};

/* ============================================================
 * INITIALIZATION
 * ============================================================ */

int posix_shim_init(void)
{
    int i;
    
    if (gGUSIInitialized) return 0;
    
    /* Initialize GUSI - Grand Unified Socket Interface */
    /* This provides BSD-compatible socket API via OpenTransport */
    GUSISocketocketAF_INET = true;  /* Enable IPv4 sockets */
    GUSIDefaultSocket = true;
    
    /* Initialize socket table */
    for (i = 0; i < MAX_SOCKETS; i++) {
        socket_table[i].in_use = false;
        socket_table[i].refnum = 0;
        socket_table[i].is_connected = false;
        socket_table[i].is_server = false;
    }
    
    /* Cache Microseconds trap for fast access */
    gMicrosecondsTrap = (ProcPtr)0xA19C;
    
    /* Initialize Tick count for fallback timing */
    InitCursorCtl(nil);
    
    gGUSIInitialized = true;
    return 0;
}

void posix_shim_cleanup(void)
{
    int i;
    
    if (!gGUSIInitialized) return;
    
    /* Close all open sockets */
    for (i = 0; i < MAX_SOCKETS; i++) {
        if (socket_table[i].in_use) {
            closesocket(i);
        }
    }
    
    gGUSIInitialized = false;
}

/* ============================================================
 * SOCKET API - BSD-compatible wrappers using GUSI 2.x
 * ============================================================ */

socket_t socket(int domain, int type, int protocol)
{
    int fd;
    OTSocketRef refnum;
    
    if (!gGUSIInitialized) {
        posix_shim_init();
    }
    
    if (domain != AF_INET) {
        errno = POSIX_EPROTO;
        return INVALID_SOCKET;
    }
    
    /* Find free socket slot */
    for (fd = 0; fd < MAX_SOCKETS; fd++) {
        if (!socket_table[fd].in_use) break;
    }
    if (fd >= MAX_SOCKETS) {
        errno = POSIX_ENOMEM;
        return INVALID_SOCKET;
    }
    
    /* Create GUSI socket - BSD-compatible via OpenTransport */
    /* GUSISocket(domain, type, protocol) returns OT copyable socket */
    refnum = GUSISocket(domain, type, protocol);
    if (refnum == kOTInvalidSocketRef) {
        errno = POSIX_EIO;
        return INVALID_SOCKET;
    }
    
    socket_table[fd].in_use = true;
    socket_table[fd].refnum = refnum;
    socket_table[fd].is_connected = false;
    socket_table[fd].is_server = false;
    
    return fd;
}

int connect(socket_t s, const struct sockaddr *addr, size_t addrlen)
{
    struct sockaddr_in *in_addr;
    InetHost host;
    UInt16 port;
    OSErr err;
    
    if (s < 0 || s >= MAX_SOCKETS || !socket_table[s].in_use) {
        errno = POSIX_EBADF;
        return SOCKET_ERROR;
    }
    
    if (addr == NULL || addrlen < sizeof(struct sockaddr_in)) {
        errno = POSIX_EINVAL;
        return SOCKET_ERROR;
    }
    
    in_addr = (struct sockaddr_in *)addr;
    host = in_addr->sin_addr;   /* Already in network byte order */
    port = in_addr->sin_port;   /* Already in network byte order */
    
    /* GUSI connect - async connect with completion */
    err = GUSIConnect(socket_table[s].refnum, &host, port);
    
    if (err != noErr) {
        errno = POSIX_EIO;
        return SOCKET_ERROR;
    }
    
    socket_table[s].is_connected = true;
    return 0;
}

int send(socket_t s, const void *buf, size_t len, int flags)
{
    long bytesSent;
    OSErr err;
    
    if (s < 0 || s >= MAX_SOCKETS || !socket_table[s].in_use) {
        errno = POSIX_EBADF;
        return SOCKET_ERROR;
    }
    
    if (!socket_table[s].is_connected) {
        errno = POSIX_ENOTCONN;
        return SOCKET_ERROR;
    }
    
    if (buf == NULL || len == 0) {
        return 0;
    }
    
    /* GUSI send - BSD-compatible send */
    err = GUSISend(socket_table[s].refnum, (Ptr)buf, len, flags, &bytesSent);
    
    if (err != noErr) {
        errno = POSIX_EIO;
        return SOCKET_ERROR;
    }
    
    return (int)bytesSent;
}

int recv(socket_t s, void *buf, size_t len, int flags)
{
    long bytesRead;
    OSErr err;
    
    if (s < 0 || s >= MAX_SOCKETS || !socket_table[s].in_use) {
        errno = POSIX_EBADF;
        return SOCKET_ERROR;
    }
    
    if (!socket_table[s].is_connected) {
        errno = POSIX_ENOTCONN;
        return SOCKET_ERROR;
    }
    
    if (buf == NULL) {
        errno = POSIX_EFAULT;
        return SOCKET_ERROR;
    }
    
    /* GUSI recv - BSD-compatible receive */
    err = GUSIRecv(socket_table[s].refnum, (Ptr)buf, len, flags, &bytesRead);
    
    if (err != noErr) {
        /* EAGAIN means no data available yet - non-blocking */
        if (err == eofErr || err == noErr) {
            return (int)bytesRead;
        }
        errno = POSIX_EIO;
        return SOCKET_ERROR;
    }
    
    return (int)bytesRead;
}

int closesocket(socket_t s)
{
    OSErr err;
    
    if (s < 0 || s >= MAX_SOCKETS || !socket_table[s].in_use) {
        errno = POSIX_EBADF;
        return SOCKET_ERROR;
    }
    
    /* GUSI close socket */
    err = GUSICloseSocket(socket_table[s].refnum);
    
    socket_table[s].in_use = false;
    socket_table[s].refnum = 0;
    socket_table[s].is_connected = false;
    
    if (err != noErr) {
        errno = POSIX_EIO;
        return SOCKET_ERROR;
    }
    
    return 0;
}

/* ============================================================
 * DNS - gethostbyname via MacTCP Name Dispatch
 * ============================================================ */

struct hostent *gethostbyname(const char *name)
{
    static struct hostent result;
    static char *h_aliases[1] = { NULL };
    static char *h_addr_list[2] = { NULL, NULL };
    static UInt32 h_addr_storage = 0;
    static char hostname[256];
    static InetHostInfo hostInfo;
    OSErr err;
    
    if (name == NULL || strlen(name) == 0) {
        errno = POSIX_EINVAL;
        return NULL;
    }
    
    /* StrLen already available via CW/MPW Lib */
    if (StrLen(name) >= 255) {
        errno = POSIX_ENOENT;
        return NULL;
    }
    
    /* MacTCP Name-to-IP resolution */
    err := OTInetNameToAddress(name, &hostInfo);
    
    if (err != noErr) {
        errno = POSIX_ENOENT;
        return NULL;
    }
    
    /* Use first resolved address */
    if (hostInfo.addr[0] == nil) {
        errno = POSIX_ENOENT;
        return NULL;
    }
    
    h_addr_storage = hostInfo.addr[0];
    h_addr_list[0] = (char *)&h_addr_storage;
    h_addr_list[1] = NULL;
    
    /* Build result structure */
    result.h_name = hostname;
    strncpy(hostname, name, 255);
    hostname[255] = '\0';
    
    result.h_aliases = h_aliases;
    result.h_addrtype = AF_INET;
    result.h_length = 4;  /* IPv4 = 4 bytes */
    result.h_addr_list = h_addr_list;
    
    return &result;
}

/* ============================================================
 * TIME API - Microseconds Toolbox trap
 * ============================================================ */

time_t time(time_t *t)
{
    struct timeval tv;
    gettimeofday(&tv, NULL);
    
    if (t != NULL) {
        *t = tv.tv_sec;
    }
    return tv.tv_sec;
}

int gettimeofday(struct timeval *tv, struct timezone *tz)
{
    UnsignedWide microseconds;
    UInt64 ticks;
    
    if (tv == NULL) {
        return -1;
    }
    
    /* Use Microseconds trap (0xA19C) for precise timing */
    Microseconds(&gLastMicroseconds);
    microseconds = gLastMicroseconds;
    
    /* Convert to seconds + microseconds */
    tv->tv_sec  = (long)(microseconds.hi / 1000000);
    tv->tv_usec = (long)(microseconds.hi % 1000000);
    
    /* Add low word contribution */
    tv->tv_sec  += (long)(microseconds.lo / 1000000);
    tv->tv_usec += (long)(microseconds.lo % 1000000);
    
    /* Carry overflow in microseconds */
    if (tv->tv_usec >= 1000000) {
        tv->tv_sec++;
        tv->tv_usec -= 1000000;
    }
    
    /* Timezone - Mac OS defaults (PST/PDT not tracked per-process) */
    if (tz != NULL) {
        tz->tz_minuteswest = 480;  /* PST = UTC-8 */
        tz->tz_dsttime = 1;         /* DST in effect Jun-Sep approx */
    }
    
    return 0;
}

/* ============================================================
 * MEMORY API - CW/MPW Standard Library
 * ============================================================ */

/*
 * malloc, free, memcpy, memset, memcmp are provided by
 * the CW/MPW Standard Library (StdCLib).
 * We include wrappers only for type safety.
 */

void *malloc(size_t size)
{
    /* CW malloc uses NewPtr under the hood */
    return NewPtr(size);
}

void free(void *ptr)
{
    if (ptr != NULL) {
        DisposPtr((Ptr)ptr);
    }
}

void *memcpy(void *dest, const void *src, size_t n)
{
    BlockMoveData(src, dest, n);
    return dest;
}

void *memset(void *s, int c, size_t n)
{
    /* CW/MPW: use fills */
    register char *p = (char *)s;
    while (n--) *p++ = (char)c;
    return s;
}

int memcmp(const void *s1, const void *s2, size_t n)
{
    return CompareMem(s1, s2, n);
}

/* ============================================================
 * STRING API - CW/MPW Standard Library
 * ============================================================ */

size_t strlen(const char *s)
{
    return StrLen(s);
}

char *strcpy(char *dest, const char *src)
{
    BlockMoveData(src, dest, StrLen(src) + 1);
    return dest;
}

char *strncpy(char *dest, const char *src, size_t n)
{
    size_t len = StrLen(src);
    if (len > n) len = n;
    BlockMoveData(src, dest, len);
    if (len < n) dest[len] = '\0';
    return dest;
}

int strcmp(const char *s1, const char *s2)
{
    return CompareString(s1, s2, false);
}

int strncmp(const char *s1, const char *s2, size_t n)
{
    return CompareString(s1, s2, true);
}

char *strchr(const char *s, int c)
{
    char *p = (char *)s;
    while (*p) {
        if (*p == c) return p;
        p++;
    }
    return NULL;
}

void *memmove(void *dest, const void *src, size_t n)
{
    /* memmove = safe copy (handle overlap) */
    Ptr tmp;
    tmp = NewPtr(n);
    if (tmp == NULL) return NULL;
    BlockMoveData(src, tmp, n);
    BlockMoveData(tmp, dest, n);
    DisposPtr(tmp);
    return dest;
}

/* ============================================================
 * BYTE ORDER - Network/Host Byte Order
 * ============================================================ */

uint16_t htons(uint16_t hostshort)
{
    /* Mac OS is big-endian, network order is big-endian = no swap needed */
    /* But we include for cross-platform portability */
    return (hostshort >> 8) | (hostshort << 8);
}

uint32_t htonl(uint32_t hostlong)
{
    /* Byte-swap for PowerPC (big-endian to network big-endian - no change) */
    return ((hostlong & 0xFF000000) >> 24) |
           ((hostlong & 0x00FF0000) >> 8)  |
           ((hostlong & 0x0000FF00) << 8)  |
           ((hostlong & 0x000000FF) << 24);
}

uint16_t ntohs(uint16_t netshort)
{
    return htons(netshort);
}

uint32_t ntohl(uint32_t netlong)
{
    return htonl(netlong);
}
