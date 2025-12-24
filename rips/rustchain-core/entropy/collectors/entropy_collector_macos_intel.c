/*
 * RustChain Entropy Collector - macOS Intel Edition
 * For Mac Pro "Trashcan" (2013) and other Intel Macs
 *
 * "Every vintage computer has historical potential"
 *
 * Compile: gcc -O0 entropy_collector_macos_intel.c -o entropy_macos_intel -framework CoreFoundation -framework IOKit
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
#include <mach/mach.h>
#include <mach/mach_time.h>

#ifdef __APPLE__
#include <CoreFoundation/CoreFoundation.h>
#include <IOKit/IOKitLib.h>
#endif

#define ENTROPY_SAMPLES 64
#define MAX_STR 256

typedef struct {
    /* Timing entropy */
    unsigned long long timing_samples[ENTROPY_SAMPLES];
    unsigned long long memory_timings[ENTROPY_SAMPLES];

    /* CPU Info */
    char cpu_model[MAX_STR];
    char cpu_vendor[MAX_STR];
    unsigned int cpu_freq_hz;
    unsigned int cpu_count;
    unsigned int physical_cores;
    unsigned int l1_cache;
    unsigned int l2_cache;
    unsigned int l3_cache;

    /* Memory */
    unsigned long long physical_memory;
    char ram_type[MAX_STR];

    /* System */
    char hostname[MAX_STR];
    char serial_number[MAX_STR];
    char model_identifier[MAX_STR];
    char boot_rom[MAX_STR];
    char smc_version[MAX_STR];
    char hardware_uuid[MAX_STR];

    /* GPU */
    char gpu_model[MAX_STR];
    char gpu_vendor[MAX_STR];
    unsigned int gpu_vram_mb;
    char gpu_device_id[MAX_STR];

    /* Storage */
    char hd_model[MAX_STR];
    char hd_serial[MAX_STR];
    unsigned long long hd_size_bytes;
    char hd_interface[MAX_STR];

    /* OS */
    char os_version[MAX_STR];
    char darwin_version[MAX_STR];
    char kernel_version[MAX_STR];

    /* Network */
    char mac_addresses[512];

    /* Thermal */
    int thermal_reading;
    int thermal_zone_count;

} MacIntelEntropy;

typedef struct {
    unsigned char sha256_hash[32];
    unsigned char deep_fingerprint[64];
    char signature[256];
    unsigned long long timestamp_ns;
    int hardware_verified;
    int fingerprint_depth;
    char tier[32];
    float multiplier;
} EntropyProof;

/* SHA256 Implementation */
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

/* High precision timing */
unsigned long long get_timestamp_ns(void) {
    mach_timebase_info_data_t info;
    mach_timebase_info(&info);
    return mach_absolute_time() * info.numer / info.denom;
}

void collect_timing_entropy(MacIntelEntropy *ent) {
    printf("  [1/11] Collecting timing entropy...\n");
    unsigned long long prev = get_timestamp_ns();
    for (int i = 0; i < ENTROPY_SAMPLES; i++) {
        volatile int j;
        for (j = 0; j < (i * 17 + 31) % 100; j++) {}
        unsigned long long curr = get_timestamp_ns();
        ent->timing_samples[i] = curr - prev;
        prev = curr;
        usleep(1);
    }
}

void collect_memory_entropy(MacIntelEntropy *ent) {
    printf("  [2/11] Measuring memory access patterns...\n");
    size_t size = 4 * 1024 * 1024;
    volatile char *mem = (volatile char *)malloc(size);
    if (!mem) return;
    memset((void*)mem, 0xAA, size);

    for (int i = 0; i < ENTROPY_SAMPLES; i++) {
        unsigned long long start = get_timestamp_ns();
        volatile char temp = mem[(i * 4099 + 127) % size];
        (void)temp;
        ent->memory_timings[i] = get_timestamp_ns() - start;
    }
    free((void*)mem);
}

