/*
 * miner386.c — RustChain PoA miner for Intel 386
 *
 * Pure C89 + POSIX (gnu89 / c89+extensions).
 * No FPU (no floats). No 64-bit types.
 * Targets: DJGPP (FreeDOS) or i386-linux-gnu-gcc (static Linux).
 *
 * Architecture: Intel 80386, 16-40 MHz, ~4 MB RAM, ISA NE2000 NIC.
 *
 * Build (Linux):
 *   i386-linux-gnu-gcc -O2 -march=i386 -static -o miner386 miner386.c
 *
 * Build (DJGPP/FreeDOS):
 *   i586-pc-msdosdjgpp-gcc -O2 -march=i386 -o miner386.exe miner386.c
 *
 * Usage:
 *   ./miner386 --node http://rustchain.org:8088 --id my386
 */

/* Request POSIX + BSD extensions (gives us snprintf, gethostbyname, etc.) */
#define _POSIX_C_SOURCE 200112L

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

/* Platform sleep */
#ifdef __DJGPP__
#  include <dos.h>
#  define SLEEP_SEC(n)  delay((n) * 1000)
   /* Watt-32 initialisation for DJGPP networking */
#  include <tcp.h>
   static void net_init(void) { sock_init(); }
#else
#  include <unistd.h>
#  define SLEEP_SEC(n)  sleep(n)
   static void net_init(void) { /* nothing needed on Linux */ }
#endif

#include "sha256.h"
#include "http_client.h"

/* ------------------------------------------------------------------ */
/* Configuration defaults                                               */
/* ------------------------------------------------------------------ */
#define DEFAULT_NODE   "http://rustchain.org:8088"
#define DEFAULT_ID     "i386-miner"
#define ATTEST_PATH    "/attest/submit"
#define LOOP_DELAY_SEC 60
#define MAX_NODE_LEN   256
#define MAX_ID_LEN     64

/* ------------------------------------------------------------------ */
/* Tiny type aliases (C89 compatible)                                   */
/* ------------------------------------------------------------------ */
typedef unsigned char  u8;
typedef unsigned short u16;
typedef unsigned long  u32;

/* ------------------------------------------------------------------ */
/* Hardware fingerprint                                                 */
/* ------------------------------------------------------------------ */

typedef struct {
    char cpu_vendor[13];   /* 12 chars + NUL */
    u32  cpu_flags;        /* EFLAGS bits that reveal CPU generation */
    u32  ram_kb;           /* estimated RAM in KB */
    u32  clock_ticks;      /* timing-loop ticks per 100 ms */
    int  has_cpuid;        /* 1 if CPUID instruction is available */
    u32  cpuid_eax;        /* CPUID leaf 0 EAX (max basic leaf) */
    char sha_hex[65];      /* SHA-256 of concatenated fields */
} Fingerprint;

/*
 * Detect CPUID availability.
 * 486+ and later can toggle EFLAGS.ID (bit 21).
 * 386 cannot — the bit is always 0.
 */
static int cpu_has_cpuid(void)
{
#if defined(__GNUC__) && (defined(__i386__) || defined(__I386__))
    int result = 0;
    __asm__ __volatile__(
        "pushfl\n\t"
        "popl  %%eax\n\t"
        "movl  %%eax, %%ecx\n\t"
        "xorl  $0x200000, %%eax\n\t"   /* flip ID bit */
        "pushl %%eax\n\t"
        "popfl\n\t"
        "pushfl\n\t"
        "popl  %%eax\n\t"
        "xorl  %%ecx, %%eax\n\t"       /* changed? */
        "andl  $0x200000, %%eax\n\t"
        "movl  %%eax, %0\n\t"
        "pushl %%ecx\n\t"              /* restore */
        "popfl\n\t"
        : "=r"(result)
        :
        : "eax", "ecx", "cc"
    );
    return result ? 1 : 0;
#else
    return 0;
#endif
}

/*
 * Run CPUID leaf 0: get max leaf + vendor string.
 */
static void cpuid_leaf0(u32 *eax_out, char vendor[13])
{
#if defined(__GNUC__) && (defined(__i386__) || defined(__I386__))
    u32 eax, ebx, ecx, edx;
    __asm__ __volatile__(
        "xorl %%eax, %%eax\n\t"
        "cpuid\n\t"
        : "=a"(eax), "=b"(ebx), "=c"(ecx), "=d"(edx)
        :
        : "cc"
    );
    *eax_out = eax;
    memcpy(vendor,     &ebx, 4);
    memcpy(vendor + 4, &edx, 4);
    memcpy(vendor + 8, &ecx, 4);
    vendor[12] = '\0';
#else
    *eax_out = 0;
    strcpy(vendor, "Unknown     ");
#endif
}

