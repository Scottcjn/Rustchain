/*
 * numa_detect.c - NUMA Topology Detection Utility
 * 
 * Detect and display NUMA topology: number of nodes, memory per node,
 * distances, and memory bandwidth per node.
 * 
 * Compile: gcc -o numa_detect numa_detect.c -lnuma
 * 
 * Author: NUMA-LLAMA Team
 * License: MIT
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#ifdef __linux__
    #include <numa.h>
    #include <numaif.h>
#endif

/* ============================================================================
 * Configuration
 * ============================================================================ */

#define MAX_NODES 16
#define MEMORY_TEST_SIZE_MB 64
#define MEMORY_TEST_ITERATIONS 5

/* ============================================================================
 * Memory Bandwidth Measurement
 * ============================================================================ */

typedef struct {
    int    node;
    double bandwidth_mbps;  /* MB/s */
    size_t memory_mb;
} node_bandwidth_t;

static double measure_node_bandwidth(int node, int size_mb) {
#ifdef __linux__
    if (numa_available() < 0) return -1;
    
    size_t size = (size_t)size_mb * 1024 * 1024;
    
    /* Allocate buffer on target node */
    void * src = numa_alloc_onnode(size, node);
    if (!src) {
        fprintf(stderr, "Failed to allocate %d MB on node %d\n", size_mb, node);
        return -1;
    }
    
    void * dst = numa_alloc_onnode(size, node);
    if (!dst) {
        fprintf(stderr, "Failed to allocate destination buffer on node %d\n", node);
        numa_free(src, size);
        return -1;
    }
    
    /* Initialize with non-zero data to prevent zero-page optimization */
    memset(src, 0x55, size);
    memset(dst, 0xAA, size);
    
    /* Warmup */
    memcpy(dst, src, size);
    
    /* Measure bandwidth */
    struct timespec start, end;
    clock_gettime(CLOCK_MONOTONIC, &start);
    
    for (int i = 0; i < MEMORY_TEST_ITERATIONS; i++) {
        memcpy(dst, src, size);
    }
    
    clock_gettime(CLOCK_MONOTONIC, &end);
    
    double elapsed_s = (end.tv_sec - start.tv_sec) + 
                       (end.tv_nsec - start.tv_nsec) / 1e9;
    
    double bandwidth = (size_mb * MEMORY_TEST_ITERATIONS) / elapsed_s;
    
    numa_free(src, size);
    numa_free(dst, size);
    
    return bandwidth;
#else
    (void)node; (void)size_mb;
    return -1;
#endif
}

/* ============================================================================
 * CPU Affinity Detection
 * ============================================================================ */

static void print_node_cpus(int node) {
#ifdef __linux__
    struct bitmask * mask = numa_allocate_nodemask();
    numa_bitmask_setbit(mask, node);
    
    printf("  CPUs on node %d: ", node);
    
    /* Get list of CPUs */
    for (int cpu = 0; cpu < numa_num_possible_cpus(); cpu++) {
        if (numa_node_has_cpu(node, cpu)) {
            printf("%d ", cpu);
        }
    }
    
    printf("\n");
    numa_free_nodemask(mask);
#else
    (void)node;
#endif
}

/* ============================================================================
 * Main
 * ============================================================================ */