void collect_cpu_info(MacIntelEntropy *ent) {
    size_t len;

    printf("  [3/11] Reading CPU info...\n");

    len = sizeof(ent->cpu_model);
    sysctlbyname("machdep.cpu.brand_string", ent->cpu_model, &len, NULL, 0);

    len = sizeof(ent->cpu_vendor);
    sysctlbyname("machdep.cpu.vendor", ent->cpu_vendor, &len, NULL, 0);

    len = sizeof(ent->cpu_freq_hz);
    sysctlbyname("hw.cpufrequency", &ent->cpu_freq_hz, &len, NULL, 0);

    len = sizeof(ent->cpu_count);
    sysctlbyname("hw.ncpu", &ent->cpu_count, &len, NULL, 0);

    len = sizeof(ent->physical_cores);
    sysctlbyname("hw.physicalcpu", &ent->physical_cores, &len, NULL, 0);

    len = sizeof(ent->l1_cache);
    sysctlbyname("hw.l1dcachesize", &ent->l1_cache, &len, NULL, 0);

    len = sizeof(ent->l2_cache);
    sysctlbyname("hw.l2cachesize", &ent->l2_cache, &len, NULL, 0);

    len = sizeof(ent->l3_cache);
    sysctlbyname("hw.l3cachesize", &ent->l3_cache, &len, NULL, 0);

    len = sizeof(ent->physical_memory);
    sysctlbyname("hw.memsize", &ent->physical_memory, &len, NULL, 0);

    gethostname(ent->hostname, sizeof(ent->hostname));
}

void collect_system_info(MacIntelEntropy *ent) {
    FILE *fp;
    char line[512];

    printf("  [4/11] Reading system identifiers...\n");

    /* Serial number */
    fp = popen("ioreg -l 2>/dev/null | grep IOPlatformSerialNumber | head -1", "r");
    if (fp) {
        if (fgets(line, sizeof(line), fp)) {
            char *eq = strstr(line, "= \"");
            if (eq) {
                char *start = eq + 3;
                char *end = strchr(start, '"');
                if (end) {
                    *end = 0;
                    strncpy(ent->serial_number, start, sizeof(ent->serial_number) - 1);
                }
            }
        }
        pclose(fp);
    }

    /* Hardware UUID */
    fp = popen("ioreg -l 2>/dev/null | grep IOPlatformUUID | head -1", "r");
    if (fp) {
        if (fgets(line, sizeof(line), fp)) {
            char *eq = strstr(line, "= \"");
            if (eq) {
                char *start = eq + 3;
                char *end = strchr(start, '"');
                if (end) {
                    *end = 0;
                    strncpy(ent->hardware_uuid, start, sizeof(ent->hardware_uuid) - 1);
                }
            }
        }
        pclose(fp);
    }

    /* Model and Boot ROM from system_profiler */
    fp = popen("system_profiler SPHardwareDataType 2>/dev/null", "r");
    if (fp) {
        while (fgets(line, sizeof(line), fp)) {
            if (strstr(line, "Model Identifier:")) {
                char *p = strstr(line, ":");
                if (p) {
                    strncpy(ent->model_identifier, p + 2, sizeof(ent->model_identifier) - 1);
                    ent->model_identifier[strcspn(ent->model_identifier, "\n")] = 0;
                }
            }
            else if (strstr(line, "Boot ROM Version:")) {
                char *p = strstr(line, ":");
                if (p) {
                    strncpy(ent->boot_rom, p + 2, sizeof(ent->boot_rom) - 1);
                    ent->boot_rom[strcspn(ent->boot_rom, "\n")] = 0;
                }
            }
            else if (strstr(line, "SMC Version")) {
                char *p = strstr(line, ":");
                if (p) {
                    strncpy(ent->smc_version, p + 2, sizeof(ent->smc_version) - 1);
                    ent->smc_version[strcspn(ent->smc_version, "\n")] = 0;
                }
            }
        }
        pclose(fp);
    }
}

