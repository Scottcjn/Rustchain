/*
 * RustChain Anti-Spoofing Challenge-Response System
 * =================================================
 *
 * Philosophy: "It's cheaper to buy a $50 vintage Mac than to emulate one"
 *
 * This system makes hardware spoofing economically irrational by:
 * 1. Real-time timing challenges using PowerPC timebase register
 * 2. Cache-timing measurements that emulators can't fake
 * 3. Hardware serial cross-validation
 * 4. Thermal sensor correlation
 * 5. Strict timing windows (emulators are too slow/fast/consistent)
 *
 * QEMU/PearPC running on modern hardware will fail because:
 * - Timing is too consistent (real hardware has jitter)
 * - Cache timing is wrong (emulated cache doesn't match real L1/L2)
 * - Missing or generic hardware serials
 * - No real thermal sensors
 * - OpenFirmware values don't match hardware
 *
 * Compile: gcc -O0 challenge_response.c -o challenge -framework CoreFoundation -framework IOKit
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#ifdef __APPLE__
#include <sys/sysctl.h>
#include <mach/mach_time.h>
#endif

#ifdef __ppc__
#include <ppc_intrinsics.h>
#endif

/* Challenge types */
#define CHALLENGE_TIMEBASE    0x01
#define CHALLENGE_CACHE       0x02
#define CHALLENGE_MEMORY      0x03
#define CHALLENGE_THERMAL     0x04
#define CHALLENGE_SERIAL      0x05

/* Timing tolerances (in timebase ticks) */
#define TIMING_TOLERANCE_MIN  0.8   /* Response must be >= 80% of expected */
#define TIMING_TOLERANCE_MAX  1.5   /* Response must be <= 150% of expected */
#define JITTER_THRESHOLD      0.02  /* Must have >= 2% variance (emulators are too consistent) */

/* Anti-emulation thresholds */
#define MIN_JITTER_SAMPLES    16
#define MAX_CONSISTENT_RUNS   3  /* If > 3 runs have identical timing, suspicious */

typedef struct {
    unsigned char challenge_type;
    unsigned char nonce[32];
    unsigned long long timestamp;
    unsigned int expected_min_ticks;
    unsigned int expected_max_ticks;
} Challenge;

typedef struct {
    unsigned char response_hash[64];
    unsigned long long timing_ticks;
    unsigned long long timebase_value;
    unsigned int cache_l1_time;
    unsigned int cache_l2_time;
    unsigned int memory_time;
    int thermal_reading;
    char hardware_serial[32];
    unsigned int jitter_variance;
} Response;

typedef struct {
    int valid;
    int timing_in_range;
    int jitter_natural;
    int hardware_match;
    int thermal_present;
    float confidence_score;
    char failure_reason[256];
} ValidationResult;

/* PowerPC-specific: Read timebase register */
static inline unsigned long long read_timebase(void) {
#ifdef __ppc__
    unsigned int tbl, tbu, tbu2;
    do {
        tbu = __mftbu();
        tbl = __mftb();
        tbu2 = __mftbu();
    } while (tbu != tbu2);
    return ((unsigned long long)tbu << 32) | tbl;
#elif defined(__APPLE__)
    return mach_absolute_time();
#else
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (unsigned long long)ts.tv_sec * 1000000000ULL + ts.tv_nsec;
#endif
}

/* Cache timing challenge - measures L1/L2 access patterns */
static void cache_timing_challenge(unsigned int *l1_time, unsigned int *l2_time) {
    volatile unsigned char *buffer_l1;
    volatile unsigned char *buffer_l2;
    unsigned long long start, end;
    int i;
    volatile unsigned char sink;

    /* L1 cache is typically 32KB, L2 is 256KB-2MB */
    buffer_l1 = (unsigned char*)malloc(16384);   /* Fits in L1 */
    buffer_l2 = (unsigned char*)malloc(524288);  /* Exceeds L1, fits L2 */

    if (!buffer_l1 || !buffer_l2) {
        *l1_time = 0;
        *l2_time = 0;
        return;
    }

    /* Prime L1 cache */
    for (i = 0; i < 16384; i += 64) {
        buffer_l1[i] = (unsigned char)i;
    }

    /* Measure L1 access time */
    start = read_timebase();
    for (i = 0; i < 16384; i += 64) {
        sink = buffer_l1[i];
    }
    end = read_timebase();
    *l1_time = (unsigned int)(end - start);

    /* Prime L2 cache (force L1 eviction) */
    for (i = 0; i < 524288; i += 64) {
        buffer_l2[i] = (unsigned char)i;
    }

    /* Measure L2 access time (L1 should be evicted) */
    start = read_timebase();
    for (i = 0; i < 16384; i += 64) {
        sink = buffer_l1[i];
    }
    end = read_timebase();
    *l2_time = (unsigned int)(end - start);

    free((void*)buffer_l1);
    free((void*)buffer_l2);

    /* L2 should be slower than L1 by at least 2x on real hardware */
    /* Emulators often don't model this correctly */
}

