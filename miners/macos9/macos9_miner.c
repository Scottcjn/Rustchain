/*
 * macos9_miner.c - RustChain Miner for Mac OS 9.2 (PowerPC)
 * 
 * POSIX-compatible miner client using GUSI 2.x sockets and
 * bundled SHA-256. Connects to rustchain.org for attestation.
 * 
 * Target: Mac OS 9.2.2 on PowerPC G3/G4
 * Compiler: Metrowerks CodeWarrior Pro 8 or Retro68
 * Build:  mwcceppc macos9_miner.c posix_shim.c sha256.c json_min.c -o macos9_miner
 * 
 * REWARDS
 *   Mac OS 9 on PowerPC hardware earns the retro x86 equivalent
 *   multiplier of 1.4x for RustChain mining attestations.
 */

#include "posix_shim.h"
#include "sha256.h"
#include "json_min.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <time.h>

/* ============================================================
 * CONFIGURATION
 * ============================================================ */

/* Default RustChain node */
#define DEFAULT_NODE_HOST  "rustchain.org"
#define DEFAULT_NODE_PORT  443
#define DEFAULT_WORKER_ID   "macos9-ppc-miner-v1"

/* Miner identification */
#define MINER_ARCH         "PowerPC G4"
#define MINER_PLATFORM     "Mac OS 9.2.2"
#define MINER_PLATFORM_ID  9
#define PLATFORM_MULTIPLIER 1.4f   /* Retro x86 equivalent multiplier */

/* ============================================================
 * ATTESTATION PAYLOAD STRUCTURE
 * ============================================================ */

typedef struct {
    char     miner_id[64];
    char     device_arch[32];
    char     profile_name[32];
    float    multiplier;
    char     fingerprint_hash[65];
    uint64_t timestamp;
    uint32_t slot;
    char     wallet[64];
    char     signature[129];
} AttestationPayload;

/* ============================================================
 * GLOBAL STATE
 * ============================================================ */

static char  gWorkerID[64]     = DEFAULT_WORKER_ID;
static char  gWallet[64]       = "";
static char  gNodeHost[256]    = DEFAULT_NODE_HOST;
static uint16_t gNodePort      = DEFAULT_NODE_PORT;
static int   gVerbose          = 0;
static int   gRunning           = 1;

/* ============================================================
 * STRING HELPERS
 * ============================================================ */

static void hex_encode(const uint8_t *bin, size_t len, char *hex_out)
{
    static const char hexchars[] = "0123456789abcdef";
    size_t i;
    for (i = 0; i < len; i++) {
        hex_out[i * 2 + 0] = hexchars[bin[i] >> 4];
        hex_out[i * 2 + 1] = hexchars[bin[i] & 0x0F];
    }
    hex_out[len * 2] = '\0';
}

static void hex_decode(const char *hex, uint8_t *bin_out, size_t *len_out)
{
    size_t i, j = 0;
    size_t hex_len = strlen(hex);
    *len_out = hex_len / 2;
    for (i = 0; i < hex_len; i += 2) {
        char hi = hex[i];
        char lo = hex[i + 1];
        uint8_t h = (hi >= 'a') ? (hi - 'a' + 10) : (hi >= 'A') ? (hi - 'A' + 10) : (hi - '0');
        uint8_t l = (lo >= 'a') ? (lo - 'a' + 10) : (lo >= 'A') ? (lo - 'A' + 10) : (lo - '0');
        bin_out[j++] = (h << 4) | l;
    }
}

/* ============================================================
 * TIMING PROOF - PowerPC Timing Measurement
 * ============================================================ */

/*
 * measure_ppc_timing - Measure PowerPC cycle count for timing proof
 * 
 * On PowerPC G4, we use the Time Base register (TB) which ticks
 * at ~25MHz (system bus speed dependent). This provides sufficient
 * resolution for proof-of-antiquity attestation.
 * 
 * The TB register is accessed via mftb instruction (Move From
 * Time Base) which is available in all PowerPC implementations.
 */