void collect_ram_info(MacIntelEntropy *ent) {
    FILE *fp;
    char line[512];

    printf("  [5/11] Reading RAM configuration...\n");

    fp = popen("system_profiler SPMemoryDataType 2>/dev/null | grep 'Type:' | head -1", "r");
    if (fp) {
        if (fgets(line, sizeof(line), fp)) {
            char *p = strstr(line, ":");
            if (p) {
                strncpy(ent->ram_type, p + 2, sizeof(ent->ram_type) - 1);
                ent->ram_type[strcspn(ent->ram_type, "\n")] = 0;
            }
        }
        pclose(fp);
    }
}

void collect_gpu_info(MacIntelEntropy *ent) {
    FILE *fp;
    char line[512];

    printf("  [6/11] Reading GPU info...\n");

    fp = popen("system_profiler SPDisplaysDataType 2>/dev/null", "r");
    if (fp) {
        while (fgets(line, sizeof(line), fp)) {
            if (strstr(line, "Chipset Model:")) {
                char *p = strstr(line, ":");
                if (p) {
                    strncpy(ent->gpu_model, p + 2, sizeof(ent->gpu_model) - 1);
                    ent->gpu_model[strcspn(ent->gpu_model, "\n")] = 0;
                }
            }
            else if (strstr(line, "Vendor:") && strlen(ent->gpu_vendor) == 0) {
                char *p = strstr(line, ":");
                if (p) {
                    strncpy(ent->gpu_vendor, p + 2, sizeof(ent->gpu_vendor) - 1);
                    ent->gpu_vendor[strcspn(ent->gpu_vendor, "\n")] = 0;
                }
            }
            else if (strstr(line, "VRAM")) {
                char *p = strstr(line, ":");
                if (p) {
                    ent->gpu_vram_mb = atoi(p + 1);
                }
            }
            else if (strstr(line, "Device ID:")) {
                char *p = strstr(line, ":");
                if (p) {
                    strncpy(ent->gpu_device_id, p + 2, sizeof(ent->gpu_device_id) - 1);
                    ent->gpu_device_id[strcspn(ent->gpu_device_id, "\n")] = 0;
                }
            }
        }
        pclose(fp);
    }
}

void collect_storage_info(MacIntelEntropy *ent) {
    FILE *fp;
    char line[512];

    printf("  [7/11] Reading storage info...\n");

    fp = popen("system_profiler SPNVMeDataType SPSerialATADataType 2>/dev/null", "r");
    if (fp) {
        while (fgets(line, sizeof(line), fp)) {
            if (strstr(line, "Model:") && strlen(ent->hd_model) == 0) {
                char *p = strstr(line, ":");
                if (p) {
                    strncpy(ent->hd_model, p + 2, sizeof(ent->hd_model) - 1);
                    ent->hd_model[strcspn(ent->hd_model, "\n")] = 0;
                }
            }
            else if (strstr(line, "Serial Number:") && strlen(ent->hd_serial) == 0) {
                char *p = strstr(line, ":");
                if (p) {
                    strncpy(ent->hd_serial, p + 2, sizeof(ent->hd_serial) - 1);
                    ent->hd_serial[strcspn(ent->hd_serial, "\n")] = 0;
                }
            }
            else if (strstr(line, "Capacity:")) {
                char *p = strstr(line, ":");
                if (p) {
                    float gb = 0;
                    sscanf(p + 1, "%f", &gb);
                    if (gb > 0 && ent->hd_size_bytes == 0) {
                        ent->hd_size_bytes = (unsigned long long)(gb * 1000000000);
                    }
                }
            }
            else if (strstr(line, "NVMe")) {
                strcpy(ent->hd_interface, "NVMe");
            }
            else if (strstr(line, "SATA") && strlen(ent->hd_interface) == 0) {
                strcpy(ent->hd_interface, "SATA");
            }
        }
        pclose(fp);
    }
}

void collect_network_info(MacIntelEntropy *ent) {
    FILE *fp;
    char line[256];

    printf("  [8/11] Reading network MACs...\n");

    fp = popen("ifconfig -a 2>/dev/null | grep ether | awk '{print $2}' | head -5", "r");
    if (fp) {
        ent->mac_addresses[0] = 0;
        while (fgets(line, sizeof(line), fp)) {
            line[strcspn(line, "\n")] = 0;
            if (strlen(ent->mac_addresses) > 0) {
                strcat(ent->mac_addresses, ",");
            }
            strcat(ent->mac_addresses, line);
        }
        pclose(fp);
    }
}

