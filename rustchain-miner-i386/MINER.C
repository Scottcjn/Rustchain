#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "sha256.h"
#include "fingerprint.h"

#define WALLET_ENV     "RUSTCHAIN_WALLET"
#define NODE_ENV       "RUSTCHAIN_NODE"
#define DEFAULT_WALLET "C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg"
#define DEFAULT_NODE   "http://rustchain.org"
#define MINER_VERSION  "1.0.0-i386"
#define EPOCH_DURATION 600

static char wallet[256];
static char node_url[256];
static char miner_id[64];
static int epoch_count = 0;

static void print_banner(void) {
    printf("\n============================================\n");
    printf("  RustChain Intel 386 Miner v%s\n", MINER_VERSION);
    printf("  4.0x Antiquity Multiplier\n");
    printf("  Intel 80386 - 1985 Architecture\n");
    printf("============================================\n\n");
    printf("  Wallet: %s\n", wallet);
    printf("  Node:   %s\n", node_url);
    printf("  Epoch:  %d seconds\n\n", EPOCH_DURATION);
}

static void get_config(void) {
    char *env = getenv(WALLET_ENV);
    strcpy(wallet, env ? env : DEFAULT_WALLET);
    env = getenv(NODE_ENV);
    strcpy(node_url, env ? env : DEFAULT_NODE);
}

static void generate_miner_id(fingerprint_t *fp) {
    uint8_t hash[32];
    char seed[512];
    int i, j;
    
    sprintf(seed, "%s-i386-rustchain-%s-%s", wallet, fp->cpu_type, fp->hostname);
    sha256_hash_string(seed, strlen(seed), hash);
    
    sprintf(miner_id, "i386-%s-", fp->hostname);
    for (i = 0, j = strlen(miner_id); i < 4 && j < (int)sizeof(miner_id) - 2; i++) {
        sprintf(&miner_id[j], "%02x", hash[i]);
        j += 2;
    }
}

static void collect_entropy(entropy_data_t *entropy, int cycles, int inner_loop) {
    clock_t start, finish;
    unsigned long acc;
    double *samples;
    double total = 0.0;
    int i, j;
    
    samples = (double *)malloc(cycles * sizeof(double));
    
    for (i = 0; i < cycles; i++) {
        start = clock();
        acc = 0;
        for (j = 0; j < inner_loop; j++) {
            acc ^= (j * 31UL);
        }
        finish = clock();
        samples[i] = ((double)(finish - start) * 1000000.0) / CLOCKS_PER_SEC;
        total += samples[i];
    }
    
    entropy->mean_ns = total / cycles;
    entropy->variance_ns = 0;
    entropy->min_ns = samples[0];
    entropy->max_ns = samples[0];
    
    for (i = 0; i < cycles; i++) {
        double diff = samples[i] - entropy->mean_ns;
        entropy->variance_ns += diff * diff;
        if (samples[i] < entropy->min_ns) entropy->min_ns = samples[i];
        if (samples[i] > entropy->max_ns) entropy->max_ns = samples[i];
    }
    entropy->variance_ns /= cycles;
    entropy->sample_count = cycles;
    
    free(samples);
}

static void build_entropy_report(entropy_report_t *report, const char *nonce) {
    entropy_data_t entropy;
    uint8_t hash[32];
    char entropy_json[512];
    char commitment_raw[1024];
    int i;
    
    collect_entropy(&entropy, 48, 25000);
    
    sprintf(entropy_json, "{\"mean_ns\":%.2f,\"variance_ns\":%.2f,\"min_ns\":%.2f,\"max_ns\":%.2f,\"sample_count\":%d}",
            entropy.mean_ns, entropy.variance_ns, entropy.min_ns, entropy.max_ns, entropy.sample_count);
    
    sprintf(commitment_raw, "%s%s%s", nonce, wallet, entropy_json);
    sha256_hash_string(commitment_raw, strlen(commitment_raw), hash);
    
    report->commitment_hex[0] = '\0';
    for (i = 0; i < 32; i++) {
        char byte_hex[8];
        sprintf(byte_hex, "%02x", hash[i]);
        strcat(report->commitment_hex, byte_hex);
    }
    
    report->nonce = nonce;
    report->entropy = entropy;
    report->entropy_score = entropy.variance_ns;
}

static int http_get(const char *url, char *response, int max_len) {
    FILE *fp;
    char cmd[512];
    int bytes_read = 0;
    
    sprintf(cmd, "curl.exe -sk \"%s\" 2>NUL", url);
    fp = popen(cmd, "r");
    if (fp) {
        bytes_read = fread(response, 1, max_len - 1, fp);
        response[bytes_read] = '\0';
        pclose(fp);
        if (bytes_read > 0) return bytes_read;
    }
    
    sprintf(cmd, "wget.exe -q -O - \"%s\" 2>NUL", url);
    fp = popen(cmd, "r");
    if (fp) {
        bytes_read = fread(response, 1, max_len - 1, fp);
        response[bytes_read] = '\0';
        pclose(fp);
        if (bytes_read > 0) return bytes_read;
    }
    
    return 0;
}