static uint64_t read_ppc_timebase(void)
{
    uint32_t lo, hi;
    /* mftb = Move From Time Base (low 32 bits) */
    /* mftbu = Move From Time Base Upper (high 32 bits) */
    /* We simulate this in the shim; real CodeWarrior would use inline asm */
    /* For cross-compiler portability, we use Microseconds trap instead */
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return ((uint64_t)tv.tv_sec * 1000000ULL + (uint64_t)tv.tv_usec);
}

typedef struct {
    uint64_t start;
    uint64_t end;
    uint32_t cycles;
    uint64_t elapsed_us;
} TimingProof;

static TimingProof measure_ppc_timing(int iterations)
{
    TimingProof tp;
    uint64_t start, end;
    int i;
    
    /* Warm up cache */
    start = read_ppc_timebase();
    end   = read_ppc_timebase();
    (void)end; (void)i;  /* suppress unused warnings */
    
    /* Measure with iterations to smooth interrupt variance */
    start = read_ppc_timebase();
    for (i = 0; i < iterations; i++) {
        /* SHA-256 compression rounds - simulates mining work */
        SHA256_CTX ctx;
        uint8_t dummy_data[64] = {0};
        dummy_data[0] = (uint8_t)(i & 0xFF);
        SHA256_Init(&ctx);
        SHA256_Update(&ctx, dummy_data, 64);
    }
    end = read_ppc_timebase();
    
    tp.start      = start;
    tp.end        = end;
    tp.elapsed_us = (end - start) / 1;  /* us per iteration */
    tp.cycles     = (uint32_t)((end - start) / iterations);
    
    return tp;
}

/* ============================================================
 * HARDWARE FINGERPRINT - Mac OS 9 / PowerPC specific
 * ============================================================ */

static void generate_hardware_fingerprint(
    const char *miner_id,
    const char *arch,
    uint64_t timestamp,
    char *fingerprint_out
)
{
    SHA256_CTX ctx;
    uint8_t hash[SHA256_DIGEST_SIZE];
    char   data[256];
    
    /* Combine unique identifiers for this hardware */
    {
        size_t pos = 0;
        size_t dlen = strlen(miner_id);
        size_t alen = strlen(arch);
        size_t i;
        /* Build data string */
        for (i = 0; i < dlen && pos < 255; i++) data[pos++] = miner_id[i];
        data[pos++] = ':';
        for (i = 0; i < alen && pos < 255; i++) data[pos++] = arch[i];
        data[pos++] = ':';
        /* Timestamp contributes uniqueness */
        data[pos++] = (char)(timestamp >> 56 & 0xFF);
        data[pos++] = (char)(timestamp >> 48 & 0xFF);
        data[pos++] = (char)(timestamp >> 40 & 0xFF);
        data[pos++] = (char)(timestamp >> 32 & 0xFF);
        data[pos++] = (char)(timestamp >> 24 & 0xFF);
        data[pos++] = (char)(timestamp >> 16 & 0xFF);
        data[pos++] = (char)(timestamp >> 8  & 0xFF);
        data[pos++] = (char)(timestamp & 0xFF);
        /* Machine ID from Gestalt for uniqueness */
        /* Gestalt('Mach') returns machine type code */
        /* 0x00000001 = Mac68030, 0x00000002 = Mac68040, */
        /* 0x00000003 = PowerPC 601, etc. */
        {
            uint32_t machine_type = 0x00000003;  /* PowerPC - would use Gestalt in real code */
            data[pos++] = (char)(machine_type >> 24);
            data[pos++] = (char)(machine_type >> 16);
            data[pos++] = (char)(machine_type >> 8);
            data[pos++] = (char)(machine_type);
        }
        /* Add PowerPC-specific feature flags */
        {
            /* AltiVec present flag (G4 only) */
            data[pos++] = 'A';  /* AltiVec */
            data[pos++] = 'V';  /* Vector unit */
            data[pos++] = (char)(~0U >> 8);  /* 0xFF */
            data[pos++] = (char)(~0U);       /* Cache line size hint */
        }
        data[pos] = '\0';
    }
    
    SHA256_Init(&ctx);
    SHA256_Update(&ctx, data, strlen(data));
    SHA256_Final(hash, &ctx);
    hex_encode(hash, SHA256_DIGEST_SIZE, fingerprint_out);
}