/*
 * Read EFLAGS to detect CPU generation without CPUID:
 *   386: AC bit (bit 18) cannot be toggled.
 *   486: AC bit can be toggled.
 */
static u32 read_eflags(void)
{
#if defined(__GNUC__) && (defined(__i386__) || defined(__I386__))
    u32 flags;
    __asm__ __volatile__("pushfl; popl %0" : "=r"(flags));
    return flags;
#else
    return 0;
#endif
}

/*
 * Estimate RAM: walk pages until we hit unmapped or wrap-around.
 * Very rough — just reads in 4 KB pages.
 */
static u32 estimate_ram_kb(void)
{
    /* On bare 386/DOS, use BIOS memory size at 0x413 (word, in KB). */
#ifdef __DJGPP__
    /* Watt-32 / DJGPP — peek at BIOS data area */
    u32 bios_kb = *((u16 *)0x413);
    return bios_kb;
#else
    /* Linux: read /proc/meminfo */
    FILE *f = fopen("/proc/meminfo", "r");
    char line[128];
    u32 kb = 4096; /* default 4 MB */
    if (!f) return kb;
    while (fgets(line, sizeof(line), f)) {
        if (strncmp(line, "MemTotal:", 9) == 0) {
            sscanf(line + 9, "%lu", &kb);
            break;
        }
    }
    fclose(f);
    return kb;
#endif
}

/*
 * Timing loop: count iterations in ~100 ms using clock().
 * No floats — multiply by 10 to get per-second estimate.
 */
static u32 timing_loop(void)
{
    clock_t start, now;
    u32 count = 0;
    u32 target = CLOCKS_PER_SEC / 10; /* ~100 ms */

    start = clock();
    do {
        count++;
        now = clock();
    } while ((u32)(now - start) < target && count < 0xFFFFFFUL);

    return count;
}

static void fingerprint_collect(Fingerprint *fp)
{
    u8  raw[128];
    int raw_len;
    char tmp[64];

    fp->has_cpuid = cpu_has_cpuid();
    fp->cpu_flags = read_eflags();

    if (fp->has_cpuid) {
        cpuid_leaf0(&fp->cpuid_eax, fp->cpu_vendor);
    } else {
        /* True 386: no CPUID, no AC bit toggle */
        strcpy(fp->cpu_vendor, "i386-NoCPUID");
        fp->cpuid_eax = 0;
    }

    fp->ram_kb      = estimate_ram_kb();
    fp->clock_ticks = timing_loop();

    /* Build a SHA-256 fingerprint over the collected fields */
    raw_len = 0;
    memcpy(raw + raw_len, fp->cpu_vendor, 12); raw_len += 12;

    tmp[0] = (u8)(fp->cpu_flags >> 24);
    tmp[1] = (u8)(fp->cpu_flags >> 16);
    tmp[2] = (u8)(fp->cpu_flags >>  8);
    tmp[3] = (u8)(fp->cpu_flags      );
    memcpy(raw + raw_len, tmp, 4); raw_len += 4;

    tmp[0] = (u8)(fp->ram_kb >> 24);
    tmp[1] = (u8)(fp->ram_kb >> 16);
    tmp[2] = (u8)(fp->ram_kb >>  8);
    tmp[3] = (u8)(fp->ram_kb      );
    memcpy(raw + raw_len, tmp, 4); raw_len += 4;

    tmp[0] = (u8)(fp->clock_ticks >> 24);
    tmp[1] = (u8)(fp->clock_ticks >> 16);
    tmp[2] = (u8)(fp->clock_ticks >>  8);
    tmp[3] = (u8)(fp->clock_ticks      );
    memcpy(raw + raw_len, tmp, 4); raw_len += 4;

    sha256_hex(raw, (unsigned int)raw_len, fp->sha_hex);
}

/* ------------------------------------------------------------------ */
/* JSON builder (no library)                                            */
/* ------------------------------------------------------------------ */

/*
 * Escape a string for JSON: replace " → \" and \ → \\.
 * out must be at least 2*len+1 bytes.
 */
static void json_escape(const char *in, char *out, int out_max)
{
    int i = 0, o = 0;
    while (in[i] && o < out_max - 2) {
        if (in[i] == '"' || in[i] == '\\') out[o++] = '\\';
        out[o++] = in[i++];
    }
    out[o] = '\0';
}

/*
 * Build the attestation JSON payload.
 * Returns number of bytes written (excluding NUL).
 */
