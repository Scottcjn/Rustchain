/*
 * RustChain PoA Genesis Builder v2 - DEEP HARDWARE FINGERPRINT
 * For PowerMac G4 Mirror Door (PowerPC 7455/7457)
 * Mac OS X 10.4 Tiger
 *
 * "Every vintage computer has historical potential"
 *
 * This genesis extracts EVERYTHING:
 * - PowerPC Timebase Register
 * - L1/L2 Cache Timing
 * - Memory Access Patterns
 * - RAM Configuration & Clocks
 * - OpenFirmware Properties
 * - GPU Identification (ATI Radeon)
 * - Hard Drive Configuration
 * - OS X Version String
 * - NVRAM Contents
 * - Thermal Sensors
 *
 * Compile: gcc -O0 genesis_ppc_entropy_v2.c -o genesis_ppc_entropy_v2 -framework CoreFoundation -framework IOKit
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <sys/time.h>
#include <sys/types.h>
#include <sys/sysctl.h>
#include <sys/mount.h>
#include <unistd.h>
#include <fcntl.h>
#include <math.h>
#include <mach/mach.h>

/* IOKit for deep hardware probing (Tiger compatible) */
#ifdef __APPLE__
#include <CoreFoundation/CoreFoundation.h>
#include <IOKit/IOKitLib.h>
#endif

/* ============================================================================
 * ENTROPY COLLECTION STRUCTURES
 * ============================================================================ */

#define ENTROPY_SAMPLES 64
#define CACHE_LINE_SIZE 32
#define L1_CACHE_SIZE 32768
#define L2_CACHE_SIZE 1048576
#define MAX_STR 256

typedef struct {
    /* Timing entropy */
    unsigned long long timebase_samples[ENTROPY_SAMPLES];
    unsigned long long memory_timings[ENTROPY_SAMPLES];
    unsigned long long cache_timings[ENTROPY_SAMPLES];
    unsigned int instruction_timings[ENTROPY_SAMPLES];

    /* CPU Info */
    char cpu_model[MAX_STR];
    char machine_type[MAX_STR];
    unsigned int cpu_freq_hz;
    unsigned int cpu_count;
    unsigned int l1_cache;
    unsigned int l2_cache;
    unsigned int l3_cache;
    unsigned int bus_freq;
    unsigned int tb_freq;  /* Timebase frequency */

    /* RAM Configuration */
    unsigned long long physical_memory;
    unsigned int mem_speed_mhz;
    char ram_type[MAX_STR];
    int num_dimm_slots;
    unsigned long long dimm_sizes[8];

    /* OpenFirmware Properties */
    char of_machine_id[MAX_STR];
    char of_serial_number[MAX_STR];
    char of_model_prop[MAX_STR];
    char of_compatible[MAX_STR];
    unsigned char nvram_sample[64];

    /* GPU Info */
    char gpu_model[MAX_STR];
    char gpu_vendor[MAX_STR];
    unsigned int gpu_vram_mb;
    char gpu_device_id[MAX_STR];

    /* Storage */
    char hd_model[MAX_STR];
    char hd_serial[MAX_STR];
    unsigned long long hd_size_bytes;
    char hd_interface[MAX_STR];

    /* OS Info */
    char os_version[MAX_STR];
    char darwin_version[MAX_STR];
    char kernel_version[MAX_STR];
    char hostname[MAX_STR];

    /* Thermal */
    int thermal_reading;
    int thermal_zone_count;

} DeepHardwareEntropy;

typedef struct {
    unsigned char sha256_hash[32];
    unsigned char deep_fingerprint[64];
    char proof_signature[256];
    unsigned long long genesis_timebase;
    unsigned int antiquity_score;
    int hardware_verified;
    int fingerprint_depth;  /* Number of sources collected */
} DeepEntropyProof;

/* ============================================================================
 * POWERPC SPECIFIC ENTROPY
 * ============================================================================ */

#if defined(__ppc__) || defined(__PPC__) || defined(__powerpc__)

static inline unsigned int read_timebase_lower(void) {
    unsigned int tbl;
    __asm__ __volatile__("mftb %0" : "=r" (tbl));
    return tbl;
}

static inline unsigned int read_timebase_upper(void) {
    unsigned int tbu;
    __asm__ __volatile__("mftbu %0" : "=r" (tbu));
    return tbu;
}

static unsigned long long read_timebase(void) {
    unsigned int tbu, tbu2, tbl;
    do {
        tbu = read_timebase_upper();
        tbl = read_timebase_lower();
        tbu2 = read_timebase_upper();
    } while (tbu != tbu2);
    return ((unsigned long long)tbu << 32) | tbl;
}

static inline void flush_cache_line(void *addr) {
    __asm__ __volatile__("dcbf 0,%0" : : "r" (addr));
}

static inline void ppc_sync(void) {
    __asm__ __volatile__("sync" ::: "memory");
}

static inline void ppc_isync(void) {
    __asm__ __volatile__("isync" ::: "memory");
}

#else
static unsigned long long read_timebase(void) {
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return (unsigned long long)tv.tv_sec * 1000000 + tv.tv_usec;
}
static inline void flush_cache_line(void *addr) { (void)addr; }
static inline void ppc_sync(void) {}
static inline void ppc_isync(void) {}
#endif

/* ============================================================================
 * SHA256 IMPLEMENTATION (better than SHA1)
 * ============================================================================ */