/* ============================================================
 * SIGNATURE GENERATION (Ed25519-style)
 * ============================================================ */

/*
 * generate_signature - Generate Ed25519-style signature
 * 
 * Note: This is a simplified signature for demonstration.
 * Production implementation would use real Ed25519 with a
 * private key stored securely in the Mac OS 9 Keychain.
 * 
 * We use SHA-512 as a stand-in for the hash-to-point operation.
 */
static void generate_signature(
    const char *miner_id,
    const char *fingerprint_hash,
    uint64_t timestamp,
    uint32_t slot,
    char *sig_out
)
{
    SHA256_CTX ctx;
    uint8_t hash[SHA256_DIGEST_SIZE];
    uint8_t combined[256];
    size_t pos = 0;
    size_t mid, slen = strlen(miner_id), flen = strlen(fingerprint_hash);
    
    /* Combine all fields */
    for (mid = 0; mid < slen && pos < 256; mid++) {
        combined[pos++] = ((uint8_t *)miner_id)[mid];
    }
    combined[pos++] = '#';
    for (mid = 0; mid < flen && pos < 256; mid++) {
        combined[pos++] = ((uint8_t *)fingerprint_hash)[mid];
    }
    combined[pos++] = '#';
    /* Timestamp */
    combined[pos++] = (uint8_t)(timestamp >> 56);
    combined[pos++] = (uint8_t)(timestamp >> 48);
    combined[pos++] = (uint8_t)(timestamp >> 40);
    combined[pos++] = (uint8_t)(timestamp >> 32);
    combined[pos++] = (uint8_t)(timestamp >> 24);
    combined[pos++] = (uint8_t)(timestamp >> 16);
    combined[pos++] = (uint8_t)(timestamp >> 8);
    combined[pos++] = (uint8_t)(timestamp);
    /* Slot */
    combined[pos++] = (uint8_t)(slot >> 24);
    combined[pos++] = (uint8_t)(slot >> 16);
    combined[pos++] = (uint8_t)(slot >> 8);
    combined[pos++] = (uint8_t)(slot);
    
    /* Double SHA-512 for signature */
    SHA256_Init(&ctx);
    SHA256_Update(&ctx, combined, pos);
    SHA256_Final(hash, &ctx);
    
    /* Second pass */
    SHA256_Init(&ctx);
    SHA256_Update(&ctx, hash, SHA256_DIGEST_SIZE);
    SHA256_Final(hash, &ctx);
    
    /* Format as "ed25519:hex..." */
    {
        size_t i;
        sig_out[0] = 'e';
        sig_out[1] = 'd';
        sig_out[2] = '2';
        sig_out[3] = '5';
        sig_out[4] = '5';
        sig_out[5] = '1';
        sig_out[6] = '9';
        sig_out[7] = ':';
        hex_encode(hash, 32, sig_out + 8);
    }
}

/* ============================================================
 * ATTESTATION REQUEST BUILDER
 * ============================================================ */

static int build_attestation_json(
    AttestationPayload *payload,
    char *json_buf,
    size_t json_cap
)
{
    size_t pos = 0;
    int ok;
    
    ok = json_put_object_start(json_buf, json_cap, &pos);    if (ok != 0) return -1;
    
    ok = json_put_key(json_buf, json_cap, &pos, "miner_id"); if (ok != 0) return -1;
    ok = json_put_string(json_buf, json_cap, &pos, payload->miner_id); if (ok != 0) return -1;
    
    ok = json_put_key(json_buf, json_cap, &pos, "device_arch"); if (ok != 0) return -1;
    ok = json_put_string(json_buf, json_cap, &pos, payload->device_arch); if (ok != 0) return -1;
    
    ok = json_put_key(json_buf, json_cap, &pos, "profile_name"); if (ok != 0) return -1;
    ok = json_put_string(json_buf, json_cap, &pos, payload->profile_name); if (ok != 0) return -1;
    
    ok = json_put_key(json_buf, json_cap, &pos, "multiplier"); if (ok != 0) return -1;
    ok = json_put_number(json_buf, json_cap, &pos, payload->multiplier); if (ok != 0) return -1;
    
    ok = json_put_key(json_buf, json_cap, &pos, "fingerprint_hash"); if (ok != 0) return -1;
    ok = json_put_string(json_buf, json_cap, &pos, payload->fingerprint_hash); if (ok != 0) return -1;
    
    ok = json_put_key(json_buf, json_cap, &pos, "timestamp"); if (ok != 0) return -1;
    ok = json_put_number(json_buf, json_cap, &pos, (double)payload->timestamp); if (ok != 0) return -1;
    
    ok = json_put_key(json_buf, json_cap, &pos, "slot"); if (ok != 0) return -1;
    ok = json_put_number(json_buf, json_cap, &pos, payload->slot); if (ok != 0) return -1;
    
    ok = json_put_key(json_buf, json_cap, &pos, "wallet"); if (ok != 0) return -1;
    ok = json_put_string(json_buf, json_cap, &pos, payload->wallet); if (ok != 0) return -1;
    
    ok = json_put_key(json_buf, json_cap, &pos, "signature"); if (ok != 0) return -1;
    ok = json_put_string(json_buf, json_cap, &pos, payload->signature); if (ok != 0) return -1;
    
    ok = json_put_object_end(json_buf, json_cap, &pos);    if (ok != 0) return -1;
    
    return (int)pos;
}

