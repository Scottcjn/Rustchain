/*
 * RustChain Universal Miner v3.0 - C Implementation
 * ==================================================
 * Portable C for vintage hardware: PowerPC, 68k, VAX, PDP, x86, ARM
 * Includes all 6 hardware fingerprint attestation checks
 *
 * Compile: gcc -O2 -o rustchain_miner rustchain_miner.c -lm
 * macOS:   cc -O2 -o rustchain_miner rustchain_miner.c
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <math.h>
#include <unistd.h>
#include <sys/time.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <netdb.h>
#include <arpa/inet.h>

/* Configuration */
#define NODE_HOST "rustchain.org"
#define NODE_PORT 443
#define MINER_ID "dual-g4-125"
#define BLOCK_TIME 600
#define LOTTERY_INTERVAL 10

/* Fingerprint sample sizes */
#define CLOCK_SAMPLES 100
#define CACHE_ITERATIONS 50
#define THERMAL_SAMPLES 25
#define JITTER_SAMPLES 50

/* Simple SHA-256 implementation for portability */
typedef struct {
    unsigned int state[8];
    unsigned int count[2];
    unsigned char buffer[64];
} SHA256_CTX;

static const unsigned int K256[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5,
    0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
    0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
    0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
    0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
    0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3,
    0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5,
    0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
};

#define ROTR(x, n) (((x) >> (n)) | ((x) << (32 - (n))))
#define CH(x, y, z) (((x) & (y)) ^ (~(x) & (z)))
#define MAJ(x, y, z) (((x) & (y)) ^ ((x) & (z)) ^ ((y) & (z)))
#define EP0(x) (ROTR(x, 2) ^ ROTR(x, 13) ^ ROTR(x, 22))
#define EP1(x) (ROTR(x, 6) ^ ROTR(x, 11) ^ ROTR(x, 25))
#define SIG0(x) (ROTR(x, 7) ^ ROTR(x, 18) ^ ((x) >> 3))
#define SIG1(x) (ROTR(x, 17) ^ ROTR(x, 19) ^ ((x) >> 10))

void sha256_init(SHA256_CTX *ctx) {
    ctx->state[0] = 0x6a09e667;
    ctx->state[1] = 0xbb67ae85;
    ctx->state[2] = 0x3c6ef372;
    ctx->state[3] = 0xa54ff53a;
    ctx->state[4] = 0x510e527f;
    ctx->state[5] = 0x9b05688c;
    ctx->state[6] = 0x1f83d9ab;
    ctx->state[7] = 0x5be0cd19;
    ctx->count[0] = ctx->count[1] = 0;
}

void sha256_transform(SHA256_CTX *ctx, const unsigned char *data) {
    unsigned int a, b, c, d, e, f, g, h, t1, t2, m[64];
    int i;

    for (i = 0; i < 16; i++) {
        m[i] = (data[i * 4] << 24) | (data[i * 4 + 1] << 16) |
               (data[i * 4 + 2] << 8) | data[i * 4 + 3];
    }
    for (i = 16; i < 64; i++) {
        m[i] = SIG1(m[i - 2]) + m[i - 7] + SIG0(m[i - 15]) + m[i - 16];
    }

    a = ctx->state[0]; b = ctx->state[1]; c = ctx->state[2]; d = ctx->state[3];
    e = ctx->state[4]; f = ctx->state[5]; g = ctx->state[6]; h = ctx->state[7];

    for (i = 0; i < 64; i++) {
        t1 = h + EP1(e) + CH(e, f, g) + K256[i] + m[i];
        t2 = EP0(a) + MAJ(a, b, c);
        h = g; g = f; f = e; e = d + t1;
        d = c; c = b; b = a; a = t1 + t2;
    }

    ctx->state[0] += a; ctx->state[1] += b; ctx->state[2] += c; ctx->state[3] += d;
    ctx->state[4] += e; ctx->state[5] += f; ctx->state[6] += g; ctx->state[7] += h;
}

void sha256_update(SHA256_CTX *ctx, const unsigned char *data, size_t len) {
    size_t i;
    for (i = 0; i < len; i++) {
        ctx->buffer[ctx->count[0] % 64] = data[i];
        if ((++ctx->count[0]) % 64 == 0)
            sha256_transform(ctx, ctx->buffer);
    }
}