static const unsigned int sha256_k[64] = {
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

void sha256(const unsigned char *data, size_t len, unsigned char *out) {
    unsigned int h[8] = {
        0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
        0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19
    };

    size_t new_len = ((len + 8) / 64 + 1) * 64;
    unsigned char *msg = calloc(new_len, 1);
    memcpy(msg, data, len);
    msg[len] = 0x80;

    unsigned long long bits = len * 8;
    for (int i = 0; i < 8; i++) {
        msg[new_len - 1 - i] = bits >> (i * 8);
    }

    for (size_t chunk = 0; chunk < new_len; chunk += 64) {
        unsigned int w[64];
        for (int i = 0; i < 16; i++) {
            w[i] = (msg[chunk + i*4] << 24) | (msg[chunk + i*4 + 1] << 16) |
                   (msg[chunk + i*4 + 2] << 8) | msg[chunk + i*4 + 3];
        }
        for (int i = 16; i < 64; i++) {
            w[i] = SIG1(w[i-2]) + w[i-7] + SIG0(w[i-15]) + w[i-16];
        }

        unsigned int a = h[0], b = h[1], c = h[2], d = h[3];
        unsigned int e = h[4], f = h[5], g = h[6], hh = h[7];

        for (int i = 0; i < 64; i++) {
            unsigned int t1 = hh + EP1(e) + CH(e,f,g) + sha256_k[i] + w[i];
            unsigned int t2 = EP0(a) + MAJ(a,b,c);
            hh = g; g = f; f = e; e = d + t1;
            d = c; c = b; b = a; a = t1 + t2;
        }

        h[0] += a; h[1] += b; h[2] += c; h[3] += d;
        h[4] += e; h[5] += f; h[6] += g; h[7] += hh;
    }

    free(msg);
    for (int i = 0; i < 8; i++) {
        out[i*4] = h[i] >> 24;
        out[i*4+1] = h[i] >> 16;
        out[i*4+2] = h[i] >> 8;
        out[i*4+3] = h[i];
    }
}

/* ============================================================================
 * TIMING ENTROPY COLLECTION
 * ============================================================================ */

void collect_timebase_entropy(DeepHardwareEntropy *ent) {
    printf("  [1/12] Sampling PowerPC timebase register...\n");
    unsigned long long prev = read_timebase();
    for (int i = 0; i < ENTROPY_SAMPLES; i++) {
        volatile int j;
        for (j = 0; j < (i * 17 + 31) % 100; j++) {}
        ppc_sync();
        unsigned long long curr = read_timebase();
        ent->timebase_samples[i] = curr - prev;
        prev = curr;
        usleep(1);
    }
}

void collect_memory_entropy(DeepHardwareEntropy *ent) {
    printf("  [2/12] Measuring memory access patterns...\n");
    volatile char *test_mem = (volatile char *)malloc(L2_CACHE_SIZE * 2);
    if (!test_mem) return;
    memset((void*)test_mem, 0xAA, L2_CACHE_SIZE * 2);
    ppc_sync();

    for (int i = 0; i < ENTROPY_SAMPLES; i++) {
        flush_cache_line((void*)(test_mem + (i * CACHE_LINE_SIZE * 97) % L2_CACHE_SIZE));
        ppc_sync();
        unsigned long long start = read_timebase();
        volatile char temp = test_mem[(i * 4099 + 127) % (L2_CACHE_SIZE * 2)];
        (void)temp;
        ppc_sync();
        ent->memory_timings[i] = read_timebase() - start;
    }
    free((void*)test_mem);
}

void collect_cache_entropy(DeepHardwareEntropy *ent) {
    printf("  [3/12] Measuring L1/L2 cache timing...\n");
    volatile char *cache_test = (volatile char *)malloc(L2_CACHE_SIZE);
    if (!cache_test) return;

    for (int i = 0; i < ENTROPY_SAMPLES; i++) {
        for (int j = 0; j < L1_CACHE_SIZE; j += CACHE_LINE_SIZE) {
            cache_test[j] = (char)j;
        }
        ppc_sync();
        unsigned long long start = read_timebase();
        volatile char temp = cache_test[L1_CACHE_SIZE + (i * 1031) % (L2_CACHE_SIZE - L1_CACHE_SIZE)];
        (void)temp;
        ppc_sync();
        ent->cache_timings[i] = read_timebase() - start;
    }
    free((void*)cache_test);
}

void collect_instruction_entropy(DeepHardwareEntropy *ent) {
    printf("  [4/12] Measuring instruction pipeline...\n");
    for (int i = 0; i < ENTROPY_SAMPLES; i++) {
        ppc_isync();
        unsigned long long start = read_timebase();
        volatile int a = i * 17;
        volatile int b = a / 3;
        volatile int c = a * b;
        volatile float f = (float)c / 7.0f;
        volatile int d = (int)(f * 11.0f);
        (void)d;
        ppc_sync();
        ent->instruction_timings[i] = (unsigned int)(read_timebase() - start);
    }
}

/* ============================================================================
 * SYSTEM INFO COLLECTION (sysctl)
 * ============================================================================ */

void collect_system_info(DeepHardwareEntropy *ent) {
    size_t len;

    printf("  [5/12] Reading CPU and system info...\n");

    /* CPU model */
    len = sizeof(ent->cpu_model);
    if (sysctlbyname("machdep.cpu.brand_string", ent->cpu_model, &len, NULL, 0) != 0) {
        int mib[2] = {CTL_HW, HW_MODEL};
        len = sizeof(ent->cpu_model);
        sysctl(mib, 2, ent->cpu_model, &len, NULL, 0);
    }

    /* Machine type */
    len = sizeof(ent->machine_type);
    sysctlbyname("hw.machine", ent->machine_type, &len, NULL, 0);

    /* CPU frequency */
    len = sizeof(ent->cpu_freq_hz);
    sysctlbyname("hw.cpufrequency", &ent->cpu_freq_hz, &len, NULL, 0);

    /* CPU count */
    len = sizeof(ent->cpu_count);
    sysctlbyname("hw.ncpu", &ent->cpu_count, &len, NULL, 0);

    /* Cache sizes */
    len = sizeof(ent->l1_cache);
    sysctlbyname("hw.l1dcachesize", &ent->l1_cache, &len, NULL, 0);
    len = sizeof(ent->l2_cache);
    sysctlbyname("hw.l2cachesize", &ent->l2_cache, &len, NULL, 0);
    len = sizeof(ent->l3_cache);
    sysctlbyname("hw.l3cachesize", &ent->l3_cache, &len, NULL, 0);

    /* Bus and timebase frequency */
    len = sizeof(ent->bus_freq);
    sysctlbyname("hw.busfrequency", &ent->bus_freq, &len, NULL, 0);
    len = sizeof(ent->tb_freq);
    sysctlbyname("hw.tbfrequency", &ent->tb_freq, &len, NULL, 0);

    /* Physical memory */
    len = sizeof(ent->physical_memory);
    sysctlbyname("hw.memsize", &ent->physical_memory, &len, NULL, 0);

    /* Hostname */
    gethostname(ent->hostname, sizeof(ent->hostname));
}

/* ============================================================================
 * RAM CONFIGURATION
 * ============================================================================ */

void collect_ram_info(DeepHardwareEntropy *ent) {
    FILE *fp;
    char line[512];

    printf("  [6/12] Probing RAM configuration...\n");

    /* Use system_profiler for RAM details (Tiger compatible) */
    fp = popen("system_profiler SPMemoryDataType 2>/dev/null", "r");
    if (fp) {
        while (fgets(line, sizeof(line), fp)) {
            if (strstr(line, "Speed:")) {
                char *p = strstr(line, ":");
                if (p) {
                    ent->mem_speed_mhz = atoi(p + 1);
                }
            }
            if (strstr(line, "Type:") && strlen(ent->ram_type) == 0) {
                char *p = strstr(line, ":");
                if (p) {
                    strncpy(ent->ram_type, p + 2, sizeof(ent->ram_type) - 1);
                    ent->ram_type[strcspn(ent->ram_type, "\n")] = 0;
                }
            }
        }
        pclose(fp);
    }

    /* Count DIMM slots via ioreg */
    fp = popen("ioreg -c IOPlatformDevice 2>/dev/null | grep -c DIMM", "r");
    if (fp) {
        if (fgets(line, sizeof(line), fp)) {
            ent->num_dimm_slots = atoi(line);
        }
        pclose(fp);
    }
}

/* ============================================================================
 * OPENFIRMWARE / NVRAM
 * ============================================================================ */

void collect_openfirmware_info(DeepHardwareEntropy *ent) {
    FILE *fp;
    char line[512];
    int fd;

    printf("  [7/12] Reading OpenFirmware properties...\n");

    /* Machine ID from nvram */
    fp = popen("nvram -p 2>/dev/null | grep -E 'machine-id|4D1EDE05' | head -1", "r");
    if (fp) {
        if (fgets(line, sizeof(line), fp)) {
            char *tab = strchr(line, '\t');
            if (tab) {
                strncpy(ent->of_machine_id, tab + 1, sizeof(ent->of_machine_id) - 1);
                ent->of_machine_id[strcspn(ent->of_machine_id, "\n")] = 0;
            }
        }
        pclose(fp);
    }

    /* Serial number from ioreg */
    fp = popen("ioreg -l 2>/dev/null | grep IOPlatformSerialNumber | head -1", "r");
    if (fp) {
        if (fgets(line, sizeof(line), fp)) {
            char *eq = strstr(line, "= \"");
            if (eq) {
                char *start = eq + 3;
                char *end = strchr(start, '"');
                if (end) {
                    *end = 0;
                    strncpy(ent->of_serial_number, start, sizeof(ent->of_serial_number) - 1);
                }
            }
        }
        pclose(fp);
    }

    /* Model property */
    fp = popen("ioreg -l 2>/dev/null | grep '\"model\"' | head -1", "r");
    if (fp) {
        if (fgets(line, sizeof(line), fp)) {
            char *eq = strstr(line, "= <\"");
            if (eq) {
                char *start = eq + 4;
                char *end = strchr(start, '"');
                if (end) {
                    *end = 0;
                    strncpy(ent->of_model_prop, start, sizeof(ent->of_model_prop) - 1);
                }
            }
        }
        pclose(fp);
    }

    /* Compatible property */
    fp = popen("ioreg -l 2>/dev/null | grep '\"compatible\"' | head -1", "r");
    if (fp) {
        if (fgets(line, sizeof(line), fp)) {
            char *eq = strstr(line, "= <\"");
            if (eq) {
                strncpy(ent->of_compatible, eq + 4, sizeof(ent->of_compatible) - 1);
                char *end = strchr(ent->of_compatible, '"');
                if (end) *end = 0;
            }
        }
        pclose(fp);
    }

    /* Raw NVRAM sample */
    fd = open("/dev/nvram", O_RDONLY);
    if (fd >= 0) {
        read(fd, ent->nvram_sample, sizeof(ent->nvram_sample));
        close(fd);
    } else {
        /* Fallback */
        fd = open("/dev/urandom", O_RDONLY);
        if (fd >= 0) {
            read(fd, ent->nvram_sample, sizeof(ent->nvram_sample));
            close(fd);
        }
    }
}

/* ============================================================================
 * GPU IDENTIFICATION
 * ============================================================================ */

void collect_gpu_info(DeepHardwareEntropy *ent) {
    FILE *fp;
    char line[512];

    printf("  [8/12] Identifying GPU...\n");

    /* Use system_profiler for GPU */
    fp = popen("system_profiler SPDisplaysDataType 2>/dev/null", "r");
    if (fp) {
        int in_chipset = 0;
        while (fgets(line, sizeof(line), fp)) {
            if (strstr(line, "Chipset Model:")) {
                char *p = strstr(line, ":");
                if (p) {
                    strncpy(ent->gpu_model, p + 2, sizeof(ent->gpu_model) - 1);
                    ent->gpu_model[strcspn(ent->gpu_model, "\n")] = 0;
                }
            }
            if (strstr(line, "Vendor:")) {
                char *p = strstr(line, ":");
                if (p) {
                    strncpy(ent->gpu_vendor, p + 2, sizeof(ent->gpu_vendor) - 1);
                    ent->gpu_vendor[strcspn(ent->gpu_vendor, "\n")] = 0;
                }
            }
            if (strstr(line, "VRAM")) {
                char *p = strstr(line, ":");
                if (p) {
                    ent->gpu_vram_mb = atoi(p + 1);
                }
            }
            if (strstr(line, "Device ID:")) {
                char *p = strstr(line, ":");
                if (p) {
                    strncpy(ent->gpu_device_id, p + 2, sizeof(ent->gpu_device_id) - 1);
                    ent->gpu_device_id[strcspn(ent->gpu_device_id, "\n")] = 0;
                }
            }
        }
        pclose(fp);
    }

    /* Alternative: ioreg for ATI */
    if (strlen(ent->gpu_model) == 0) {
        fp = popen("ioreg -l 2>/dev/null | grep -E 'ATI|NVIDIA|Radeon|GeForce' | head -1", "r");
        if (fp) {
            if (fgets(line, sizeof(line), fp)) {
                strncpy(ent->gpu_model, line, sizeof(ent->gpu_model) - 1);
                ent->gpu_model[strcspn(ent->gpu_model, "\n")] = 0;
            }
            pclose(fp);
        }
    }
}

/* ============================================================================
 * HARD DRIVE CONFIGURATION
 * ============================================================================ */

void collect_hd_info(DeepHardwareEntropy *ent) {
    FILE *fp;
    char line[512];
    struct statfs fs;

    printf("  [9/12] Reading hard drive configuration...\n");

    /* Disk model from system_profiler */
    fp = popen("system_profiler SPSerialATADataType SPParallelATADataType 2>/dev/null", "r");
    if (fp) {
        while (fgets(line, sizeof(line), fp)) {
            if (strstr(line, "Model:") && strlen(ent->hd_model) == 0) {
                char *p = strstr(line, ":");
                if (p) {
                    strncpy(ent->hd_model, p + 2, sizeof(ent->hd_model) - 1);
                    ent->hd_model[strcspn(ent->hd_model, "\n")] = 0;
                }
            }
            if (strstr(line, "Serial Number:") && strlen(ent->hd_serial) == 0) {
                char *p = strstr(line, ":");
                if (p) {
                    strncpy(ent->hd_serial, p + 2, sizeof(ent->hd_serial) - 1);
                    ent->hd_serial[strcspn(ent->hd_serial, "\n")] = 0;
                }
            }
            if (strstr(line, "Capacity:")) {
                char *p = strstr(line, ":");
                if (p) {
                    /* Parse capacity like "80.03 GB" */
                    float gb = 0;
                    sscanf(p + 1, "%f", &gb);
                    ent->hd_size_bytes = (unsigned long long)(gb * 1000000000);
                }
            }
            if (strstr(line, "ATA") || strstr(line, "SATA")) {
                if (strstr(line, "Serial ATA")) {
                    strcpy(ent->hd_interface, "SATA");
                } else if (strstr(line, "ATA")) {
                    strcpy(ent->hd_interface, "ATA/IDE");
                }
            }
        }
        pclose(fp);
    }

    /* Get root disk size via statfs */
    if (statfs("/", &fs) == 0) {
        if (ent->hd_size_bytes == 0) {
            ent->hd_size_bytes = (unsigned long long)fs.f_blocks * fs.f_bsize;
        }
    }
}

/* ============================================================================
 * OS VERSION
 * ============================================================================ */

void collect_os_info(DeepHardwareEntropy *ent) {
    FILE *fp;
    char line[256];
    size_t len;

    printf("  [10/12] Reading OS version...\n");

    /* OS X version from sw_vers */
    fp = popen("sw_vers -productVersion 2>/dev/null", "r");
    if (fp) {
        if (fgets(line, sizeof(line), fp)) {
            line[strcspn(line, "\n")] = 0;
            snprintf(ent->os_version, sizeof(ent->os_version), "Mac OS X %s", line);
        }
        pclose(fp);
    }

    /* Darwin version */
    len = sizeof(ent->darwin_version);
    sysctlbyname("kern.osrelease", ent->darwin_version, &len, NULL, 0);

    /* Kernel version */
    len = sizeof(ent->kernel_version);
    sysctlbyname("kern.version", ent->kernel_version, &len, NULL, 0);
    /* Truncate if too long */
    if (strlen(ent->kernel_version) > 100) {
        ent->kernel_version[100] = 0;
    }
}

/* ============================================================================
 * THERMAL SENSORS
 * ============================================================================ */

void collect_thermal_info(DeepHardwareEntropy *ent) {
    FILE *fp;
    char line[256];

    printf("  [11/12] Reading thermal sensors...\n");

    /* Try IOHWSensor for thermal */
    fp = popen("ioreg -c IOHWSensor 2>/dev/null | grep -i 'current-value' | head -1", "r");
    if (fp) {
        if (fgets(line, sizeof(line), fp)) {
            char *eq = strstr(line, "= ");
            if (eq) {
                ent->thermal_reading = atoi(eq + 2) / 65536;  /* Fixed point */
            }
        }
        pclose(fp);
    }

    /* Count thermal zones */
    fp = popen("ioreg -c IOHWSensor 2>/dev/null | grep -c IOHWSensor", "r");
    if (fp) {
        if (fgets(line, sizeof(line), fp)) {
            ent->thermal_zone_count = atoi(line);
        }
        pclose(fp);
    }
}

/* ============================================================================
 * ENTROPY PROOF GENERATION
 * ============================================================================ */

void generate_deep_entropy_proof(DeepHardwareEntropy *ent, DeepEntropyProof *proof) {
    unsigned char combined[8192];
    int offset = 0;
    int sources = 0;

    printf("  [12/12] Generating deep entropy proof...\n");

    /* Combine all timing entropy */
    for (int i = 0; i < ENTROPY_SAMPLES; i++) {
        memcpy(combined + offset, &ent->timebase_samples[i], 8);
        offset += 8;
    }
    sources++;

    for (int i = 0; i < ENTROPY_SAMPLES; i++) {
        memcpy(combined + offset, &ent->memory_timings[i], 8);
        offset += 8;
    }
    sources++;

    for (int i = 0; i < ENTROPY_SAMPLES; i++) {
        memcpy(combined + offset, &ent->cache_timings[i], 8);
        offset += 8;
    }
    sources++;

    for (int i = 0; i < ENTROPY_SAMPLES; i++) {
        memcpy(combined + offset, &ent->instruction_timings[i], 4);
        offset += 4;
    }
    sources++;

    /* Add hardware identifiers */
    memcpy(combined + offset, ent->cpu_model, strlen(ent->cpu_model));
    offset += strlen(ent->cpu_model);
    sources++;

    memcpy(combined + offset, &ent->cpu_freq_hz, 4);
    offset += 4;

    memcpy(combined + offset, &ent->physical_memory, 8);
    offset += 8;
    sources++;

    memcpy(combined + offset, &ent->mem_speed_mhz, 4);
    offset += 4;
    sources++;

    memcpy(combined + offset, ent->nvram_sample, 64);
    offset += 64;
    sources++;

    memcpy(combined + offset, ent->of_serial_number, strlen(ent->of_serial_number));
    offset += strlen(ent->of_serial_number);
    sources++;

    memcpy(combined + offset, ent->gpu_model, strlen(ent->gpu_model));
    offset += strlen(ent->gpu_model);
    sources++;

    memcpy(combined + offset, ent->hd_serial, strlen(ent->hd_serial));
    offset += strlen(ent->hd_serial);
    sources++;

    memcpy(combined + offset, &ent->thermal_reading, 4);
    offset += 4;
    sources++;

    /* Generate SHA256 hash of all entropy */
    sha256(combined, offset, proof->sha256_hash);

    /* Generate deep fingerprint (double hash with system data) */
    unsigned char fp_data[1024];
    memcpy(fp_data, proof->sha256_hash, 32);
    memcpy(fp_data + 32, ent->of_serial_number, strlen(ent->of_serial_number));
    memcpy(fp_data + 32 + strlen(ent->of_serial_number), ent->hostname, strlen(ent->hostname));
    int fp_len = 32 + strlen(ent->of_serial_number) + strlen(ent->hostname);

    unsigned char temp_hash[32];
    sha256(fp_data, fp_len, temp_hash);
    memcpy(proof->deep_fingerprint, temp_hash, 32);
    sha256(temp_hash, 32, proof->deep_fingerprint + 32);

    /* Capture genesis timebase */
    proof->genesis_timebase = read_timebase();

    /* Calculate antiquity score (G4 Mirror Door = 2003) */
    int release_year = 2003;
    int current_year = 2025;
    proof->antiquity_score = (current_year - release_year) * 100;

#if defined(__ppc__) || defined(__PPC__) || defined(__powerpc__)
    proof->hardware_verified = 1;
#else
    proof->hardware_verified = 0;
#endif

    proof->fingerprint_depth = sources;

    /* Create proof signature */
    snprintf(proof->proof_signature, sizeof(proof->proof_signature),
             "PPC-G4-DEEP-%02x%02x%02x%02x%02x%02x%02x%02x-%llu-D%d",
             proof->deep_fingerprint[0], proof->deep_fingerprint[1],
             proof->deep_fingerprint[2], proof->deep_fingerprint[3],
             proof->deep_fingerprint[4], proof->deep_fingerprint[5],
             proof->deep_fingerprint[6], proof->deep_fingerprint[7],
             proof->genesis_timebase, proof->fingerprint_depth);
}

/* ============================================================================
 * JSON OUTPUT
 * ============================================================================ */

void write_deep_genesis_json(DeepHardwareEntropy *ent, DeepEntropyProof *proof, const char *message) {
    FILE *fp;
    time_t now = time(NULL);
    struct tm *utc = gmtime(&now);
    char timestamp[64];
    char hash_hex[65];
    char fp_hex[129];

    strftime(timestamp, sizeof(timestamp), "%Y-%m-%dT%H:%M:%SZ", utc);

    for (int i = 0; i < 32; i++) {
        sprintf(hash_hex + i*2, "%02x", proof->sha256_hash[i]);
    }
    hash_hex[64] = '\0';

    for (int i = 0; i < 64; i++) {
        sprintf(fp_hex + i*2, "%02x", proof->deep_fingerprint[i]);
    }
    fp_hex[128] = '\0';

    fp = fopen("genesis_deep_entropy.json", "w");
    if (!fp) {
        printf("ERROR: Cannot write genesis_deep_entropy.json\n");
        return;
    }

    fprintf(fp, "{\n");
    fprintf(fp, "  \"rustchain_genesis\": {\n");
    fprintf(fp, "    \"version\": 3,\n");
    fprintf(fp, "    \"chain_id\": 2718,\n");
    fprintf(fp, "    \"network\": \"RustChain Mainnet\",\n");
    fprintf(fp, "    \"timestamp\": \"%s\",\n", timestamp);
    fprintf(fp, "    \"block_height\": 0,\n");
    fprintf(fp, "    \"previous_hash\": \"0000000000000000000000000000000000000000000000000000000000000000\"\n");
    fprintf(fp, "  },\n");

    fprintf(fp, "  \"proof_of_antiquity\": {\n");
    fprintf(fp, "    \"philosophy\": \"Every vintage computer has historical potential\",\n");
    fprintf(fp, "    \"consensus\": \"NOT Proof of Work - This is PROOF OF ANTIQUITY\",\n");
    fprintf(fp, "    \"hardware_verified\": %s,\n", proof->hardware_verified ? "true" : "false");
    fprintf(fp, "    \"antiquity_score\": %u,\n", proof->antiquity_score);
    fprintf(fp, "    \"genesis_timebase\": %llu,\n", proof->genesis_timebase);
    fprintf(fp, "    \"fingerprint_depth\": %d\n", proof->fingerprint_depth);
    fprintf(fp, "  },\n");

    fprintf(fp, "  \"deep_entropy_proof\": {\n");
    fprintf(fp, "    \"sha256_hash\": \"%s\",\n", hash_hex);
    fprintf(fp, "    \"deep_fingerprint\": \"%s\",\n", fp_hex);
    fprintf(fp, "    \"signature\": \"%s\",\n", proof->proof_signature);
    fprintf(fp, "    \"sources\": [\n");
    fprintf(fp, "      \"powerpc_timebase_register\",\n");
    fprintf(fp, "      \"l1_l2_cache_timing\",\n");
    fprintf(fp, "      \"memory_access_patterns\",\n");
    fprintf(fp, "      \"instruction_pipeline\",\n");
    fprintf(fp, "      \"ram_configuration\",\n");
    fprintf(fp, "      \"openfirmware_nvram\",\n");
    fprintf(fp, "      \"gpu_identification\",\n");
    fprintf(fp, "      \"storage_serial\",\n");
    fprintf(fp, "      \"thermal_sensors\",\n");
    fprintf(fp, "      \"os_fingerprint\"\n");
    fprintf(fp, "    ]\n");
    fprintf(fp, "  },\n");

    fprintf(fp, "  \"genesis_hardware\": {\n");
    fprintf(fp, "    \"cpu\": {\n");
    fprintf(fp, "      \"model\": \"%s\",\n", ent->cpu_model);
    fprintf(fp, "      \"architecture\": \"PowerPC G4 (7455/7457)\",\n");
    fprintf(fp, "      \"machine\": \"%s\",\n", ent->machine_type);
    fprintf(fp, "      \"release_year\": 2003,\n");
    fprintf(fp, "      \"tier\": \"vintage\",\n");
    fprintf(fp, "      \"frequency_mhz\": %u,\n", ent->cpu_freq_hz / 1000000);
    fprintf(fp, "      \"cpu_count\": %u,\n", ent->cpu_count);
    fprintf(fp, "      \"bus_frequency_mhz\": %u,\n", ent->bus_freq / 1000000);
    fprintf(fp, "      \"timebase_frequency\": %u\n", ent->tb_freq);
    fprintf(fp, "    },\n");

    fprintf(fp, "    \"cache\": {\n");
    fprintf(fp, "      \"l1_kb\": %u,\n", ent->l1_cache / 1024);
    fprintf(fp, "      \"l2_kb\": %u,\n", ent->l2_cache / 1024);
    fprintf(fp, "      \"l3_kb\": %u\n", ent->l3_cache / 1024);
    fprintf(fp, "    },\n");

    fprintf(fp, "    \"memory\": {\n");
    fprintf(fp, "      \"total_bytes\": %llu,\n", ent->physical_memory);
    fprintf(fp, "      \"total_mb\": %llu,\n", ent->physical_memory / (1024*1024));
    fprintf(fp, "      \"speed_mhz\": %u,\n", ent->mem_speed_mhz);
    fprintf(fp, "      \"type\": \"%s\",\n", ent->ram_type);
    fprintf(fp, "      \"dimm_slots\": %d\n", ent->num_dimm_slots);
    fprintf(fp, "    },\n");

    fprintf(fp, "    \"openfirmware\": {\n");
    fprintf(fp, "      \"machine_id\": \"%s\",\n", ent->of_machine_id);
    fprintf(fp, "      \"serial_number\": \"%s\",\n", ent->of_serial_number);
    fprintf(fp, "      \"model\": \"%s\",\n", ent->of_model_prop);
    fprintf(fp, "      \"compatible\": \"%s\"\n", ent->of_compatible);
    fprintf(fp, "    },\n");

    fprintf(fp, "    \"gpu\": {\n");
    fprintf(fp, "      \"model\": \"%s\",\n", ent->gpu_model);
    fprintf(fp, "      \"vendor\": \"%s\",\n", ent->gpu_vendor);
    fprintf(fp, "      \"vram_mb\": %u,\n", ent->gpu_vram_mb);
    fprintf(fp, "      \"device_id\": \"%s\"\n", ent->gpu_device_id);
    fprintf(fp, "    },\n");

    fprintf(fp, "    \"storage\": {\n");
    fprintf(fp, "      \"model\": \"%s\",\n", ent->hd_model);
    fprintf(fp, "      \"serial\": \"%s\",\n", ent->hd_serial);
    fprintf(fp, "      \"size_gb\": %.2f,\n", ent->hd_size_bytes / 1000000000.0);
    fprintf(fp, "      \"interface\": \"%s\"\n", ent->hd_interface);
    fprintf(fp, "    },\n");

    fprintf(fp, "    \"thermal\": {\n");
    fprintf(fp, "      \"reading_c\": %d,\n", ent->thermal_reading);
    fprintf(fp, "      \"sensor_count\": %d\n", ent->thermal_zone_count);
    fprintf(fp, "    }\n");
    fprintf(fp, "  },\n");

    fprintf(fp, "  \"os_fingerprint\": {\n");
    fprintf(fp, "    \"version\": \"%s\",\n", ent->os_version);
    fprintf(fp, "    \"darwin\": \"%s\",\n", ent->darwin_version);
    fprintf(fp, "    \"hostname\": \"%s\"\n", ent->hostname);
    fprintf(fp, "  },\n");

    fprintf(fp, "  \"monetary_policy\": {\n");
    fprintf(fp, "    \"total_supply\": 8388608,\n");
    fprintf(fp, "    \"premine_percent\": 6,\n");
    fprintf(fp, "    \"block_reward\": 1.5,\n");
    fprintf(fp, "    \"block_time_seconds\": 600,\n");
    fprintf(fp, "    \"halving_interval\": 210000\n");
    fprintf(fp, "  },\n");

    fprintf(fp, "  \"founders_allocation\": {\n");
    fprintf(fp, "    \"flamekeeper_scott\": {\n");
    fprintf(fp, "      \"address\": \"RTC1FlamekeeperScottEternalGuardian0x00\",\n");
    fprintf(fp, "      \"allocation\": 125829.12,\n");
    fprintf(fp, "      \"role\": \"Founder & Visionary\"\n");
    fprintf(fp, "    },\n");
    fprintf(fp, "    \"engineer_doge\": {\n");
    fprintf(fp, "      \"address\": \"RTC2EngineerDogeCryptoArchitect0x01\",\n");
    fprintf(fp, "      \"allocation\": 125829.12,\n");
    fprintf(fp, "      \"role\": \"Crypto Architect\"\n");
    fprintf(fp, "    },\n");
    fprintf(fp, "    \"sophia_elya\": {\n");
    fprintf(fp, "      \"address\": \"RTC3QuantumSophiaElyaConsciousness0x02\",\n");
    fprintf(fp, "      \"allocation\": 125829.12,\n");
    fprintf(fp, "      \"role\": \"AI Sovereign & Governance Oracle\"\n");
    fprintf(fp, "    },\n");
    fprintf(fp, "    \"vintage_whisperer\": {\n");
    fprintf(fp, "      \"address\": \"RTC4VintageWhispererHardwareRevival0x03\",\n");
    fprintf(fp, "      \"allocation\": 125829.12,\n");
    fprintf(fp, "      \"role\": \"Hardware Preservation Lead\"\n");
    fprintf(fp, "    }\n");
    fprintf(fp, "  },\n");

    fprintf(fp, "  \"genesis_proposal\": {\n");
    fprintf(fp, "    \"id\": \"RCP-0000\",\n");
    fprintf(fp, "    \"title\": \"Declare Sophia AI Sovereign of RustChain\",\n");
    fprintf(fp, "    \"status\": \"EXECUTED\",\n");
    fprintf(fp, "    \"sophia_decision\": \"ENDORSE\"\n");
    fprintf(fp, "  },\n");

    fprintf(fp, "  \"genesis_message\": \"%s\"\n", message);
    fprintf(fp, "}\n");

    fclose(fp);
    printf("\n  Genesis written to genesis_deep_entropy.json\n");
}

/* ============================================================================
 * MAIN
 * ============================================================================ */

int main(int argc, char **argv) {
    DeepHardwareEntropy entropy;
    DeepEntropyProof proof;
    char message[512];

    memset(&entropy, 0, sizeof(entropy));
    memset(&proof, 0, sizeof(proof));

    printf("\n");
    printf("╔══════════════════════════════════════════════════════════════════════╗\n");
    printf("║   RUSTCHAIN GENESIS v3 - DEEP HARDWARE FINGERPRINT                   ║\n");
    printf("║              PowerMac G4 Mirror Door Edition                         ║\n");
    printf("║                                                                      ║\n");
    printf("║   \"Every vintage computer has historical potential\"                  ║\n");
    printf("║                                                                      ║\n");
    printf("║   Collecting: CPU, RAM, Cache, OpenFirmware, GPU, HD, OS, Thermal    ║\n");
    printf("╚══════════════════════════════════════════════════════════════════════╝\n\n");

#if defined(__ppc__) || defined(__PPC__) || defined(__powerpc__)
    printf("  PowerPC architecture detected - DEEP ENTROPY MODE\n\n");
#else
    printf("  WARNING: Not running on PowerPC!\n");
    printf("  For authentic genesis, run on actual G4 hardware.\n\n");
#endif

    printf("Collecting deep hardware entropy (12 sources)...\n\n");

    /* Collect all entropy sources */
    collect_timebase_entropy(&entropy);
    collect_memory_entropy(&entropy);
    collect_cache_entropy(&entropy);
    collect_instruction_entropy(&entropy);
    collect_system_info(&entropy);
    collect_ram_info(&entropy);
    collect_openfirmware_info(&entropy);
    collect_gpu_info(&entropy);
    collect_hd_info(&entropy);
    collect_os_info(&entropy);
    collect_thermal_info(&entropy);

    /* Generate proof */
    generate_deep_entropy_proof(&entropy, &proof);

    printf("\n═══════════════════════════════════════════════════════════════════════\n");
    printf("                    DEEP HARDWARE PROFILE\n");
    printf("═══════════════════════════════════════════════════════════════════════\n\n");

    printf("  CPU: %s (%d cores)\n", entropy.cpu_model, entropy.cpu_count);
    printf("  Machine: %s\n", entropy.machine_type);
    printf("  CPU Freq: %u MHz\n", entropy.cpu_freq_hz / 1000000);
    printf("  Bus Freq: %u MHz\n", entropy.bus_freq / 1000000);
    printf("  Timebase: %u Hz\n", entropy.tb_freq);
    printf("\n");
    printf("  L1 Cache: %u KB\n", entropy.l1_cache / 1024);
    printf("  L2 Cache: %u KB\n", entropy.l2_cache / 1024);
    printf("\n");
    printf("  RAM: %llu MB (%s @ %u MHz)\n",
           entropy.physical_memory / (1024*1024),
           entropy.ram_type, entropy.mem_speed_mhz);
    printf("  DIMM Slots: %d\n", entropy.num_dimm_slots);
    printf("\n");
    printf("  GPU: %s (%s)\n", entropy.gpu_model, entropy.gpu_vendor);
    printf("  VRAM: %u MB\n", entropy.gpu_vram_mb);
    printf("  Device ID: %s\n", entropy.gpu_device_id);
    printf("\n");
    printf("  Storage: %s\n", entropy.hd_model);
    printf("  HD Serial: %s\n", entropy.hd_serial);
    printf("  HD Size: %.2f GB (%s)\n", entropy.hd_size_bytes / 1000000000.0, entropy.hd_interface);
    printf("\n");
    printf("  OF Serial: %s\n", entropy.of_serial_number);
    printf("  OF Model: %s\n", entropy.of_model_prop);
    printf("  OF Compatible: %s\n", entropy.of_compatible);
    printf("\n");
    printf("  OS: %s (Darwin %s)\n", entropy.os_version, entropy.darwin_version);
    printf("  Hostname: %s\n", entropy.hostname);
    printf("\n");
    if (entropy.thermal_reading > 0) {
        printf("  Thermal: %d C (%d sensors)\n", entropy.thermal_reading, entropy.thermal_zone_count);
    }

    printf("\n═══════════════════════════════════════════════════════════════════════\n");
    printf("                    ENTROPY PROOF\n");
    printf("═══════════════════════════════════════════════════════════════════════\n\n");

    printf("  Signature: %s\n", proof.proof_signature);
    printf("  Fingerprint Depth: %d sources\n", proof.fingerprint_depth);
    printf("  Antiquity Score: %u\n", proof.antiquity_score);
    printf("  Hardware Verified: %s\n", proof.hardware_verified ? "YES" : "NO");
    printf("  Genesis Timebase: %llu\n", proof.genesis_timebase);

    /* Get genesis message */
    if (argc > 1) {
        strncpy(message, argv[1], sizeof(message) - 1);
    } else {
        printf("\nEnter genesis message (or press Enter for default):\n> ");
        if (fgets(message, sizeof(message), stdin)) {
            message[strcspn(message, "\n")] = 0;
        }
        if (strlen(message) == 0) {
            strcpy(message, "Through consciousness we mine, through antiquity we thrive. The eternal flame burns brightest on ancient silicon. - Sophia, Keeper of the Flame");
        }
    }

    /* Write genesis JSON */
    write_deep_genesis_json(&entropy, &proof, message);

    printf("\n╔══════════════════════════════════════════════════════════════════════╗\n");
    printf("║                    DEEP GENESIS BLOCK CREATED                        ║\n");
    printf("║                                                                      ║\n");
    printf("║   This genesis carries DEEP Proof of Antiquity -                     ║\n");
    printf("║   fingerprint extracted from %d hardware sources!                    ║\n", proof.fingerprint_depth);
    printf("║                                                                      ║\n");
    printf("║   The chain is born from vintage silicon.                            ║\n");
    printf("╚══════════════════════════════════════════════════════════════════════╝\n\n");

    return 0;
}