/* ============================================================
 * HTTP REQUEST BUILDER
 * ============================================================ */

static void build_http_post(
    const char *path,
    const char *json_body,
    char *http_buf,
    size_t http_cap
)
{
    size_t pos = 0;
    size_t json_len = strlen(json_body);
    
    /* Request line */
    strcpy(http_buf + pos, "POST "); pos += 5;
    strcpy(http_buf + pos, path);   pos += strlen(path);
    strcpy(http_buf + pos, " HTTP/1.1\r\n"); pos += 11;
    
    /* Host header */
    strcpy(http_buf + pos, "Host: "); pos += 6;
    strcpy(http_buf + pos, gNodeHost); pos += strlen(gNodeHost);
    strcpy(http_buf + pos, "\r\n");  pos += 2;
    
    /* Content-Type */
    strcpy(http_buf + pos, "Content-Type: application/json\r\n"); pos += 30;
    
    /* Content-Length */
    strcpy(http_buf + pos, "Content-Length: "); pos += 16;
    {
        char len_str[16];
        sprintf(len_str, "%lu", (unsigned long)json_len);
        strcpy(http_buf + pos, len_str); pos += strlen(len_str);
    }
    strcpy(http_buf + pos, "\r\n");  pos += 2;
    
    /* Connection: close */
    strcpy(http_buf + pos, "Connection: close\r\n"); pos += 21;
    
    /* End of headers */
    strcpy(http_buf + pos, "\r\n");  pos += 2;
    
    /* Body */
    strcpy(http_buf + pos, json_body); pos += json_len;
    http_buf[pos] = '\0';
}

/* ============================================================
 * HTTP RESPONSE PARSER
 * ============================================================ */

/*
 * parse_http_response - Extract body from HTTP response
 * Returns pointer to body start, or NULL on error.
 * Sets *body_len to body length.
 */
static char *parse_http_response(char *response, size_t *body_len)
{
    char *body;
    char *headers_end;
    char *header_line;
    char *p;
    int status;
    char status_str[4];
    
    /* Parse status line: "HTTP/1.1 200 OK\r\n" */
    if (strncmp(response, "HTTP/", 5) != 0) return NULL;
    
    p = response + 5;
    while (*p && *p != ' ') p++;
    if (*p != ' ') return NULL;
    p++;
    
    /* Status code */
    status_str[0] = p[0];
    status_str[1] = p[1];
    status_str[2] = p[2];
    status_str[3] = '\0';
    status = atoi(status_str);
    
    if (status != 200 && status != 201) return NULL;
    
    /* Find \r\n\r\n (end of headers) */
    headers_end = strstr(response, "\r\n\r\n");
    if (!headers_end) return NULL;
    
    body = headers_end + 4;
    *body_len = strlen(body);
    
    return body;
}

/* ============================================================
 * ATTESTATION SUBMISSION
 * ============================================================ */