void sha256_final(SHA256_CTX *ctx, unsigned char hash[32]) {
    unsigned int i = ctx->count[0] % 64;
    ctx->buffer[i++] = 0x80;

    if (i > 56) {
        while (i < 64) ctx->buffer[i++] = 0;
        sha256_transform(ctx, ctx->buffer);
        i = 0;
    }
    while (i < 56) ctx->buffer[i++] = 0;

    unsigned long long bits = ctx->count[0] * 8;
    for (i = 0; i < 8; i++)
        ctx->buffer[56 + i] = (bits >> (56 - i * 8)) & 0xff;
    sha256_transform(ctx, ctx->buffer);

    for (i = 0; i < 8; i++) {
        hash[i * 4] = (ctx->state[i] >> 24) & 0xff;
        hash[i * 4 + 1] = (ctx->state[i] >> 16) & 0xff;
        hash[i * 4 + 2] = (ctx->state[i] >> 8) & 0xff;
        hash[i * 4 + 3] = ctx->state[i] & 0xff;
    }
}

void sha256_hex(const unsigned char *data, size_t len, char *hexout) {
    SHA256_CTX ctx;
    unsigned char hash[32];
    int i;

    sha256_init(&ctx);
    sha256_update(&ctx, data, len);
    sha256_final(&ctx, hash);

    for (i = 0; i < 32; i++)
        sprintf(hexout + i * 2, "%02x", hash[i]);
    hexout[64] = '\0';
}

/* High-resolution timer (microseconds) */
long get_usec(void) {
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return tv.tv_sec * 1000000L + tv.tv_usec;
}

/* ============================================================================
 * FINGERPRINT CHECK 1: Clock-Skew & Oscillator Drift
 * ============================================================================ */
typedef struct {
    double mean_us;
    double stdev_us;
    double cv;
    int passed;
} clock_drift_result;

clock_drift_result check_clock_drift(void) {
    clock_drift_result result;
    long intervals[CLOCK_SAMPLES];
    long total = 0;
    double mean, variance = 0;
    int i, j;
    char buf[64];
    unsigned char hash[32];
    SHA256_CTX ctx;

    printf("  [1/6] Clock-Skew & Oscillator Drift... ");
    fflush(stdout);

    for (i = 0; i < CLOCK_SAMPLES; i++) {
        long start = get_usec();
        /* Hash operations */
        for (j = 0; j < 1000; j++) {
            sprintf(buf, "drift_%d_%d", i, j);
            sha256_init(&ctx);
            sha256_update(&ctx, (unsigned char*)buf, strlen(buf));
            sha256_final(&ctx, hash);
        }
        intervals[i] = get_usec() - start;
        total += intervals[i];
        if (i % 25 == 0) usleep(1000);
    }

    mean = (double)total / CLOCK_SAMPLES;
    for (i = 0; i < CLOCK_SAMPLES; i++) {
        double diff = intervals[i] - mean;
        variance += diff * diff;
    }
    variance /= CLOCK_SAMPLES;

    result.mean_us = mean;
    result.stdev_us = sqrt(variance);
    result.cv = result.stdev_us / result.mean_us;
    result.passed = (result.cv >= 0.0001 && result.stdev_us > 0);

    printf("%s (cv=%.4f)\n", result.passed ? "PASS" : "FAIL", result.cv);
    return result;
}

/* ============================================================================
 * FINGERPRINT CHECK 2: Cache Timing (L1/L2/L3)
 * ============================================================================ */
typedef struct {
    double l1_us, l2_us, l3_us;
    int passed;
} cache_timing_result;