/* Memory access pattern challenge */
static unsigned int memory_pattern_challenge(void) {
    volatile unsigned char *buffer;
    unsigned long long start, end;
    int i;
    volatile unsigned char sink;

    /* Large buffer that exceeds all cache levels */
    buffer = (unsigned char*)malloc(16 * 1024 * 1024);
    if (!buffer) return 0;

    /* Random-ish access pattern that defeats prefetching */
    start = read_timebase();
    for (i = 0; i < 1000; i++) {
        int offset = ((i * 7919) % (16 * 1024 * 1024));
        sink = buffer[offset];
    }
    end = read_timebase();

    free((void*)buffer);
    return (unsigned int)(end - start);
}

/* Measure timing jitter - real hardware has natural variance */
static unsigned int measure_jitter(void) {
    unsigned long long samples[MIN_JITTER_SAMPLES];
    unsigned long long sum = 0, sum_sq = 0;
    unsigned long long mean, variance;
    int i;

    for (i = 0; i < MIN_JITTER_SAMPLES; i++) {
        unsigned long long start = read_timebase();
        volatile int j;
        for (j = 0; j < 1000; j++) { /* Simple loop */
            /* empty */
        }
        samples[i] = read_timebase() - start;
        sum += samples[i];
    }

    mean = sum / MIN_JITTER_SAMPLES;

    for (i = 0; i < MIN_JITTER_SAMPLES; i++) {
        long long diff = (long long)samples[i] - (long long)mean;
        sum_sq += diff * diff;
    }

    variance = sum_sq / MIN_JITTER_SAMPLES;

    /* Return variance as percentage of mean * 1000 */
    if (mean == 0) return 0;
    return (unsigned int)((variance * 1000) / (mean * mean / 1000));
}

/* Get hardware serial (hard to fake) */
static void get_hardware_serial(char *serial, size_t len) {
#ifdef __APPLE__
    FILE *fp;

    /* Try OpenFirmware first */
    fp = popen("nvram 'platform-uuid' 2>/dev/null | cut -d'%' -f2 | head -c 30", "r");
    if (fp) {
        if (fgets(serial, (int)len, fp)) {
            serial[strcspn(serial, "\n")] = 0;
            pclose(fp);
            if (strlen(serial) > 5) return;
        }
        pclose(fp);
    }

    /* Fall back to system serial */
    fp = popen("ioreg -l | grep IOPlatformSerialNumber | cut -d'\"' -f4 | head -1", "r");
    if (fp) {
        if (fgets(serial, (int)len, fp)) {
            serial[strcspn(serial, "\n")] = 0;
            pclose(fp);
            if (strlen(serial) > 5) return;
        }
        pclose(fp);
    }
#endif
    strcpy(serial, "UNKNOWN");
}

/* Get thermal reading */
static int get_thermal_reading(void) {
#ifdef __APPLE__
    FILE *fp;
    char buf[64];

    /* Try various thermal sources */
    fp = popen("sysctl -n hw.sensors 2>/dev/null | head -1", "r");
    if (fp) {
        if (fgets(buf, sizeof(buf), fp)) {
            pclose(fp);
            return atoi(buf);
        }
        pclose(fp);
    }

    /* PowerMac thermal zone */
    fp = popen("cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null", "r");
    if (fp) {
        if (fgets(buf, sizeof(buf), fp)) {
            pclose(fp);
            return atoi(buf) / 1000;
        }
        pclose(fp);
    }
#endif
    return -1; /* No thermal = suspicious */
}

/* Simple SHA256-like hash (for demonstration - use real crypto in production) */
static void compute_response_hash(Response *resp, unsigned char *hash) {
    /* In production: use OpenSSL SHA256 or similar */
    /* For now, XOR-based mixing of all response data */
    unsigned char *data = (unsigned char*)resp;
    size_t data_len = sizeof(Response) - 64; /* Exclude hash field */
    int i;

    memset(hash, 0, 64);
    for (i = 0; i < (int)data_len; i++) {
        hash[i % 64] ^= data[i];
        hash[(i + 13) % 64] ^= (data[i] << 4) | (data[i] >> 4);
        hash[(i + 37) % 64] ^= ~data[i];
    }

    /* Mix in timebase for uniqueness */
    for (i = 0; i < 8; i++) {
        hash[i] ^= (resp->timebase_value >> (i * 8)) & 0xFF;
        hash[63 - i] ^= (resp->timing_ticks >> (i * 8)) & 0xFF;
    }
}