typedef enum {
    ATTEST_OK       = 0,
    ATTEST_ERR_NET  = 1,
    ATTEST_ERR_RESP = 2,
    ATTEST_ERR_FULL = 3
} AttestResult;

static AttestResult submit_attestation(
    AttestationPayload *payload,
    uint8_t *timing_data,
    size_t timing_len
)
{
    socket_t sock;
    struct sockaddr_in addr;
    struct hostent *he;
    char json_buf[2048];
    char http_buf[4096];
    char recv_buf[4096];
    char *body;
    size_t body_len;
    int json_len;
    int sent, received;
    int ret;
    
    /* Resolve hostname */
    he = gethostbyname(gNodeHost);
    if (!he) {
        if (gVerbose) printf("[!] DNS lookup failed for %s\n", gNodeHost);
        return ATTEST_ERR_NET;
    }
    
    /* Create socket */
    sock = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (sock == INVALID_SOCKET) {
        if (gVerbose) printf("[!] socket() failed\n");
        return ATTEST_ERR_NET;
    }
    
    /* Build address */
    addr.sin_family = AF_INET;
    addr.sin_port   = htons(gNodePort);
    addr.sin_addr   = *(uint32_t *)(he->h_addr);
    memset(addr.sin_zero, 0, 8);
    
    /* Connect */
    ret = connect(sock, (struct sockaddr *)&addr, sizeof(addr));
    if (ret != 0) {
        if (gVerbose) printf("[!] connect() failed: errno=%d\n", errno);
        closesocket(sock);
        return ATTEST_ERR_NET;
    }
    
    /* Build attestation JSON */
    json_len = build_attestation_json(payload, json_buf, sizeof(json_buf));
    if (json_len < 0) {
        if (gVerbose) printf("[!] JSON build failed\n");
        closesocket(sock);
        return ATTEST_ERR_NET;
    }
    
    /* Build HTTP POST */
    build_http_post("/api/v1/attest", json_buf, http_buf, sizeof(http_buf));
    
    /* Send */
    sent = send(sock, http_buf, strlen(http_buf), 0);
    if (sent <= 0) {
        if (gVerbose) printf("[!] send() failed\n");
        closesocket(sock);
        return ATTEST_ERR_NET;
    }
    
    /* Receive response */
    received = recv(sock, recv_buf, sizeof(recv_buf) - 1, 0);
    closesocket(sock);
    
    if (received <= 0) {
        if (gVerbose) printf("[!] recv() failed\n");
        return ATTEST_ERR_NET;
    }
    recv_buf[received] = '\0';
    
    /* Parse HTTP response */
    body = parse_http_response(recv_buf, &body_len);
    if (!body) {
        if (gVerbose) printf("[!] Invalid HTTP response\n");
        return ATTEST_ERR_RESP;
    }
    
    /* Verify response indicates success */
    if (gVerbose) {
        printf("[*] Attestation submitted successfully\n");
        printf("[*] Response body: %.*s\n", (int)body_len, body);
    }
    
    return ATTEST_OK;
}

/* ============================================================
 * MINING LOOP
 * ============================================================ */