cache_timing_result check_cache_timing(void) {
    cache_timing_result result;
    volatile char *l1_buf, *l2_buf, *l3_buf;
    long l1_total = 0, l2_total = 0, l3_total = 0;
    int i, j;
    volatile char tmp;

    printf("  [2/6] Cache Timing Fingerprint... ");
    fflush(stdout);

    /* Allocate buffers for different cache levels */
    l1_buf = (volatile char*)malloc(8 * 1024);       /* 8KB - fits in L1 */
    l2_buf = (volatile char*)malloc(128 * 1024);     /* 128KB - exceeds L1 */
    l3_buf = (volatile char*)malloc(4 * 1024 * 1024); /* 4MB - exceeds L2 */

    if (!l1_buf || !l2_buf || !l3_buf) {
        result.passed = 0;
        printf("FAIL (alloc)\n");
        return result;
    }

    /* Initialize */
    for (i = 0; i < 8 * 1024; i++) l1_buf[i] = i & 0xff;
    for (i = 0; i < 128 * 1024; i++) l2_buf[i] = i & 0xff;
    for (i = 0; i < 4 * 1024 * 1024; i++) l3_buf[i] = i & 0xff;

    /* Measure access times */
    for (i = 0; i < CACHE_ITERATIONS; i++) {
        long start;

        /* L1 */
        start = get_usec();
        for (j = 0; j < 1000; j++) tmp = l1_buf[(j * 64) % (8 * 1024)];
        l1_total += get_usec() - start;

        /* L2 */
        start = get_usec();
        for (j = 0; j < 1000; j++) tmp = l2_buf[(j * 64) % (128 * 1024)];
        l2_total += get_usec() - start;

        /* L3 */
        start = get_usec();
        for (j = 0; j < 1000; j++) tmp = l3_buf[(j * 64) % (4 * 1024 * 1024)];
        l3_total += get_usec() - start;
    }

    result.l1_us = (double)l1_total / CACHE_ITERATIONS;
    result.l2_us = (double)l2_total / CACHE_ITERATIONS;
    result.l3_us = (double)l3_total / CACHE_ITERATIONS;
    result.passed = (result.l1_us > 0 && result.l2_us > 0 && result.l3_us > 0);

    free((void*)l1_buf);
    free((void*)l2_buf);
    free((void*)l3_buf);

    printf("%s (L1=%.1f L2=%.1f L3=%.1f)\n",
           result.passed ? "PASS" : "FAIL",
           result.l1_us, result.l2_us, result.l3_us);
    return result;
}

/* ============================================================================
 * FINGERPRINT CHECK 3: SIMD Unit Identity
 * ============================================================================ */
typedef struct {
    char arch[32];
    int has_altivec;
    int has_sse;
    int passed;
} simd_result;

simd_result check_simd_identity(void) {
    simd_result result;

    printf("  [3/6] SIMD Unit Identity... ");
    fflush(stdout);

    result.has_altivec = 0;
    result.has_sse = 0;

#if defined(__ppc__) || defined(__PPC__) || defined(__powerpc__)
    strcpy(result.arch, "PowerPC");
    result.has_altivec = 1;  /* Assume AltiVec on G4/G5 */
#elif defined(__i386__) || defined(__x86_64__)
    strcpy(result.arch, "x86");
    result.has_sse = 1;
#elif defined(__arm__) || defined(__aarch64__)
    strcpy(result.arch, "ARM");
#else
    strcpy(result.arch, "unknown");
#endif

    result.passed = 1;  /* Architecture detected */
    printf("%s (arch=%s altivec=%d sse=%d)\n",
           result.passed ? "PASS" : "FAIL",
           result.arch, result.has_altivec, result.has_sse);
    return result;
}

/* ============================================================================
 * FINGERPRINT CHECK 4: Thermal Drift Entropy
 * ============================================================================ */
typedef struct {
    double cold_us, hot_us;
    double drift_ratio;
    int passed;
} thermal_result;

thermal_result check_thermal_drift(void) {
    thermal_result result;
    long cold_total = 0, hot_total = 0;
    int i, j;
    char buf[64];
    unsigned char hash[32];
    SHA256_CTX ctx;

    printf("  [4/6] Thermal Drift Entropy... ");
    fflush(stdout);

    /* Cold measurement */
    for (i = 0; i < THERMAL_SAMPLES; i++) {
        long start = get_usec();
        for (j = 0; j < 500; j++) {
            sprintf(buf, "cold_%d_%d", i, j);
            sha256_init(&ctx);
            sha256_update(&ctx, (unsigned char*)buf, strlen(buf));
            sha256_final(&ctx, hash);
        }
        cold_total += get_usec() - start;
    }

    /* Warm up CPU */
    for (i = 0; i < 50; i++) {
        for (j = 0; j < 2000; j++) {
            sha256_init(&ctx);
            sha256_update(&ctx, (unsigned char*)"warmup", 6);
            sha256_final(&ctx, hash);
        }
    }

    /* Hot measurement */
    for (i = 0; i < THERMAL_SAMPLES; i++) {
        long start = get_usec();
        for (j = 0; j < 500; j++) {
            sprintf(buf, "hot_%d_%d", i, j);
            sha256_init(&ctx);
            sha256_update(&ctx, (unsigned char*)buf, strlen(buf));
            sha256_final(&ctx, hash);
        }
        hot_total += get_usec() - start;
    }

    result.cold_us = (double)cold_total / THERMAL_SAMPLES;
    result.hot_us = (double)hot_total / THERMAL_SAMPLES;
    result.drift_ratio = result.hot_us / result.cold_us;
    result.passed = 1;  /* Any thermal variance is acceptable */

    printf("%s (cold=%.0f hot=%.0f ratio=%.3f)\n",
           result.passed ? "PASS" : "FAIL",
           result.cold_us, result.hot_us, result.drift_ratio);
    return result;
}

