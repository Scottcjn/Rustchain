/**
 * numa_shard_bench.c — Benchmark NUMA-sharded vs flat tensor allocation
 *
 * Measures per-node memory bandwidth using sequential and random access
 * patterns, then compares flat mmap against NUMA-pinned allocation.
 *
 * Build:
 *   gcc -O3 -mcpu=power8 -mvsx -lnuma numa_shard_bench.c -o numa_bench
 *   gcc -O3 -march=native -lnuma numa_shard_bench.c -o numa_bench  # x86
 *
 * Usage:
 *   ./numa_bench [--size-mb N] [--iterations N]
 *
 * License: MIT
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <sys/mman.h>

#ifdef __linux__
#include <numaif.h>
#include <sched.h>
#include <unistd.h>
#include <dirent.h>
#endif

/* ------------------------------------------------------------------ */
/*  Config                                                             */
/* ------------------------------------------------------------------ */

#define DEFAULT_SIZE_MB    256
#define DEFAULT_ITERATIONS 5
#define CACHE_LINE         128   /* POWER8 has 128-byte cache lines */

/* ------------------------------------------------------------------ */
/*  Timing                                                             */
/* ------------------------------------------------------------------ */

static double now_sec(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec * 1e-9;
}

/* ------------------------------------------------------------------ */
/*  NUMA helpers                                                       */
/* ------------------------------------------------------------------ */

static int detect_numa_nodes(void) {
#ifdef __linux__
    DIR *d = opendir("/sys/devices/system/node");
    struct dirent *ent;
    int count = 0;
    if (!d) return 1;
    while ((ent = readdir(d)) != NULL) {
        if (strncmp(ent->d_name, "node", 4) == 0) count++;
    }
    closedir(d);
    return count > 0 ? count : 1;
#else
    return 1;
#endif
}

