#include "fingerprint.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static char *get_env(const char *name) {
    return getenv(name) ? getenv(name) : "";
}

int fingerprint_detect_cpuid(void) {
    char *cpu_env = get_env("CPU");
    char *proc_env = get_env("PROCESSOR_IDENTIFIER");
    
    if (strstr(cpu_env, "386") || strstr(proc_env, "386")) return 0;
    if (strstr(cpu_env, "486") || strstr(proc_env, "486")) return 1;
    if (strstr(cpu_env, "Pentium") || strstr(proc_env, "Pentium")) return 1;
    
    FILE *fp = popen("CPU 2>NUL", "r");
    if (fp) {
        char buf[128];
        if (fgets(buf, sizeof(buf), fp)) {
            if (strstr(buf, "386")) { pclose(fp); return 0; }
            if (strstr(buf, "486") || strstr(buf, "586")) { pclose(fp); return 1; }
        }
        pclose(fp);
    }
    
    return 0;
}

int fingerprint_detect_fpu(void) {
    char *coproc_env = get_env("COPROCESSOR");
    if (strstr(cocoproc_env, "387")) return 1;
    
    FILE *fp = popen("FPU 2>NUL", "r");
    if (fp) {
        char buf[128];
        if (fgets(buf, sizeof(buf), fp)) {
            if (strstr(buf, "present") || strstr(buf, "387")) { pclose(fp); return 1; }
        }
        pclose(fp);
    }
    
    return 0;
}

const char *fingerprint_get_mac(void) {
    static char mac[18] = "00:00:00:00:00:01";
    char *env_mac = get_env("NE2000_MAC");
    if (env_mac && strlen(env_mac) == 17) {
        strcpy(mac, env_mac);
        return mac;
    }
    
    FILE *fp = fopen("C:\\MTCP\\MTCPDCFG", "r");
    if (fp) {
        char buf[256];
        while (fgets(buf, sizeof(buf), fp)) {
            if (strncmp(buf, "ETHERNET_ADDRESS=", 17) == 0) {
                char *p = buf + 17;
                char *end = p + strlen(p) - 1;
                while (end > p && (*end == '\n' || *end == '\r')) *end-- = '\0';
                if (strlen(p) == 17) strcpy(mac, p);
                break;
            }
        }
        fclose(fp);
    }
    
    return mac;
}

static void get_hostname(char *hostname, int max_len) {
    const char *src = get_env("HOSTNAME");
    if (!src || !*src) src = get_env("COMPUTERNAME");
    if (!src || !*src) src = "RUSTCHAIN-386";
    
    int i, j = 0;
    for (i = 0; i < max_len - 1 && src[i]; i++) {
        if ((src[i] >= 'A' && src[i] <= 'Z') ||
            (src[i] >= 'a' && src[i] <= 'z') ||
            (src[i] >= '0' && src[i] <= '9') ||
            src[i] == '-' || src[i] == '_') {
            hostname[j++] = src[i];
        }
    }
    hostname[j] = '\0';
    if (j == 0) strcpy(hostname, "RUSTCHAIN-386");
}

static int detect_memory_kb(void) {
    int mem_kb = 640;
    FILE *fp = popen("MEM 2>NUL", "r");
    if (fp) {
        char buf[256];
        while (fgets(buf, sizeof(buf), fp)) {
            int kb;
            if (sscanf(buf, "%dK Conventional", &kb) == 1) {
                mem_kb = kb;
                break;
            }
        }
        pclose(fp);
    }
    return mem_kb;
}

void fingerprint_collect(fingerprint_t *fp) {
    fp->has_cpuid = fingerprint_detect_cpuid();
    
    if (fp->has_cpuid) {
        FILE *fp_cpu = popen("CPU 2>NUL", "r");
        if (fp_cpu) {
            char buf[128];
            if (fgets(buf, sizeof(buf), fp_cpu)) {
                strncpy(fp->cpu_type, buf, sizeof(fp->cpu_type) - 1);
                fp->cpu_type[sizeof(fp->cpu_type) - 1] = '\0';
            } else {
                strcpy(fp->cpu_type, "Intel 80486+");
            }
            pclose(fp_cpu);
        } else {
            strcpy(fp->cpu_type, "Intel 80486+");
        }
    } else {
        strcpy(fp->cpu_type, "Intel 80386DX");
    }
    
    fp->cpuid_result = fp->has_cpuid ? 0xFFFF : 0;
    fp->has_387 = fingerprint_detect_fpu();
    strcpy(fp->fpu_type, fp->has_387 ? "Intel 80387" : "none");
    fp->memory_kb = detect_memory_kb();
    fp->cache_kb = 0;
    fp->bus_speed_mhz = 8;
    strcpy(fp->mac, fingerprint_get_mac());
    get_hostname(fp->hostname, sizeof(fp->hostname));
}