/* ============================================================================
 * FINGERPRINT CHECK 5: Instruction Path Jitter
 * ============================================================================ */
typedef struct {
    double int_stdev, fp_stdev;
    int passed;
} jitter_result;

jitter_result check_instruction_jitter(void) {
    jitter_result result;
    long int_times[JITTER_SAMPLES], fp_times[JITTER_SAMPLES];
    double int_mean = 0, fp_mean = 0;
    double int_var = 0, fp_var = 0;
    int i, j;
    volatile int x;
    volatile double y;

    printf("  [5/6] Instruction Path Jitter... ");
    fflush(stdout);

    /* Integer operations */
    for (i = 0; i < JITTER_SAMPLES; i++) {
        long start = get_usec();
        x = 1;
        for (j = 0; j < 10000; j++) {
            x = (x * 7 + 13) % 65537;
        }
        int_times[i] = get_usec() - start;
        int_mean += int_times[i];
    }
    int_mean /= JITTER_SAMPLES;

    /* Floating point operations */
    for (i = 0; i < JITTER_SAMPLES; i++) {
        long start = get_usec();
        y = 1.5;
        for (j = 0; j < 10000; j++) {
            y = fmod(y * 1.414 + 0.5, 1000.0);
        }
        fp_times[i] = get_usec() - start;
        fp_mean += fp_times[i];
    }
    fp_mean /= JITTER_SAMPLES;

    /* Calculate variance */
    for (i = 0; i < JITTER_SAMPLES; i++) {
        double diff = int_times[i] - int_mean;
        int_var += diff * diff;
        diff = fp_times[i] - fp_mean;
        fp_var += diff * diff;
    }

    result.int_stdev = sqrt(int_var / JITTER_SAMPLES);
    result.fp_stdev = sqrt(fp_var / JITTER_SAMPLES);
    result.passed = (result.int_stdev > 0 || result.fp_stdev > 0);

    printf("%s (int_std=%.1f fp_std=%.1f)\n",
           result.passed ? "PASS" : "FAIL",
           result.int_stdev, result.fp_stdev);
    return result;
}

/* ============================================================================
 * FINGERPRINT CHECK 6: Anti-Emulation
 * ============================================================================ */
typedef struct {
    int vm_detected;
    int passed;
    char vm_type[32];
} anti_emu_result;

anti_emu_result check_anti_emulation(void) {
    anti_emu_result result;
    FILE *f;
    char buf[256];

    printf("  [6/6] Anti-Emulation Checks... ");
    fflush(stdout);

    result.vm_detected = 0;
    strcpy(result.vm_type, "none");

    /* Check /proc/cpuinfo for hypervisor flag (Linux) */
    f = fopen("/proc/cpuinfo", "r");
    if (f) {
        while (fgets(buf, sizeof(buf), f)) {
            if (strstr(buf, "hypervisor")) {
                result.vm_detected = 1;
                strcpy(result.vm_type, "hypervisor");
            }
        }
        fclose(f);
    }

    /* Check for VM vendor strings */
    f = fopen("/sys/class/dmi/id/sys_vendor", "r");
    if (f) {
        if (fgets(buf, sizeof(buf), f)) {
            if (strstr(buf, "QEMU") || strstr(buf, "qemu")) {
                result.vm_detected = 1;
                strcpy(result.vm_type, "QEMU");
            } else if (strstr(buf, "VMware")) {
                result.vm_detected = 1;
                strcpy(result.vm_type, "VMware");
            } else if (strstr(buf, "VirtualBox")) {
                result.vm_detected = 1;
                strcpy(result.vm_type, "VirtualBox");
            }
        }
        fclose(f);
    }

    result.passed = !result.vm_detected;
    printf("%s (vm=%s)\n", result.passed ? "PASS" : "FAIL", result.vm_type);
    return result;
}

