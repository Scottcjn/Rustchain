/**
 * @file ggml-numa-shard.c
 * @brief Extended NUMA sharding implementation for llama.cpp
 * 
 * Optional C implementation file providing additional functionality
 * beyond the header-only version. Use this when you need:
 * - Advanced statistics tracking
 * - Runtime rebalancing
 * - Custom allocation hooks
 * 
 * @version 1.0.0
 * @date 2026-03-23
 * @bounty Scottcjn/rustchain-bounties #2277
 */

#include "ggml-numa-shard.h"
#include <pthread.h>
#include <time.h>
#include <errno.h>

#if defined(GGML_NUMA_LINUX)
#include <sys/mman.h>
#include <fcntl.h>
#endif

/* ============================================================================
 * Extended Statistics Structure
 * ============================================================================ */

struct ggml_numa_extended_stats {
    /* Timing */
    struct timespec init_time;
    struct timespec last_bind_time;
    
    /* Detailed per-node stats */
    struct {
        size_t alloc_count;
        size_t free_count;
        size_t migrate_count;
        size_t fail_count;
        size_t total_bytes;
        double avg_bind_time_us;
    } node_stats[GGML_NUMA_MAX_NODES];
    
    /* Thread affinity tracking */
    int thread_cpu_map[GGML_NUMA_MAX_NODES];
    int num_threads_tracked;
};

static struct ggml_numa_extended_stats g_ext_stats = {0};
static pthread_mutex_t g_stats_mutex = PTHREAD_MUTEX_INITIALIZER;

/* ============================================================================
 * High-Precision Timing
 * ============================================================================ */

static inline double get_time_us(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1e6 + ts.tv_nsec / 1e3;
}

/* ============================================================================
 * Extended API Implementation
 * ============================================================================ */

/**
 * @brief Initialize with extended statistics
 */
int ggml_numa_shard_init_extended(const char *config_string) {
    pthread_mutex_lock(&g_stats_mutex);
    memset(&g_ext_stats, 0, sizeof(g_ext_stats));
    clock_gettime(CLOCK_MONOTONIC, &g_ext_stats.init_time);
    pthread_mutex_unlock(&g_stats_mutex);
    
    return ggml_numa_shard_init(config_string);
}

/**
 * @brief Bind with timing and detailed statistics
 */
int ggml_numa_shard_bind_extended(void *addr, size_t len, int numa_node) {
    if (!addr || len == 0 || numa_node < 0) {
        return -1;
    }
    
    double start_time = get_time_us();
    
    int ret = ggml_numa_shard_bind_memory(addr, len, numa_node);
    
    double elapsed = get_time_us() - start_time;
    
    pthread_mutex_lock(&g_stats_mutex);
    g_ext_stats.last_bind_time = (struct timespec){0};
    clock_gettime(CLOCK_MONOTONIC, &g_ext_stats.last_bind_time);
    
    if (ret == 0) {
        g_ext_stats.node_stats[numa_node].alloc_count++;
        g_ext_stats.node_stats[numa_node].total_bytes += len;
        
        /* Update running average */
        size_t n = g_ext_stats.node_stats[numa_node].alloc_count;
        double avg = g_ext_stats.node_stats[numa_node].avg_bind_time_us;
        g_ext_stats.node_stats[numa_node].avg_bind_time_us = 
            avg + (elapsed - avg) / n;
    } else {
        g_ext_stats.node_stats[numa_node].fail_count++;
    }
    pthread_mutex_unlock(&g_stats_mutex);
    
    return ret;
}

/**
 * @brief Migrate pages with progress tracking
 */
int ggml_numa_shard_migrate_extended(void *addr, size_t len, 
                                      int from_node, int to_node,
                                      size_t *migrated_bytes) {
    if (!g_ggml_numa_ctx.initialized || !ggml_numa_available()) {
        return 0;
    }
    
    long page_size = sysconf(_SC_PAGESIZE);
    if (page_size <= 0) page_size = 4096;
    
    long num_pages = len / page_size;
    if (num_pages == 0) return 0;
    
    void **pages = malloc(num_pages * sizeof(void*));
    int *nodes = malloc(num_pages * sizeof(int));
    int *status = malloc(num_pages * sizeof(int));
    
    if (!pages || !nodes || !status) {
        free(pages);
        free(nodes);
        free(status);
        return -1;
    }
    
    for (long i = 0; i < num_pages; i++) {
        pages[i] = (char*)addr + (i * page_size);
        nodes[i] = to_node;
        status[i] = 0;
    }
    
    int ret = move_pages(0, num_pages, pages, nodes, status, MPOL_MF_MOVE);
    
    size_t migrated = 0;
    if (ret >= 0) {
        for (long i = 0; i < num_pages; i++) {
            if (status[i] == 0) {
                migrated++;
            }
        }
        
        pthread_mutex_lock(&g_stats_mutex);
        g_ext_stats.node_stats[to_node].migrate_count += migrated;
        pthread_mutex_unlock(&g_stats_mutex);
    }
    
    if (migrated_bytes) {
        *migrated_bytes = migrated * page_size;
    }
    
    free(pages);
    free(nodes);
    free(status);
    
    return (ret < 0) ? ret : (int)migrated;
}