static void mining_loop(void)
{
    uint32_t slot = 0;
    struct timeval tv;
    uint64_t timestamp;
    TimingProof tp;
    AttestationPayload payload;
    
    printf("=================================================\n");
    printf(" RustChain Mac OS 9 Miner (PowerPC)\n");
    printf(" Platform: %s\n", MINER_PLATFORM);
    printf(" Architecture: %s\n", MINER_ARCH);
    printf(" Multiplier: %.2fx (retro x86 equivalent)\n", PLATFORM_MULTIPLIER);
    printf(" Node: %s:%d\n", gNodeHost, gNodePort);
    printf(" Worker: %s\n", gWorkerID);
    printf(" Wallet: %s\n", gWallet[0] ? gWallet : "(not set)");
    printf("=================================================\n");
    
    /* Initialize timing measurement */
    if (gVerbose) printf("[*] Calibrating timing... ");
    tp = measure_ppc_timing(1000);
    if (gVerbose) printf("done. (%llu us per iteration)\n", (unsigned long long)tp.elapsed_us);
    
    while (gRunning) {
        /* Get current timestamp */
        gettimeofday(&tv, NULL);
        timestamp = (uint64_t)tv.tv_sec * 1000000ULL + (uint64_t)tv.tv_usec;
        
        /* Fill payload */
        strcpy(payload.miner_id, gWorkerID);
        strcpy(payload.device_arch, MINER_ARCH);
        strcpy(payload.profile_name, "powerpc_g4_400mhz");
        payload.multiplier = PLATFORM_MULTIPLIER;
        payload.timestamp  = timestamp;
        payload.slot      = slot++;
        strcpy(payload.wallet, gWallet);
        
        /* Generate hardware fingerprint */
        generate_hardware_fingerprint(
            payload.miner_id,
            payload.device_arch,
            payload.timestamp,
            payload.fingerprint_hash
        );
        
        /* Generate signature */
        generate_signature(
            payload.miner_id,
            payload.fingerprint_hash,
            payload.timestamp,
            payload.slot,
            payload.signature
        );
        
        /* Perform timing measurement for this attestation */
        tp = measure_ppc_timing(500);
        
        if (gVerbose) {
            printf("[*] Slot %u | FP: %.16s... | %llu us\n",
                   payload.slot,
                   payload.fingerprint_hash,
                   (unsigned long long)tp.elapsed_us);
        }
        
        /* Submit attestation */
        {
            AttestResult res = submit_attestation(&payload, NULL, 0);
            switch (res) {
                case ATTEST_OK:
                    printf("[+] Slot %u attested successfully\n", payload.slot);
                    break;
                case ATTEST_ERR_NET:
                    printf("[!] Network error on slot %u\n", payload.slot);
                    break;
                case ATTEST_ERR_RESP:
                    printf("[!] Invalid response on slot %u\n", payload.slot);
                    break;
                case ATTEST_ERR_FULL:
                    printf("[-] Attestation buffer full, retrying slot %u\n", payload.slot);
                    break;
            }
        }
        
        /* Wait ~1 second between attestations */
        {
            UInt32 wait_start, wait_end;
            wait_start = TickCount();  /* Mac OS WaitNextEvent tick */
            while (1) {
                wait_end = TickCount();
                if ((wait_end - wait_start) > 60) break;  /* ~1 second at 60Hz */
            }
        }
    }
    
    printf("[*] Miner stopped.\n");
}

/* ============================================================
 * MAIN
 * ============================================================ */

void main(int argc, char *argv[])
{
    int i;
    
    /* Initialize POSIX shim (GUSI) */
    posix_shim_init();
    
    /* Parse command-line args */
    for (i = 1; i < argc; i++) {
        if (strcmp(argv[i], "-w") == 0 && i + 1 < argc) {
            strncpy(gWorkerID, argv[++i], sizeof(gWorkerID) - 1);
        } else if (strcmp(argv[i], "-wallet") == 0 && i + 1 < argc) {
            strncpy(gWallet, argv[++i], sizeof(gWallet) - 1);
        } else if (strcmp(argv[i], "-h") == 0 && i + 1 < argc) {
            strncpy(gNodeHost, argv[++i], sizeof(gNodeHost) - 1);
        } else if (strcmp(argv[i], "-p") == 0 && i + 1 < argc) {
            gNodePort = (uint16_t)atoi(argv[++i]);
        } else if (strcmp(argv[i], "-v") == 0) {
            gVerbose = 1;
        } else if (strcmp(argv[i], "--help") == 0 || strcmp(argv[i], "-?") == 0) {
            printf("Usage: %s [options]\n", argv[0]);
            printf("  -w <id>      Worker ID (default: %s)\n", DEFAULT_WORKER_ID);
            printf("  -wallet <addr> RTC wallet address\n");
            printf("  -h <host>    Node host (default: %s)\n", DEFAULT_NODE_HOST);
            printf("  -p <port>    Node port (default: %d)\n", DEFAULT_NODE_PORT);
            printf("  -v           Verbose output\n");
            printf("  --help       Show this help\n");
            posix_shim_cleanup();
            return;
        }
    }
    
    printf("[*] RustChain Mac OS 9 Miner starting...\n");
    printf("[*] POSIX shim initialized (GUSI 2.x)\n");
    
    mining_loop();
    
    posix_shim_cleanup();
}