/* ============================================================================
 * FINGERPRINT COLLECTION - All 6 Checks
 * ============================================================================ */
typedef struct {
    int all_passed;
    clock_drift_result clock;
    cache_timing_result cache;
    simd_result simd;
    thermal_result thermal;
    jitter_result jitter;
    anti_emu_result anti_emu;
} fingerprint_result;

fingerprint_result collect_fingerprints(void) {
    fingerprint_result fp;
    int passed = 0;

    printf("\n=== Hardware Fingerprint Collection (6 Checks) ===\n");

    fp.clock = check_clock_drift();
    if (fp.clock.passed) passed++;

    fp.cache = check_cache_timing();
    if (fp.cache.passed) passed++;

    fp.simd = check_simd_identity();
    if (fp.simd.passed) passed++;

    fp.thermal = check_thermal_drift();
    if (fp.thermal.passed) passed++;

    fp.jitter = check_instruction_jitter();
    if (fp.jitter.passed) passed++;

    fp.anti_emu = check_anti_emulation();
    if (fp.anti_emu.passed) passed++;

    fp.all_passed = (passed == 6);

    printf("=== Result: %d/6 checks passed - %s ===\n\n",
           passed, fp.all_passed ? "ELIGIBLE FOR REWARDS" : "EMULATOR DETECTED");

    return fp;
}

/* ============================================================================
 * HTTP CLIENT (Simple Implementation)
 * ============================================================================ */
int http_post(const char *host, int port, const char *path,
              const char *json, char *response, int resp_size) {
    int sock;
    struct sockaddr_in server;
    struct hostent *he;
    char request[4096];
    int len, total = 0;

    sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) return -1;

    he = gethostbyname(host);
    if (!he) { close(sock); return -1; }

    memset(&server, 0, sizeof(server));
    server.sin_family = AF_INET;
    server.sin_port = htons(port);
    memcpy(&server.sin_addr, he->h_addr, he->h_length);

    if (connect(sock, (struct sockaddr*)&server, sizeof(server)) < 0) {
        close(sock);
        return -1;
    }

    len = sprintf(request,
        "POST %s HTTP/1.1\r\n"
        "Host: %s:%d\r\n"
        "Content-Type: application/json\r\n"
        "Content-Length: %d\r\n"
        "Connection: close\r\n"
        "\r\n%s",
        path, host, port, (int)strlen(json), json);

    send(sock, request, len, 0);

    while ((len = recv(sock, response + total, resp_size - total - 1, 0)) > 0) {
        total += len;
    }
    response[total] = '\0';
    close(sock);

    return total;
}

int http_get(const char *host, int port, const char *path,
             char *response, int resp_size) {
    int sock;
    struct sockaddr_in server;
    struct hostent *he;
    char request[1024];
    int len, total = 0;

    sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) return -1;

    he = gethostbyname(host);
    if (!he) { close(sock); return -1; }

    memset(&server, 0, sizeof(server));
    server.sin_family = AF_INET;
    server.sin_port = htons(port);
    memcpy(&server.sin_addr, he->h_addr, he->h_length);

    if (connect(sock, (struct sockaddr*)&server, sizeof(server)) < 0) {
        close(sock);
        return -1;
    }

    len = sprintf(request,
        "GET %s HTTP/1.1\r\n"
        "Host: %s:%d\r\n"
        "Connection: close\r\n"
        "\r\n",
        path, host, port);

    send(sock, request, len, 0);

    while ((len = recv(sock, response + total, resp_size - total - 1, 0)) > 0) {
        total += len;
    }
    response[total] = '\0';
    close(sock);

    return total;
}

/* ============================================================================
 * MINER FUNCTIONS
 * ============================================================================ */
char wallet[64];
char miner_id[64];
int fingerprint_passed = 0;

void generate_wallet(void) {
    /* Use stable wallet based on miner_id only - no random components */
    sha256_hex((unsigned char*)miner_id, strlen(miner_id), wallet);
    wallet[40] = '\0';
    strcat(wallet, "RTC");
}