static void *alloc_on_node(size_t size, int node) {
    void *p = mmap(NULL, size, PROT_READ | PROT_WRITE,
                   MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (p == MAP_FAILED) return NULL;

#ifdef __linux__
    unsigned long nodemask = 1UL << node;
    mbind(p, size, MPOL_BIND, &nodemask, 64, MPOL_MF_MOVE | MPOL_MF_STRICT);
#endif

    /* Fault pages to ensure physical allocation */
    memset(p, 0, size);
    return p;
}

static void *alloc_flat(size_t size) {
    void *p = mmap(NULL, size, PROT_READ | PROT_WRITE,
                   MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (p == MAP_FAILED) return NULL;
    memset(p, 0, size);
    return p;
}

/* ------------------------------------------------------------------ */
/*  Benchmark kernels                                                  */
/* ------------------------------------------------------------------ */

/* Sequential read: sum all 64-bit words */
static double bench_seq_read(const void *buf, size_t size) {
    const volatile unsigned long *p = (const volatile unsigned long *)buf;
    size_t n = size / sizeof(unsigned long);
    size_t i;
    unsigned long sum = 0;
    double t0 = now_sec();

    for (i = 0; i < n; i += CACHE_LINE / sizeof(unsigned long)) {
        sum += p[i];
    }

    double elapsed = now_sec() - t0;
    (void)sum;

    /* Bytes actually read (one cache line per stride) */
    size_t bytes_read = (n / (CACHE_LINE / sizeof(unsigned long))) * CACHE_LINE;
    return (double)bytes_read / elapsed / (1024.0 * 1024.0);  /* MB/s */
}

/* Sequential write: store pattern */
static double bench_seq_write(void *buf, size_t size) {
    volatile unsigned long *p = (volatile unsigned long *)buf;
    size_t n = size / sizeof(unsigned long);
    size_t i;
    double t0 = now_sec();

    for (i = 0; i < n; i += CACHE_LINE / sizeof(unsigned long)) {
        p[i] = (unsigned long)i;
    }

    double elapsed = now_sec() - t0;
    size_t bytes_written = (n / (CACHE_LINE / sizeof(unsigned long))) * CACHE_LINE;
    return (double)bytes_written / elapsed / (1024.0 * 1024.0);
}

/* Random read: chase pointers (latency-bound) */
static double bench_random_read(const void *buf, size_t size) {
    const unsigned long *p = (const unsigned long *)buf;
    size_t n = size / sizeof(unsigned long);
    size_t idx = 0;
    size_t count = n / 4;  /* fewer iterations for random */
    size_t i;
    unsigned long sum = 0;
    double t0 = now_sec();

    for (i = 0; i < count; i++) {
        sum += p[idx];
        idx = (idx * 6364136223846793005ULL + 1442695040888963407ULL) % n;
    }

    double elapsed = now_sec() - t0;
    (void)sum;
    return (double)(count * sizeof(unsigned long)) / elapsed / (1024.0 * 1024.0);
}

/* ------------------------------------------------------------------ */
/*  Results                                                            */
/* ------------------------------------------------------------------ */

typedef struct {
    double seq_read_mbs;
    double seq_write_mbs;
    double random_read_mbs;
} bench_result;

static bench_result run_bench(void *buf, size_t size, int iterations) {
    bench_result best = {0, 0, 0};
    int i;

    for (i = 0; i < iterations; i++) {
        double sr = bench_seq_read(buf, size);
        double sw = bench_seq_write(buf, size);
        double rr = bench_random_read(buf, size);

        if (sr > best.seq_read_mbs)    best.seq_read_mbs = sr;
        if (sw > best.seq_write_mbs)   best.seq_write_mbs = sw;
        if (rr > best.random_read_mbs) best.random_read_mbs = rr;
    }
    return best;
}

/* ------------------------------------------------------------------ */
/*  Main                                                               */
/* ------------------------------------------------------------------ */

int main(int argc, char **argv) {
    int size_mb    = DEFAULT_SIZE_MB;
    int iterations = DEFAULT_ITERATIONS;
    int i;

    /* Parse args */
    for (i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--size-mb") == 0 && i + 1 < argc)
            size_mb = atoi(argv[++i]);
        else if (strcmp(argv[i], "--iterations") == 0 && i + 1 < argc)
            iterations = atoi(argv[++i]);
        else if (strcmp(argv[i], "--help") == 0) {
            printf("Usage: %s [--size-mb N] [--iterations N]\n", argv[0]);
            return 0;
        }
    }

    size_t size = (size_t)size_mb * 1024 * 1024;
    int num_nodes = detect_numa_nodes();

    printf("NUMA Shard Benchmark\n");
    printf("====================\n");
    printf("Buffer size:  %d MiB per test\n", size_mb);
    printf("Iterations:   %d (best of)\n", iterations);
    printf("NUMA nodes:   %d\n", num_nodes);
    printf("Cache line:   %d bytes\n", CACHE_LINE);
#ifdef __powerpc__
    printf("Architecture: POWER (VSX enabled)\n");
#elif defined(__x86_64__)
    printf("Architecture: x86_64\n");
#elif defined(__aarch64__)
    printf("Architecture: AArch64\n");
#else
    printf("Architecture: unknown\n");
#endif
    printf("\n");

    /* ---- Per-node bandwidth ---- */
    printf("%-8s  %12s  %12s  %12s\n",
           "Node", "Seq Read", "Seq Write", "Random Read");
    printf("--------  ------------  ------------  ------------\n");

    bench_result node_results[GGML_NUMA_MAX_NODES];

    for (i = 0; i < num_nodes && i < 16; i++) {
        void *buf = alloc_on_node(size, i);
        if (!buf) {
            fprintf(stderr, "Failed to allocate on node %d\n", i);
            continue;
        }

        node_results[i] = run_bench(buf, size, iterations);
        printf("Node %-3d  %9.1f MB/s  %9.1f MB/s  %9.1f MB/s\n",
               i,
               node_results[i].seq_read_mbs,
               node_results[i].seq_write_mbs,
               node_results[i].random_read_mbs);

        munmap(buf, size);
    }

    /* ---- Flat allocation baseline ---- */
    printf("\n--- Flat (default mmap) ---\n");
    {
        void *buf = alloc_flat(size);
        if (buf) {
            bench_result flat = run_bench(buf, size, iterations);
            printf("Flat      %9.1f MB/s  %9.1f MB/s  %9.1f MB/s\n",
                   flat.seq_read_mbs, flat.seq_write_mbs, flat.random_read_mbs);

            /* Find best NUMA node for comparison */
            double best_numa_sr = 0;
            for (i = 0; i < num_nodes && i < 16; i++) {
                if (node_results[i].seq_read_mbs > best_numa_sr)
                    best_numa_sr = node_results[i].seq_read_mbs;
            }

            if (flat.seq_read_mbs > 0) {
                printf("\nSpeedup (best NUMA node vs flat): %.2fx seq read\n",
                       best_numa_sr / flat.seq_read_mbs);
            }

            munmap(buf, size);
        }
    }

    /* ---- Sharded simulation: assign layers across nodes ---- */
    printf("\n--- Sharded Simulation (32 layers across %d nodes) ---\n", num_nodes);
    {
        int total_layers = 32;
        double total_time = 0;
        size_t layer_size = size / 4;  /* smaller per layer */

        double t0 = now_sec();
        for (i = 0; i < total_layers && i < 128; i++) {
            int node = i % num_nodes;
            void *buf = alloc_on_node(layer_size, node);
            if (buf) {
                bench_seq_read(buf, layer_size);
                munmap(buf, layer_size);
            }
        }
        total_time = now_sec() - t0;

        double total_bytes = (double)total_layers * layer_size;
        printf("Sharded:  %.1f MB/s aggregate (%.3f s for %d layers × %zu MiB)\n",
               total_bytes / total_time / (1024.0 * 1024.0),
               total_time, total_layers, layer_size / (1024 * 1024));

        /* Flat comparison */
        void *flat_buf = alloc_flat(layer_size);
        if (flat_buf) {
            t0 = now_sec();
            for (i = 0; i < total_layers; i++) {
                bench_seq_read(flat_buf, layer_size);
            }
            double flat_time = now_sec() - t0;
            printf("Flat:     %.1f MB/s aggregate (%.3f s)\n",
                   total_bytes / flat_time / (1024.0 * 1024.0), flat_time);
            printf("Sharding speedup: %.2fx\n",
                   flat_time / (total_time > 0 ? total_time : 1));
            munmap(flat_buf, layer_size);
        }
    }

    printf("\nDone.\n");
    return 0;
}