/* Generate a challenge */
Challenge generate_challenge(unsigned char type) {
    Challenge c;
    int i;

    c.challenge_type = type;
    c.timestamp = read_timebase();

    /* Generate random nonce */
    for (i = 0; i < 32; i++) {
        c.nonce[i] = (unsigned char)(rand() ^ (c.timestamp >> (i % 8)));
    }

    /* Set expected timing based on challenge type */
    switch (type) {
        case CHALLENGE_CACHE:
            c.expected_min_ticks = 100;
            c.expected_max_ticks = 50000;
            break;
        case CHALLENGE_MEMORY:
            c.expected_min_ticks = 1000;
            c.expected_max_ticks = 500000;
            break;
        default:
            c.expected_min_ticks = 10;
            c.expected_max_ticks = 100000;
    }

    return c;
}

/* Execute challenge and generate response */
Response execute_challenge(Challenge *c) {
    Response r;
    unsigned long long start, end;

    memset(&r, 0, sizeof(r));

    start = read_timebase();
    r.timebase_value = start;

    switch (c->challenge_type) {
        case CHALLENGE_CACHE:
            cache_timing_challenge(&r.cache_l1_time, &r.cache_l2_time);
            break;
        case CHALLENGE_MEMORY:
            r.memory_time = memory_pattern_challenge();
            break;
        case CHALLENGE_THERMAL:
            r.thermal_reading = get_thermal_reading();
            break;
        case CHALLENGE_SERIAL:
            get_hardware_serial(r.hardware_serial, sizeof(r.hardware_serial));
            break;
        default:
            cache_timing_challenge(&r.cache_l1_time, &r.cache_l2_time);
            r.memory_time = memory_pattern_challenge();
            r.thermal_reading = get_thermal_reading();
            get_hardware_serial(r.hardware_serial, sizeof(r.hardware_serial));
    }

    r.jitter_variance = measure_jitter();

    end = read_timebase();
    r.timing_ticks = end - start;

    compute_response_hash(&r, r.response_hash);

    return r;
}

/* Validate a response */
ValidationResult validate_response(Challenge *c, Response *r) {
    ValidationResult v;
    float timing_ratio;

    memset(&v, 0, sizeof(v));
    v.valid = 1;
    v.confidence_score = 100.0;

    /* Check timing is in expected range */
    if (r->timing_ticks < c->expected_min_ticks) {
        v.timing_in_range = 0;
        v.confidence_score -= 30.0;
        snprintf(v.failure_reason, sizeof(v.failure_reason),
                 "Response too fast (%llu < %u ticks) - possible emulator speedhack",
                 r->timing_ticks, c->expected_min_ticks);
    } else if (r->timing_ticks > c->expected_max_ticks) {
        v.timing_in_range = 0;
        v.confidence_score -= 20.0;
        snprintf(v.failure_reason, sizeof(v.failure_reason),
                 "Response too slow (%llu > %u ticks) - possible slow emulator",
                 r->timing_ticks, c->expected_max_ticks);
    } else {
        v.timing_in_range = 1;
    }

    /* Check for natural jitter (emulators are too consistent) */
    if (r->jitter_variance < 5) { /* Less than 0.5% variance is suspicious */
        v.jitter_natural = 0;
        v.confidence_score -= 40.0;
        if (strlen(v.failure_reason) == 0) {
            snprintf(v.failure_reason, sizeof(v.failure_reason),
                     "Timing too consistent (jitter=%u) - emulator detected",
                     r->jitter_variance);
        }
    } else {
        v.jitter_natural = 1;
    }

    /* Check L1/L2 cache timing ratio */
    if (r->cache_l1_time > 0 && r->cache_l2_time > 0) {
        timing_ratio = (float)r->cache_l2_time / (float)r->cache_l1_time;
        if (timing_ratio < 1.5 || timing_ratio > 20.0) {
            v.confidence_score -= 25.0;
            if (strlen(v.failure_reason) == 0) {
                snprintf(v.failure_reason, sizeof(v.failure_reason),
                         "Invalid L1/L2 cache timing ratio (%.2f) - emulated cache",
                         timing_ratio);
            }
        }
    }

    /* Check thermal sensor presence */
    if (r->thermal_reading < 0) {
        v.thermal_present = 0;
        v.confidence_score -= 15.0;
    } else if (r->thermal_reading < 10 || r->thermal_reading > 100) {
        v.thermal_present = 0;
        v.confidence_score -= 10.0;
    } else {
        v.thermal_present = 1;
    }

    /* Check hardware serial */
    if (strcmp(r->hardware_serial, "UNKNOWN") == 0 ||
        strlen(r->hardware_serial) < 5) {
        v.hardware_match = 0;
        v.confidence_score -= 20.0;
        if (strlen(v.failure_reason) == 0) {
            snprintf(v.failure_reason, sizeof(v.failure_reason),
                     "Missing or invalid hardware serial - generic VM");
        }
    } else {
        v.hardware_match = 1;
    }

    /* Final determination */
    if (v.confidence_score < 50.0) {
        v.valid = 0;
    }

    return v;
}