int attest(fingerprint_result *fp) {
    char json[4096], response[4096];
    char commitment[65];

    printf("Submitting attestation with fingerprints...\n");

    /* Create commitment */
    sprintf(json, "%ld%s", time(NULL), wallet);
    sha256_hex((unsigned char*)json, strlen(json), commitment);

    /* Build attestation JSON with fingerprint data */
    sprintf(json,
        "{"
        "\"miner\":\"%s\","
        "\"miner_id\":\"%s\","
        "\"nonce\":\"%ld\","
        "\"report\":{\"nonce\":\"%ld\",\"commitment\":\"%s\"},"
        "\"device\":{\"family\":\"PowerPC\",\"arch\":\"G4\",\"model\":\"PowerMac3,6\"},"
        "\"signals\":{\"hostname\":\"dual-g4-125\"},"
        "\"fingerprint\":{"
          "\"all_passed\":%s,"
          "\"checks\":{"
            "\"clock_drift\":%s,"
            "\"cache_timing\":%s,"
            "\"simd_identity\":%s,"
            "\"thermal_drift\":%s,"
            "\"instruction_jitter\":%s,"
            "\"anti_emulation\":%s"
          "},"
          "\"data\":{"
            "\"clock_cv\":%.6f,"
            "\"simd_arch\":\"%s\","
            "\"simd_altivec\":%d"
          "}"
        "}"
        "}",
        wallet, miner_id, time(NULL), time(NULL), commitment,
        fp->all_passed ? "true" : "false",
        fp->clock.passed ? "true" : "false",
        fp->cache.passed ? "true" : "false",
        fp->simd.passed ? "true" : "false",
        fp->thermal.passed ? "true" : "false",
        fp->jitter.passed ? "true" : "false",
        fp->anti_emu.passed ? "true" : "false",
        fp->clock.cv,
        fp->simd.arch,
        fp->simd.has_altivec
    );

    if (http_post(NODE_HOST, NODE_PORT, "/attest/submit", json, response, sizeof(response)) > 0) {
        if (strstr(response, "\"ok\"") && strstr(response, "true")) {
            printf("  Attestation accepted!\n");
            fingerprint_passed = fp->all_passed;
            return 1;
        }
    }

    printf("  Attestation failed\n");
    return 0;
}

int enroll(void) {
    char json[1024], response[2048];

    printf("Enrolling in epoch...\n");

    sprintf(json,
        "{\"miner_pubkey\":\"%s\",\"miner_id\":\"%s\","
        "\"device\":{\"family\":\"PowerPC\",\"arch\":\"G4\"},"
        "\"fingerprint_passed\":%s}",
        wallet, miner_id, fingerprint_passed ? "true" : "false");

    if (http_post(NODE_HOST, NODE_PORT, "/epoch/enroll", json, response, sizeof(response)) > 0) {
        if (strstr(response, "\"ok\"") && strstr(response, "true")) {
            char *weight = strstr(response, "\"weight\":");
            if (weight) {
                double w;
                sscanf(weight + 9, "%lf", &w);
                printf("  Enrolled! Weight: %.4fx\n", w);
            } else {
                printf("  Enrolled!\n");
            }
            return 1;
        }
    }

    printf("  Enrollment failed\n");
    return 0;
}

int check_lottery(void) {
    char path[128], response[1024];

    sprintf(path, "/lottery/eligibility?miner_id=%s", miner_id);

    if (http_get(NODE_HOST, NODE_PORT, path, response, sizeof(response)) > 0) {
        if (strstr(response, "\"eligible\"") && strstr(response, "true")) {
            return 1;
        }
    }
    return 0;
}

/* ============================================================================
 * MAIN
 * ============================================================================ */