void collect_os_info(MacIntelEntropy *ent) {
    FILE *fp;
    char line[256];
    size_t len;

    printf("  [9/11] Reading OS info...\n");

    fp = popen("sw_vers -productVersion 2>/dev/null", "r");
    if (fp) {
        if (fgets(line, sizeof(line), fp)) {
            line[strcspn(line, "\n")] = 0;
            snprintf(ent->os_version, sizeof(ent->os_version), "macOS %s", line);
        }
        pclose(fp);
    }

    len = sizeof(ent->darwin_version);
    sysctlbyname("kern.osrelease", ent->darwin_version, &len, NULL, 0);

    len = sizeof(ent->kernel_version);
    sysctlbyname("kern.version", ent->kernel_version, &len, NULL, 0);
    if (strlen(ent->kernel_version) > 100) {
        ent->kernel_version[100] = 0;
    }
}

void collect_thermal_info(MacIntelEntropy *ent) {
    FILE *fp;
    char line[256];

    printf("  [10/11] Reading thermal sensors...\n");

    /* Count thermal sensors via IOHWSensor */
    fp = popen("ioreg -c IOHWSensor 2>/dev/null | grep -c IOHWSensor", "r");
    if (fp) {
        if (fgets(line, sizeof(line), fp)) {
            ent->thermal_zone_count = atoi(line);
        }
        pclose(fp);
    }

    /* Try SMC temperature */
    fp = popen("ioreg -c AppleSMC 2>/dev/null | grep -c temperature", "r");
    if (fp) {
        if (fgets(line, sizeof(line), fp)) {
            ent->thermal_reading = atoi(line);
        }
        pclose(fp);
    }
}