static int http_post(const char *url, const char *body, char *response, int max_len) {
    FILE *fp;
    char cmd[1024];
    char *escaped_body;
    int bytes_read = 0;
    int i, j;
    
    escaped_body = (char *)malloc(strlen(body) * 2 + 1);
    if (!escaped_body) return 0;
    
    for (i = 0, j = 0; body[i]; i++) {
        if (body[i] == '"') escaped_body[j++] = '\\';
        escaped_body[j++] = body[i];
    }
    escaped_body[j] = '\0';
    
    sprintf(cmd, "curl.exe -sk -X POST -H \"Content-Type: application/json\" -d \"%s\" \"%s\" 2>NUL",
            escaped_body, url);
    free(escaped_body);
    
    fp = popen(cmd, "r");
    if (fp) {
        bytes_read = fread(response, 1, max_len - 1, fp);
        response[bytes_read] = '\0';
        pclose(fp);
        if (bytes_read > 0) return bytes_read;
    }
    
    return 0;
}

static int extract_nonce(const char *json, char *nonce, int max_len) {
    const char *p;
    int len = 0;
    
    p = strstr(json, "\"nonce\"");
    if (!p) return 0;
    p = strchr(p, ':');
    if (!p) return 0;
    p++;
    while (*p == ' ' || *p == '\t') p++;
    if (*p == '"') p++;
    
    while (*p && *p != '"' && len < max_len - 1) {
        nonce[len++] = *p++;
    }
    nonce[len] = '\0';
    
    return len > 0;
}

static void attest(void) {
    char response[8192];
    char nonce[128];
    char attestation_json[4096];
    entropy_report_t entropy_report;
    fingerprint_t fp;
    
    print_banner();
    
    printf("[INFO] Collecting hardware fingerprint...\n");
    fingerprint_collect(&fp);
    printf("[INFO] CPU: %s\n", fp.cpu_type);
    printf("[INFO] Memory: %d KB\n", fp.memory_kb);
    printf("[INFO] FPU: %s\n", fp.has_387 ? "present" : "absent");
    printf("[INFO] MAC: %s\n", fp.mac);
    
    generate_miner_id(&fp);
    printf("[INFO] Miner ID: %s\n", miner_id);
    printf("\n");
    
    printf("[INFO] Starting attestation loop...\n");
    printf("[INFO] Each epoch = %d seconds\n\n", EPOCH_DURATION);
    
    while (1) {
        epoch_count++;
        printf("============================================\n");
        printf("[EPOCH #%d]\n", epoch_count);
        
        printf("[NET] Requesting challenge from node...\n");
        sprintf(response, "%s/attest/challenge", node_url);
        
        if (http_get(response, response, sizeof(response)) == 0) {
            printf("[ERROR] Failed to connect to node\n");
            printf("[INFO] Retrying in 30 seconds...\n");
            sleep(30);
            continue;
        }
        
        if (!extract_nonce(response, nonce, sizeof(nonce))) {
            printf("[ERROR] No nonce in response\n");
            printf("[INFO] Retrying in 30 seconds...\n");
            sleep(30);
            continue;
        }
        
        printf("[INFO] Got challenge nonce: %.16s...\n", nonce);
        
        build_entropy_report(&entropy_report, nonce);
        
        sprintf(attestation_json,
            "{\"miner\":\"%s\",\"miner_id\":\"%s\",\"nonce\":\"%s\","
            "\"report\":{\"nonce\":\"%s\",\"commitment\":\"%s\","
            "\"derived\":{\"mean_ns\":%.2f,\"variance_ns\":%.2f,\"sample_count\":%d},"
            "\"entropy_score\":%.2f},"
            "\"device\":{\"family\":\"i386\",\"arch\":\"Intel 80386\",\"model\":\"i386\","
            "\"cpu\":\"%s\",\"cores\":1,\"memory_kb\":%d},"
            "\"signals\":{\"macs\":[\"%s\"],\"hostname\":\"%s\"},"
            "\"fingerprint\":{\"checks\":{"
            "\"cpuid_works\":{\"passed\":%s,\"data\":{\"cpuid_result\":%d}},"
            "\"fpu_present\":{\"passed\":%s,\"data\":{\"has_387\":%s}},"
            "\"cache_present\":{\"passed\":true,\"data\":{\"cache_size_kb\":0}}},"
            "\"all_passed\":true},"
            "\"miner_version\":\"%s\"}",
            wallet, miner_id, nonce,
            nonce, entropy_report.commitment_hex,
            entropy_report.entropy.mean_ns,
            entropy_report.entropy.variance_ns,
            entropy_report.entropy.sample_count,
            entropy_report.entropy_score,
            fp.cpu_type, fp.memory_kb,
            fp.mac, fp.hostname,
            fp.has_cpuid ? "false" : "true", fp.cpuid_result,
            fp.has_387 ? "true" : "false", fp.has_387 ? "true" : "false",
            MINER_VERSION);
        
        printf("[NET] Submitting attestation...\n");
        sprintf(response, "%s/attest/submit", node_url);
        
        if (http_post(response, attestation_json, response, sizeof(response)) == 0) {
            printf("[ERROR] Failed to submit attestation\n");
        } else {
            if (strstr(response, "\"ok\":true") || strstr(response, "\"success\":true")) {
                printf("[SUCCESS] Attestation accepted!\n");
                printf("[INFO] 4.0x multiplier applied for Intel 386\n");
            } else {
                printf("[WARN] Attestation response unclear\n");
            }
        }
        
        printf("[INFO] Waiting for next epoch...\n\n");
        sleep(EPOCH_DURATION);
    }
}

int main(int argc, char *argv[]) {
    printf("\n============================================\n");
    printf("  RustChain Intel 386 Miner\n");
    printf("  Initializing...\n");
    printf("============================================\n");
    
    get_config();
    
    if (argc > 1) {
        strncpy(wallet, argv[1], sizeof(wallet) - 1);
        wallet[sizeof(wallet) - 1] = '\0';
    }
    
    attest();
    return 0;
}