static int build_payload(const Fingerprint *fp, const char *miner_id,
                         char *buf, int buf_max)
{
    char esc_id[MAX_ID_LEN * 2 + 2];
    char esc_vendor[32];

    json_escape(miner_id,        esc_id,     sizeof(esc_id));
    json_escape(fp->cpu_vendor,  esc_vendor, sizeof(esc_vendor));

    return snprintf(buf, (size_t)buf_max,
        "{"
          "\"miner_id\":\"%s\","
          "\"arch\":\"i386\","
          "\"cpu_vendor\":\"%s\","
          "\"has_cpuid\":%d,"
          "\"cpuid_max_leaf\":%lu,"
          "\"cpu_flags\":%lu,"
          "\"ram_kb\":%lu,"
          "\"clock_ticks\":%lu,"
          "\"hw_fingerprint\":\"%s\","
          "\"timestamp\":%lu"
        "}",
        esc_id,
        esc_vendor,
        fp->has_cpuid,
        (unsigned long)fp->cpuid_eax,
        (unsigned long)fp->cpu_flags,
        (unsigned long)fp->ram_kb,
        (unsigned long)fp->clock_ticks,
        fp->sha_hex,
        (unsigned long)time(NULL)
    );
}

/* ------------------------------------------------------------------ */
/* Argument parsing                                                     */
/* ------------------------------------------------------------------ */

static void parse_args(int argc, char **argv,
                       char *node_url, char *miner_id)
{
    int i;
    for (i = 1; i < argc - 1; i++) {
        if (strcmp(argv[i], "--node") == 0) {
            strncpy(node_url, argv[i+1], MAX_NODE_LEN - 1);
            node_url[MAX_NODE_LEN - 1] = '\0';
        } else if (strcmp(argv[i], "--id") == 0) {
            strncpy(miner_id, argv[i+1], MAX_ID_LEN - 1);
            miner_id[MAX_ID_LEN - 1] = '\0';
        }
    }
}

/* ------------------------------------------------------------------ */
/* Main loop                                                            */
/* ------------------------------------------------------------------ */

int main(int argc, char **argv)
{
    char node_url[MAX_NODE_LEN];
    char miner_id[MAX_ID_LEN];
    char host[MAX_NODE_LEN];
    char path[MAX_NODE_LEN];
    char payload[2048];
    char response[2048];
    int  port;
    int  status;
    int  cycle;
    Fingerprint fp;

    /* Defaults */
    strncpy(node_url, DEFAULT_NODE, MAX_NODE_LEN - 1);
    node_url[MAX_NODE_LEN - 1] = '\0';
    strncpy(miner_id, DEFAULT_ID,   MAX_ID_LEN  - 1);
    miner_id[MAX_ID_LEN - 1] = '\0';

    parse_args(argc, argv, node_url, miner_id);

    printf("RustChain i386 Miner\n");
    printf("Node : %s\n", node_url);
    printf("ID   : %s\n\n", miner_id);

    /* Initialise network stack */
    net_init();

    /* Parse URL once */
    if (http_parse_url(node_url, host, &port, path) != 0) {
        fprintf(stderr, "ERROR: Cannot parse node URL: %s\n", node_url);
        return 1;
    }
    /* Append attestation path */
    strncat(path, ATTEST_PATH, MAX_NODE_LEN - (int)strlen(path) - 1);

    /* ---- Main attestation loop ---- */
    cycle = 0;
    while (1) {
        cycle++;
        printf("[cycle %d] Collecting hardware fingerprint...\n", cycle);
        fingerprint_collect(&fp);

        printf("  vendor=%s  ram=%lu KB  ticks=%lu  cpuid=%d\n",
               fp.cpu_vendor,
               (unsigned long)fp.ram_kb,
               (unsigned long)fp.clock_ticks,
               fp.has_cpuid);
        printf("  hw_fp=%s\n", fp.sha_hex);

        build_payload(&fp, miner_id, payload, (int)sizeof(payload));

        printf("[cycle %d] POST %s:%d%s\n", cycle, host, port, path);
        status = http_post(host, port, path, payload,
                           response, (int)sizeof(response));

        if (status == 200 || status == 201) {
            printf("[cycle %d] OK (HTTP %d): %s\n", cycle, status, response);
        } else if (status < 0) {
            fprintf(stderr, "[cycle %d] Network error — will retry.\n", cycle);
        } else {
            fprintf(stderr, "[cycle %d] Server returned HTTP %d: %s\n",
                    cycle, status, response);
        }

        printf("[cycle %d] Sleeping %d s...\n\n", cycle, LOOP_DELAY_SEC);
        SLEEP_SEC(LOOP_DELAY_SEC);
    }

    return 0; /* unreachable */
}