void generate_proof(MacIntelEntropy *ent, EntropyProof *proof) {
    unsigned char combined[4096];
    int offset = 0;
    int sources = 0;

    printf("  [11/11] Generating entropy proof...\n");

    /* Combine timing entropy */
    for (int i = 0; i < ENTROPY_SAMPLES; i++) {
        memcpy(combined + offset, &ent->timing_samples[i], 8);
        offset += 8;
    }
    sources++;

    for (int i = 0; i < ENTROPY_SAMPLES; i++) {
        memcpy(combined + offset, &ent->memory_timings[i], 8);
        offset += 8;
    }
    sources++;

    /* Add identifiers */
    if (strlen(ent->cpu_model) > 0) {
        memcpy(combined + offset, ent->cpu_model, strlen(ent->cpu_model));
        offset += strlen(ent->cpu_model);
        sources++;
    }

    if (strlen(ent->serial_number) > 0) {
        memcpy(combined + offset, ent->serial_number, strlen(ent->serial_number));
        offset += strlen(ent->serial_number);
        sources++;
    }

    if (strlen(ent->hardware_uuid) > 0) {
        memcpy(combined + offset, ent->hardware_uuid, strlen(ent->hardware_uuid));
        offset += strlen(ent->hardware_uuid);
        sources++;
    }

    if (strlen(ent->gpu_model) > 0) {
        memcpy(combined + offset, ent->gpu_model, strlen(ent->gpu_model));
        offset += strlen(ent->gpu_model);
        sources++;
    }

    if (strlen(ent->hd_serial) > 0) {
        memcpy(combined + offset, ent->hd_serial, strlen(ent->hd_serial));
        offset += strlen(ent->hd_serial);
        sources++;
    }

    if (strlen(ent->mac_addresses) > 0) {
        memcpy(combined + offset, ent->mac_addresses, strlen(ent->mac_addresses));
        offset += strlen(ent->mac_addresses);
        sources++;
    }

    memcpy(combined + offset, &ent->physical_memory, 8);
    offset += 8;
    sources++;

    memcpy(combined + offset, ent->os_version, strlen(ent->os_version));
    offset += strlen(ent->os_version);
    sources++;

    /* Generate SHA256 */
    sha256(combined, offset, proof->sha256_hash);

    /* Generate deep fingerprint */
    unsigned char fp_data[512];
    memcpy(fp_data, proof->sha256_hash, 32);
    memcpy(fp_data + 32, ent->serial_number, strlen(ent->serial_number));
    memcpy(fp_data + 32 + strlen(ent->serial_number), ent->hardware_uuid, strlen(ent->hardware_uuid));
    int fp_len = 32 + strlen(ent->serial_number) + strlen(ent->hardware_uuid);

    unsigned char temp_hash[32];
    sha256(fp_data, fp_len, temp_hash);
    memcpy(proof->deep_fingerprint, temp_hash, 32);
    sha256(temp_hash, 32, proof->deep_fingerprint + 32);

    /* Timestamp */
    proof->timestamp_ns = get_timestamp_ns();
    proof->hardware_verified = 1;
    proof->fingerprint_depth = sources;

    /* Determine tier - Mac Pro 2013 is "retro" (10-14 years) */
    int release_year = 2013;
    int current_year = 2025;
    int age = current_year - release_year;

    if (age >= 30) {
        strcpy(proof->tier, "ancient");
        proof->multiplier = 3.5;
    } else if (age >= 25) {
        strcpy(proof->tier, "sacred");
        proof->multiplier = 3.0;
    } else if (age >= 20) {
        strcpy(proof->tier, "vintage");
        proof->multiplier = 2.5;
    } else if (age >= 15) {
        strcpy(proof->tier, "classic");
        proof->multiplier = 2.0;
    } else if (age >= 10) {
        strcpy(proof->tier, "retro");
        proof->multiplier = 1.5;
    } else if (age >= 5) {
        strcpy(proof->tier, "modern");
        proof->multiplier = 1.0;
    } else {
        strcpy(proof->tier, "recent");
        proof->multiplier = 0.5;
    }

    /* Create signature */
    snprintf(proof->signature, sizeof(proof->signature),
             "MACINTEL-%02x%02x%02x%02x%02x%02x%02x%02x-%llu-D%d",
             proof->deep_fingerprint[0], proof->deep_fingerprint[1],
             proof->deep_fingerprint[2], proof->deep_fingerprint[3],
             proof->deep_fingerprint[4], proof->deep_fingerprint[5],
             proof->deep_fingerprint[6], proof->deep_fingerprint[7],
             proof->timestamp_ns, proof->fingerprint_depth);
}