/**
 * @brief Pin current thread to a NUMA node's CPUs
 */
int ggml_numa_shard_pin_thread(int numa_node) {
#if defined(GGML_NUMA_LINUX)
    if (!ggml_numa_available()) {
        return -1;
    }
    
    struct bitmask *cpus = numa_allocate_cpumask();
    if (!cpus) {
        return -1;
    }
    
    /* Get CPUs for this NUMA node */
    int ret = numa_node_to_cpus(numa_node, cpus);
    if (ret < 0) {
        numa_free_cpumask(cpus);
        return -1;
    }
    
    /* Pin thread to these CPUs */
    ret = numa_sched_setaffinity(0, cpus);
    
    numa_free_cpumask(cpus);
    
    pthread_mutex_lock(&g_stats_mutex);
    if (g_ext_stats.num_threads_tracked < GGML_NUMA_MAX_NODES) {
        g_ext_stats.thread_cpu_map[g_ext_stats.num_threads_tracked] = numa_node;
        g_ext_stats.num_threads_tracked++;
    }
    pthread_mutex_unlock(&g_stats_mutex);
    
    return ret;
#else
    (void)numa_node;
    return -1;
#endif
}

/**
 * @brief Get detailed statistics as JSON string
 */
int ggml_numa_shard_get_stats_json(char *buffer, size_t buf_size) {
    if (!buffer || buf_size == 0) {
        return -1;
    }
    
    pthread_mutex_lock(&g_stats_mutex);
    
    int offset = 0;
    offset += snprintf(buffer + offset, buf_size - offset, "{\n");
    offset += snprintf(buffer + offset, buf_size - offset, 
                       "  \"initialized\": %s,\n", 
                       g_ggml_numa_ctx.initialized ? "true" : "false");
    offset += snprintf(buffer + offset, buf_size - offset, 
                       "  \"num_nodes\": %d,\n", g_ggml_numa_ctx.num_nodes);
    offset += snprintf(buffer + offset, buf_size - offset, 
                       "  \"num_rules\": %d,\n", g_ggml_numa_ctx.num_rules);
    offset += snprintf(buffer + offset, buf_size - offset, 
                       "  \"total_bytes_bound\": %zu,\n", 
                       g_ggml_numa_ctx.total_bytes_bound);
    offset += snprintf(buffer + offset, buf_size - offset, 
                       "  \"tensors_assigned\": %d,\n", 
                       g_ggml_numa_ctx.tensors_assigned);
    offset += snprintf(buffer + offset, buf_size - offset, 
                       "  \"bind_failures\": %d,\n", 
                       g_ggml_numa_ctx.bind_failures);
    offset += snprintf(buffer + offset, buf_size - offset, 
                       "  \"nodes\": [\n");
    
    for (int i = 0; i < g_ggml_numa_ctx.num_nodes; i++) {
        offset += snprintf(buffer + offset, buf_size - offset, 
                           "    {\n");
        offset += snprintf(buffer + offset, buf_size - offset, 
                           "      \"id\": %d,\n", i);
        offset += snprintf(buffer + offset, buf_size - offset, 
                           "      \"bytes\": %zu,\n", 
                           g_ggml_numa_ctx.bytes_per_node[i]);
        offset += snprintf(buffer + offset, buf_size - offset, 
                           "      \"alloc_count\": %zu,\n", 
                           g_ext_stats.node_stats[i].alloc_count);
        offset += snprintf(buffer + offset, buf_size - offset, 
                           "      \"fail_count\": %zu,\n", 
                           g_ext_stats.node_stats[i].fail_count);
        offset += snprintf(buffer + offset, buf_size - offset, 
                           "      \"avg_bind_time_us\": %.2f\n", 
                           g_ext_stats.node_stats[i].avg_bind_time_us);
        offset += snprintf(buffer + offset, buf_size - offset, 
                           "    }%s\n", (i < g_ggml_numa_ctx.num_nodes - 1) ? "," : "");
    }
    
    offset += snprintf(buffer + offset, buf_size - offset, "  ]\n");
    offset += snprintf(buffer + offset, buf_size - offset, "}\n");
    
    pthread_mutex_unlock(&g_stats_mutex);
    
    return offset;
}

/**
 * @brief Print extended statistics
 */