int main(int argc, char ** argv) {
    printf("==================================================\n");
    printf("    NUMA Topology Detection Utility\n");
    printf("    POWER8 S824 (4 NUMA Nodes, 512GB RAM)\n");
    printf("==================================================\n\n");
    
#ifdef __linux__
    if (numa_available() < 0) {
        printf("ERROR: NUMA not available on this system\n");
        return 1;
    }
    
    int num_nodes = numa_max_node() + 1;
    printf("System has %d NUMA node(s)\n\n", num_nodes);
    
    /* Detect CPUs per node */
    printf("=== CPU Topology ===\n");
    for (int node = 0; node < num_nodes; node++) {
        print_node_cpus(node);
    }
    printf("===================\n\n");
    
    /* Memory per node */
    printf("=== Memory per Node ===\n");
    unsigned long total_memory = 0;
    for (int node = 0; node < num_nodes; node++) {
        unsigned long size = numa_node_size(node, NULL);
        long long free_size = 0;
        numa_node_size(node, &free_size);
        
        total_memory += size;
        
        double size_gb = size / (1024.0 * 1024.0 * 1024.0);
        double free_gb = free_size / (1024.0 * 1024.0 * 1024.0);
        
        printf("Node %d:\n", node);
        printf("  Total: %.2f GB\n", size_gb);
        printf("  Free:  %.2f GB\n", free_gb);
    }
    printf("Total system memory: %.2f GB\n", total_memory / (1024.0 * 1024.0 * 1024.0));
    printf("========================\n\n");
    
    /* NUMA distances */
    printf("=== NUMA Distances (hop cost) ===\n");
    printf("      ");
    for (int j = 0; j < num_nodes; j++) {
        printf("  Node%d", j);
    }
    printf("\n");
    
    for (int i = 0; i < num_nodes; i++) {
        printf("Node%d  ", i);
        for (int j = 0; j < num_nodes; j++) {
            int dist = numa_distance(i, j);
            printf("  %4d", dist);
        }
        printf("\n");
    }
    printf("===================================\n\n");
    
    /* Memory bandwidth per node */
    printf("=== Memory Bandwidth per Node ===\n");
    printf("(Using %d MB copy test, %d iterations)\n\n", 
           MEMORY_TEST_SIZE_MB, MEMORY_TEST_ITERATIONS);
    
    node_bandwidth_t results[MAX_NODES];
    int fastest_node = -1;
    double fastest_bw = 0;
    
    for (int node = 0; node < num_nodes; node++) {
        double bw = measure_node_bandwidth(node, MEMORY_TEST_SIZE_MB);
        results[node].node = node;
        results[node].bandwidth_mbps = bw;
        
        if (bw > fastest_bw) {
            fastest_bw = bw;
            fastest_node = node;
        }
        
        if (bw > 0) {
            printf("Node %d: %.0f MB/s\n", node, bw);
        } else {
            printf("Node %d: (measurement failed)\n", node);
        }
    }
    
    if (fastest_node >= 0) {
        printf("\n==> Fastest memory: Node %d (%.0f MB/s)\n", fastest_node, fastest_bw);
    }
    printf("=================================\n\n");
    
    /* Optimal NUMA placement recommendations */
    printf("=== Optimal Layer Placement ===\n");
    printf("Based on POWER8 S824 memory characteristics:\n\n");
    
    /* Find slowest node */
    int slowest_node = -1;
    double slowest_bw = 1e9;
    for (int node = 0; node < num_nodes; node++) {
        if (results[node].bandwidth_mbps > 0 && 
            results[node].bandwidth_mbps < slowest_bw) {
            slowest_bw = results[node].bandwidth_mbps;
            slowest_node = node;
        }
    }
    
    if (slowest_node >= 0) {
        printf("- Node %d (%.0f MB/s): SLOWEST - use for embeddings, early layers\n",
               slowest_node, slowest_bw);
    }
    
    if (fastest_node >= 0 && fastest_node != slowest_node) {
        printf("- Node %d (%.0f MB/s): FASTEST - use for attention layers\n",
               fastest_node, fastest_bw);
    }
    
    printf("- Attention layers: Node %d (high BW, frequent access)\n", 
           fastest_node >= 0 ? fastest_node : 3);
    printf("- FFN layers: Node 2 (second fastest)\n");
    printf("- Early layers (0-7): Node 0 (embedding)\n");
    printf("- Transformer blocks (8-31): Node 1\n");
    printf("- KV cache: Node 3\n");
    printf("=============================\n\n");
    
    /* Environment variable suggestion */
    printf("=== Recommended GGML_NUMA_SHARD_MAP ===\n");
    printf("export GGML_NUMA_SHARD_MAP=\"0-7:node%d,8-19:node1,20-31:node2,attn:node%d\"\n",
           slowest_node >= 0 ? slowest_node : 0,
           fastest_node >= 0 ? fastest_node : 3);
    printf("=======================================\n\n");
    
#else
    printf("ERROR: This tool requires Linux with libnuma\n");
    printf("Install: sudo apt-get install libnuma-dev\n");
    return 1;
#endif
    
    printf("Detection complete.\n");
    return 0;
}