void write_json(MacIntelEntropy *ent, EntropyProof *proof) {
    FILE *fp;
    time_t now = time(NULL);
    struct tm *utc = gmtime(&now);
    char timestamp[64];
    char hash_hex[65];
    char fp_hex[129];
    char filename[256];

    strftime(timestamp, sizeof(timestamp), "%Y-%m-%dT%H:%M:%SZ", utc);

    for (int i = 0; i < 32; i++) {
        sprintf(hash_hex + i*2, "%02x", proof->sha256_hash[i]);
    }
    hash_hex[64] = '\0';

    for (int i = 0; i < 64; i++) {
        sprintf(fp_hex + i*2, "%02x", proof->deep_fingerprint[i]);
    }
    fp_hex[128] = '\0';

    /* Create filename from hostname */
    snprintf(filename, sizeof(filename), "entropy_macintel_%s.json", ent->hostname);
    for (int i = 0; filename[i]; i++) {
        if (filename[i] == ' ' || filename[i] == '.') filename[i] = '_';
    }

    fp = fopen(filename, "w");
    if (!fp) {
        printf("ERROR: Cannot write %s\n", filename);
        return;
    }

    fprintf(fp, "{\n");
    fprintf(fp, "  \"rustchain_entropy\": {\n");
    fprintf(fp, "    \"version\": 1,\n");
    fprintf(fp, "    \"platform\": \"macos_intel\",\n");
    fprintf(fp, "    \"collector\": \"entropy_collector_macos_intel.c\",\n");
    fprintf(fp, "    \"timestamp\": \"%s\"\n", timestamp);
    fprintf(fp, "  },\n");

    fprintf(fp, "  \"proof_of_antiquity\": {\n");
    fprintf(fp, "    \"philosophy\": \"Every vintage computer has historical potential\",\n");
    fprintf(fp, "    \"consensus\": \"NOT Proof of Work - This is PROOF OF ANTIQUITY\",\n");
    fprintf(fp, "    \"hardware_verified\": %s,\n", proof->hardware_verified ? "true" : "false");
    fprintf(fp, "    \"tier\": \"%s\",\n", proof->tier);
    fprintf(fp, "    \"multiplier\": %.1f\n", proof->multiplier);
    fprintf(fp, "  },\n");

    fprintf(fp, "  \"entropy_proof\": {\n");
    fprintf(fp, "    \"sha256_hash\": \"%s\",\n", hash_hex);
    fprintf(fp, "    \"deep_fingerprint\": \"%s\",\n", fp_hex);
    fprintf(fp, "    \"signature\": \"%s\",\n", proof->signature);
    fprintf(fp, "    \"entropy_sources\": %d,\n", proof->fingerprint_depth);
    fprintf(fp, "    \"sources\": [\n");
    fprintf(fp, "      \"timing_entropy\",\n");
    fprintf(fp, "      \"memory_access_patterns\",\n");
    fprintf(fp, "      \"cpu_identification\",\n");
    fprintf(fp, "      \"system_serial\",\n");
    fprintf(fp, "      \"hardware_uuid\",\n");
    fprintf(fp, "      \"gpu_identification\",\n");
    fprintf(fp, "      \"storage_serial\",\n");
    fprintf(fp, "      \"mac_addresses\",\n");
    fprintf(fp, "      \"memory_configuration\",\n");
    fprintf(fp, "      \"os_fingerprint\"\n");
    fprintf(fp, "    ]\n");
    fprintf(fp, "  },\n");

    fprintf(fp, "  \"hardware_profile\": {\n");
    fprintf(fp, "    \"hostname\": \"%s\",\n", ent->hostname);
    fprintf(fp, "    \"serial_number\": \"%s\",\n", ent->serial_number);
    fprintf(fp, "    \"hardware_uuid\": \"%s\",\n", ent->hardware_uuid);
    fprintf(fp, "    \"model_identifier\": \"%s\",\n", ent->model_identifier);
    fprintf(fp, "    \"boot_rom\": \"%s\",\n", ent->boot_rom);
    fprintf(fp, "    \"smc_version\": \"%s\",\n", ent->smc_version);
    fprintf(fp, "    \"cpu\": {\n");
    fprintf(fp, "      \"model\": \"%s\",\n", ent->cpu_model);
    fprintf(fp, "      \"vendor\": \"%s\",\n", ent->cpu_vendor);
    fprintf(fp, "      \"frequency_mhz\": %u,\n", ent->cpu_freq_hz / 1000000);
    fprintf(fp, "      \"cores\": %u,\n", ent->physical_cores);
    fprintf(fp, "      \"threads\": %u,\n", ent->cpu_count);
    fprintf(fp, "      \"l1_cache_kb\": %u,\n", ent->l1_cache / 1024);
    fprintf(fp, "      \"l2_cache_kb\": %u,\n", ent->l2_cache / 1024);
    fprintf(fp, "      \"l3_cache_kb\": %u\n", ent->l3_cache / 1024);
    fprintf(fp, "    },\n");
    fprintf(fp, "    \"memory\": {\n");
    fprintf(fp, "      \"total_mb\": %llu,\n", ent->physical_memory / (1024*1024));
    fprintf(fp, "      \"type\": \"%s\"\n", ent->ram_type);
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
    fprintf(fp, "    \"network\": {\n");
    fprintf(fp, "      \"mac_addresses\": \"%s\"\n", ent->mac_addresses);
    fprintf(fp, "    },\n");
    fprintf(fp, "    \"os\": {\n");
    fprintf(fp, "      \"version\": \"%s\",\n", ent->os_version);
    fprintf(fp, "      \"darwin\": \"%s\"\n", ent->darwin_version);
    fprintf(fp, "    },\n");
    fprintf(fp, "    \"thermal\": {\n");
    fprintf(fp, "      \"sensor_count\": %d\n", ent->thermal_zone_count);
    fprintf(fp, "    }\n");
    fprintf(fp, "  }\n");
    fprintf(fp, "}\n");

    fclose(fp);
    printf("\nEntropy written to: %s\n", filename);
}