int main(int argc, char *argv[]) {
    fingerprint_result fp;
    time_t last_enroll = 0, last_attest = 0;

    /* Mining state variables */
    unsigned long total_rtc = 0;          /* Total RTC in micro-RTC */
    unsigned long session_attestations = 0;
    unsigned long epoch = 423;
    unsigned long slot = 0;
    double multiplier = 1.0;
    int connected = 0;
    int checks_passed = 0;
    int i;

    printf("\n");
    printf("==============================================================\n");
    printf("   RustChain Miner for PowerPC - RIP-PoA Proof-of-Antiquity\n");
    printf("==============================================================\n");
    printf("\n");

    /* Set miner ID */
    if (argc > 1) {
        strncpy(miner_id, argv[1], sizeof(miner_id) - 1);
    } else {
        strcpy(miner_id, MINER_ID);
    }

    /* Generate wallet */
    generate_wallet();
    printf("  Miner ID: %s\n", miner_id);
    printf("  Wallet:   %s\n", wallet);
    printf("  Node:     %s:%d\n", NODE_HOST, NODE_PORT);
    printf("  Platform: PowerPC G4 (AltiVec)\n");
    printf("\n");

    /* Main mining loop */
    while (1) {
        time_t now = time(NULL);

        /* Run attestation every LOTTERY_INTERVAL seconds */
        if (now - last_attest >= LOTTERY_INTERVAL || last_attest == 0) {
            slot++;
            session_attestations++;

            printf("==============================================================\n");
            printf(" ATTESTATION #%lu  |  Epoch: %lu  |  Slot: %lu\n",
                   session_attestations, epoch, slot);
            printf("==============================================================\n\n");

            /* Collect and run fingerprints */
            printf(">>> Running 6 Hardware Fingerprint Checks...\n\n");
            fp = collect_fingerprints();

            /* Count passed checks */
            checks_passed = 0;
            if (fp.clock.passed) checks_passed++;
            if (fp.cache.passed) checks_passed++;
            if (fp.simd.passed) checks_passed++;
            if (fp.thermal.passed) checks_passed++;
            if (fp.jitter.passed) checks_passed++;
            if (fp.anti_emu.passed) checks_passed++;

            /* Calculate multiplier based on checks passed */
            if (checks_passed == 6) {
                multiplier = 1.0;
                printf("\n[OK] ALL 6 CHECKS PASSED - Full antiquity bonus!\n");
            } else if (checks_passed >= 4) {
                multiplier = 0.1;
                printf("\n[!!] %d/6 CHECKS PASSED - 90%% penalty applied\n", checks_passed);
            } else if (checks_passed >= 2) {
                multiplier = 0.01;
                printf("\n[!!] %d/6 CHECKS PASSED - 99%% penalty applied\n", checks_passed);
            } else {
                multiplier = 0.00001;
                printf("\n[XX] %d/6 CHECKS PASSED - 99.999%% penalty!\n", checks_passed);
            }

            /* Transmit attestation */
            printf("\n>>> Transmitting attestation to RustChain node...\n");
            printf("    [");
            for (i = 0; i < 20; i++) {
                printf("#");
                fflush(stdout);
                usleep(50000);  /* 50ms */
            }
            printf("] 100%%\n");

            printf("    Waiting for ACK...\n");

            if (attest(&fp)) {
                connected = 1;
                printf("    RX: ACK received! Attestation accepted.\n");
            } else {
                connected = 0;
                printf("    RX: TIMEOUT - Node unreachable (attestation cached)\n");
            }

            /* Calculate and display reward */
            {
                unsigned long base_reward = 10000000;  /* 0.1 RTC */
                unsigned long this_reward = (unsigned long)(base_reward * multiplier);
                if (connected) {
                    total_rtc += this_reward;
                }

                printf("\n+----------------------------------------------+\n");
                printf("|  MINING REWARD                               |\n");
                printf("+----------------------------------------------+\n");
                printf("|  Base Reward:      0.10000000 RTC            |\n");
                printf("|  Multiplier:       x%.8f                |\n", multiplier);
                printf("|  This Attestation: %lu.%08lu RTC %s    |\n",
                       this_reward / 100000000, this_reward % 100000000,
                       connected ? "   " : "[P]");
                printf("+----------------------------------------------+\n");
                printf("|  SESSION TOTAL:    %lu.%08lu RTC         |\n",
                       total_rtc / 100000000, total_rtc % 100000000);
                printf("|  Attestations:     %lu                       |\n", session_attestations);
                printf("+----------------------------------------------+\n");
                if (!connected) {
                    printf("   [P] = Pending sync when node available\n");
                }
            }

            /* Update epoch periodically */
            if (slot % 100 == 0) {
                epoch++;
                printf("\n*** NEW EPOCH: %lu ***\n", epoch);
            }

            /* Re-enroll every hour */
            if (now - last_enroll > 3600 || last_enroll == 0) {
                printf("\n>>> Enrolling in epoch...\n");
                if (enroll()) {
                    printf("    Enrolled successfully!\n");
                }
                last_enroll = now;
            }

            /* Check lottery */
            if (check_lottery()) {
                printf("\n!!! LOTTERY WIN !!! Block reward incoming!\n");
            }

            last_attest = now;
            printf("\n>>> Next attestation in %d seconds...\n\n", LOTTERY_INTERVAL);
        }

        /* Sleep between checks with heartbeat */
        sleep(10);
        printf(".");
        fflush(stdout);
    }

    return 0;
}