/* Print response details */
void print_response(Response *r) {
    int i;

    printf("\n╔══════════════════════════════════════════════════════════════════════╗\n");
    printf("║          RUSTCHAIN ANTI-SPOOFING CHALLENGE RESPONSE                  ║\n");
    printf("╚══════════════════════════════════════════════════════════════════════╝\n\n");

    printf("  Timing Analysis:\n");
    printf("    Total ticks:    %llu\n", r->timing_ticks);
    printf("    Timebase value: %llu\n", r->timebase_value);
    printf("    Jitter variance: %u (%.2f%%)\n", r->jitter_variance, r->jitter_variance / 10.0);

    printf("\n  Cache Timing:\n");
    printf("    L1 access time: %u ticks\n", r->cache_l1_time);
    printf("    L2 access time: %u ticks\n", r->cache_l2_time);
    if (r->cache_l1_time > 0) {
        printf("    L2/L1 ratio:    %.2fx\n", (float)r->cache_l2_time / r->cache_l1_time);
    }

    printf("\n  Memory:\n");
    printf("    Random access:  %u ticks\n", r->memory_time);

    printf("\n  Hardware:\n");
    printf("    Serial:         %s\n", r->hardware_serial);
    printf("    Thermal:        %d C\n", r->thermal_reading);

    printf("\n  Response Hash:\n    ");
    for (i = 0; i < 64; i++) {
        printf("%02x", r->response_hash[i]);
        if (i == 31) printf("\n    ");
    }
    printf("\n");
}

/* Print validation result */
void print_validation(ValidationResult *v) {
    printf("\n╔══════════════════════════════════════════════════════════════════════╗\n");
    printf("║                    VALIDATION RESULT                                 ║\n");
    printf("╚══════════════════════════════════════════════════════════════════════╝\n\n");

    printf("  Checks:\n");
    printf("    Timing in range:  %s\n", v->timing_in_range ? "✓ PASS" : "✗ FAIL");
    printf("    Natural jitter:   %s\n", v->jitter_natural ? "✓ PASS" : "✗ FAIL");
    printf("    Hardware serial:  %s\n", v->hardware_match ? "✓ PASS" : "✗ FAIL");
    printf("    Thermal sensor:   %s\n", v->thermal_present ? "✓ PASS" : "✗ FAIL");

    printf("\n  Confidence Score: %.1f%%\n", v->confidence_score);

    if (v->valid) {
        printf("\n  ╔════════════════════════════════════════════════════╗\n");
        printf("  ║  ✓ HARDWARE VERIFIED - NOT AN EMULATOR             ║\n");
        printf("  ╚════════════════════════════════════════════════════╝\n");
    } else {
        printf("\n  ╔════════════════════════════════════════════════════╗\n");
        printf("  ║  ✗ VALIDATION FAILED - POSSIBLE EMULATOR           ║\n");
        printf("  ╚════════════════════════════════════════════════════╝\n");
        printf("\n  Failure: %s\n", v->failure_reason);
    }
}

int main(int argc, char *argv[]) {
    Challenge c;
    Response r;
    ValidationResult v;

    printf("\n");
    printf("╔══════════════════════════════════════════════════════════════════════╗\n");
    printf("║        RUSTCHAIN PROOF OF ANTIQUITY - ANTI-SPOOFING SYSTEM          ║\n");
    printf("║                                                                      ║\n");
    printf("║   Philosophy: \"It's cheaper to buy a $50 vintage Mac                ║\n");
    printf("║                than to emulate one\"                                  ║\n");
    printf("╚══════════════════════════════════════════════════════════════════════╝\n");

    srand((unsigned int)time(NULL) ^ (unsigned int)read_timebase());

    printf("\n  Generating comprehensive challenge...\n");
    c = generate_challenge(0); /* Full challenge */

    printf("  Executing hardware tests...\n");
    r = execute_challenge(&c);

    print_response(&r);

    printf("\n  Validating response...\n");
    v = validate_response(&c, &r);

    print_validation(&v);

    printf("\n  Economic Analysis:\n");
    printf("    Emulator development cost: $50,000+ (accurate timing/cache)\n");
    printf("    Working PowerMac G4 cost:  $30-50\n");
    printf("    Rational choice:           BUY REAL HARDWARE\n");
    printf("\n");

    return v.valid ? 0 : 1;
}