void ggml_numa_shard_print_extended_stats(void) {
    pthread_mutex_lock(&g_stats_mutex);
    
    fprintf(stdout, "\n========== Extended NUMA Statistics ==========\n");
    fprintf(stdout, "Initialization time: %ld.%09ld\n", 
            g_ext_stats.init_time.tv_sec, g_ext_stats.init_time.tv_nsec);
    fprintf(stdout, "Threads tracked:    %d\n", g_ext_stats.num_threads_tracked);
    
    fprintf(stdout, "\nPer-node detailed stats:\n");
    for (int i = 0; i < g_ggml_numa_ctx.num_nodes; i++) {
        struct {
            size_t alloc_count;
            size_t fail_count;
            size_t migrate_count;
            double avg_time;
        } *ns = &g_ext_stats.node_stats[i];
        
        if (ns->alloc_count > 0 || ns->fail_count > 0) {
            fprintf(stdout, "  Node %d:\n", i);
            fprintf(stdout, "    Allocations:  %zu\n", ns->alloc_count);
            fprintf(stdout, "    Failures:     %zu\n", ns->fail_count);
            fprintf(stdout, "    Migrations:   %zu\n", ns->migrate_count);
            fprintf(stdout, "    Avg bind:     %.2f µs\n", ns->avg_time);
            fprintf(stdout, "    Total bytes:  %zu MB\n", 
                    ns->total_bytes / (1024 * 1024));
        }
    }
    
    fprintf(stdout, "=============================================\n\n");
    
    pthread_mutex_unlock(&g_stats_mutex);
}

/**
 * @brief Validate NUMA configuration
 * 
 * Checks for common misconfigurations:
 * - Invalid node IDs
 * - Overlapping layer ranges
 * - Missing layers
 */
int ggml_numa_shard_validate_config(int total_layers) {
    if (!g_ggml_numa_ctx.initialized) {
        return -1;
    }
    
    int errors = 0;
    
    /* Check node IDs are valid */
    for (int i = 0; i < g_ggml_numa_ctx.num_rules; i++) {
        struct ggml_numa_shard_rule *rule = &g_ggml_numa_ctx.rules[i];
        if (rule->numa_node < 0 || rule->numa_node >= g_ggml_numa_ctx.num_nodes) {
            fprintf(stderr, "[NUMA] Error: Rule %d has invalid node %d\n", 
                    i, rule->numa_node);
            errors++;
        }
    }
    
    /* Check for overlapping ranges */
    for (int i = 0; i < g_ggml_numa_ctx.num_rules; i++) {
        struct ggml_numa_shard_rule *rule_i = &g_ggml_numa_ctx.rules[i];
        if (rule_i->is_pattern_match) continue;
        
        for (int j = i + 1; j < g_ggml_numa_ctx.num_rules; j++) {
            struct ggml_numa_shard_rule *rule_j = &g_ggml_numa_ctx.rules[j];
            if (rule_j->is_pattern_match) continue;
            
            if (rule_i->layer_end >= rule_j->layer_start &&
                rule_j->layer_end >= rule_i->layer_start) {
                fprintf(stderr, "[NUMA] Warning: Rules %d and %d overlap\n", i, j);
            }
        }
    }
    
    /* Check coverage */
    bool *covered = calloc(total_layers, sizeof(bool));
    if (covered) {
        for (int i = 0; i < g_ggml_numa_ctx.num_rules; i++) {
            struct ggml_numa_shard_rule *rule = &g_ggml_numa_ctx.rules[i];
            if (!rule->is_pattern_match) {
                for (int l = rule->layer_start; l <= rule->layer_end && l < total_layers; l++) {
                    covered[l] = true;
                }
            }
        }
        
        for (int l = 0; l < total_layers; l++) {
            if (!covered[l]) {
                fprintf(stderr, "[NUMA] Warning: Layer %d has no NUMA rule\n", l);
            }
        }
        
        free(covered);
    }
    
    return errors;
}

/* ============================================================================
 * POWER8-Specific Optimizations
 * ============================================================================ */

#if defined(GGML_NUMA_POWERPC)

/**
 * @brief Optimize for POWER8 S824 topology
 * 
 * S824 has 4 NUMA nodes with asymmetric bandwidth:
 * - Node 0: 215-225 MB/s (slowest)
 * - Node 1: ~350 MB/s
 * - Node 2/3: 400-425 MB/s (fastest)
 */
int ggml_numa_shard_optimize_power8_s824(void) {
    fprintf(stdout, "[NUMA] Applying POWER8 S824 optimizations\n");
    
    /* Use default S824 mapping */
    const char *s824_config = "0-8:1,9-20:3,21-31:2";
    return ggml_numa_shard_init(s824_config);
}

/**
 * @brief Get POWER8-specific recommendations
 */
const char* ggml_numa_shard_get_power8_recommendations(void) {
    return 
        "POWER8 S824 Recommendations:\n"
        "  - Use 64 threads (NOT 128)\n"
        "  - Bind attention layers to Node 3 (highest bandwidth)\n"
        "  - Bind FFN layers to Node 2 (highest bandwidth)\n"
        "  - Use numactl --cpunodebind for thread affinity\n"
        "  - Avoid Node 0 for compute-intensive layers";
}

#endif /* GGML_NUMA_POWERPC */

/* ============================================================================
 * Cleanup
 * ============================================================================ */

void ggml_numa_shard_cleanup_extended(void) {
    pthread_mutex_lock(&g_stats_mutex);
    ggml_numa_shard_print_extended_stats();
    memset(&g_ext_stats, 0, sizeof(g_ext_stats));
    pthread_mutex_unlock(&g_stats_mutex);
    
    ggml_numa_shard_cleanup();
}