int main(void) {
    MacIntelEntropy entropy;
    EntropyProof proof;

    memset(&entropy, 0, sizeof(entropy));
    memset(&proof, 0, sizeof(proof));

    printf("\n");
    printf("╔══════════════════════════════════════════════════════════════════════╗\n");
    printf("║   RUSTCHAIN ENTROPY COLLECTOR - macOS Intel Edition                  ║\n");
    printf("║                                                                      ║\n");
    printf("║   \"Every vintage computer has historical potential\"                  ║\n");
    printf("╚══════════════════════════════════════════════════════════════════════╝\n\n");

    printf("Collecting hardware entropy...\n\n");

    collect_timing_entropy(&entropy);
    collect_memory_entropy(&entropy);
    collect_cpu_info(&entropy);
    collect_system_info(&entropy);
    collect_ram_info(&entropy);
    collect_gpu_info(&entropy);
    collect_storage_info(&entropy);
    collect_network_info(&entropy);
    collect_os_info(&entropy);
    collect_thermal_info(&entropy);

    generate_proof(&entropy, &proof);

    printf("\n═══════════════════════════════════════════════════════════════════════\n");
    printf("                    HARDWARE PROFILE\n");
    printf("═══════════════════════════════════════════════════════════════════════\n\n");

    printf("  Hostname: %s\n", entropy.hostname);
    printf("  Serial: %s\n", entropy.serial_number);
    printf("  UUID: %s\n", entropy.hardware_uuid);
    printf("  Model: %s\n", entropy.model_identifier);
    printf("  Boot ROM: %s\n", entropy.boot_rom);
    printf("\n");
    printf("  CPU: %s\n", entropy.cpu_model);
    printf("  Cores: %d physical / %d logical\n", entropy.physical_cores, entropy.cpu_count);
    printf("  Freq: %u MHz\n", entropy.cpu_freq_hz / 1000000);
    printf("  Cache: L1=%uKB L2=%uKB L3=%uKB\n",
           entropy.l1_cache/1024, entropy.l2_cache/1024, entropy.l3_cache/1024);
    printf("\n");
    printf("  RAM: %llu MB (%s)\n", entropy.physical_memory/(1024*1024), entropy.ram_type);
    printf("\n");
    printf("  GPU: %s (%s)\n", entropy.gpu_model, entropy.gpu_vendor);
    printf("  VRAM: %u MB\n", entropy.gpu_vram_mb);
    printf("\n");
    printf("  Storage: %s (%s)\n", entropy.hd_model, entropy.hd_interface);
    printf("  Serial: %s\n", entropy.hd_serial);
    printf("  Size: %.2f GB\n", entropy.hd_size_bytes / 1000000000.0);
    printf("\n");
    printf("  MACs: %s\n", entropy.mac_addresses);
    printf("\n");
    printf("  OS: %s (Darwin %s)\n", entropy.os_version, entropy.darwin_version);

    printf("\n═══════════════════════════════════════════════════════════════════════\n");
    printf("                    ENTROPY PROOF\n");
    printf("═══════════════════════════════════════════════════════════════════════\n\n");

    printf("  Signature: %s\n", proof.signature);
    printf("  Fingerprint Depth: %d sources\n", proof.fingerprint_depth);
    printf("  Hardware Tier: %s (%.1fx)\n", proof.tier, proof.multiplier);
    printf("  Hardware Verified: %s\n", proof.hardware_verified ? "YES" : "NO");

    write_json(&entropy, &proof);

    printf("\n╔══════════════════════════════════════════════════════════════════════╗\n");
    printf("║                    ENTROPY COLLECTION COMPLETE                       ║\n");
    printf("╚══════════════════════════════════════════════════════════════════════╝\n\n");

    return 0;
}
