/*
 * ggml-numa-shard.h - NUMA-Aware Layer Sharding for llama.cpp
 * 
 * Header-only NUMA shard router for IBM POWER8 S824 (4 NUMA nodes).
 * Parse GGUF tensor metadata and pin transformer layers to optimal NUMA nodes.
 * 
 * Compile: GCC 9+, -mcpu=power8 -mvsx (POWER8) or standard x86_64 (x86)
 * 
 * Author: NUMA-LLAMA Team
 * License: MIT
 */

#ifndef GGML_NUMA_SHARD_H
#define GGML_NUMA_SHARD_H

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ============================================================================
 * Platform Detection
 * ============================================================================ */

#if defined(__powerpc__) || defined(__powerpc64__) || defined(__ppc__) || defined(__ppc64__)
    #define GGML_NUMA_ARCH_POWER 1
    #include <sched.h>
#else
    #define GGML_NUMA_ARCH_POWER 0
#endif

#if defined(__linux__)
    #define GGML_NUMA_LINUX 1
#else
    #define GGML_NUMA_LINUX 0
#endif

/* ============================================================================
 * NUMA Configuration
 * ============================================================================ */

/* Default NUMA node assignment for POWER8 S824 (4 nodes, 512GB RAM) */
#define GGML_NUMA_MAX_NODES 16
#define GGML_NUMA_DEFAULT_NODE_COUNT 4

/* Layer type classification */
typedef enum {
    GGML_NUMA_LAYER_UNKNOWN = 0,
    GGML_NUMA_LAYER_EMBEDDING,      /* token embeddings */
    GGML_NUMA_LAYER_BLOCK,          /* transformer block (blk.*) */
    GGML_NUMA_LAYER_ATTENTION,      /* attention layer (attn.*) */
    GGML_NUMA_LAYER_FFN,            /* feed-forward network (ffn.*) */
    GGML_NUMA_LAYER_OUTPUT,          /* output layer */
    GGML_NUMA_LAYER_NORM,           /* layer normalization */
} ggml_numa_layer_type_t;

/* Tensor information */
typedef struct {
    const char * name;
    uint64_t     offset;
    uint64_t     size;
    int          numa_node;           /* assigned NUMA node (-1 = unassigned) */
    ggml_numa_layer_type_t type;
} ggml_numa_tensor_t;

/* GGUF metadata header (simplified) */
typedef struct {
    uint32_t magic;
    uint32_t version;
    uint64_t tensor_count;
    uint64_t metadata_kv_count;
} ggml_numa_gguf_header_t;

/* Sharding configuration */
typedef struct {
    int      node_count;
    int      layer_to_node[256];      /* layer index -> NUMA node mapping */
    int      attn_node;               /* dedicated node for attention */
    int      ffn_node;                /* dedicated node for FFN */
    int      default_node;            /* fallback node */
    bool     enabled;
    bool     verbose;
} ggml_numa_shard_config_t;

/* Global sharding state */
extern ggml_numa_shard_config_t g_ggml_numa_config;

/* ============================================================================
 * Public API
 * ============================================================================ */

/*
 * Initialize NUMA sharding from environment variable GGML_NUMA_SHARD_MAP.
 * 
 * Format: "0-8:node0,9-20:node1,21-31:node2,attn:node3"
 *   - Range mapping: "L-R:nodeN" maps layers [L,R] to node N
 *   - Type mapping: "attn:nodeN" maps attention layers to node N
 *   - Special: "blk:N" maps transformer blocks to node N
 * 
 * Returns: 0 on success, -1 on error.
 */
int numa_init_sharding(void);

/*
 * Parse GGUF file tensor metadata and classify layers.
 * 
 * Parameters:
 *   - gguf_path: Path to GGUF model file
 *   - tensors: Output array of tensor descriptors
 *   - max_tensors: Maximum number of tensors to parse
 * 
 * Returns: Number of tensors parsed, -1 on error.
 */
int numa_parse_gguf(const char * gguf_path, 
                    ggml_numa_tensor_t * tensors, 
                    int max_tensors);

/*
 * Assign layers to NUMA nodes based on GGML_NUMA_SHARD_MAP policy.
 * 
 * Parameters:
 *   - tensors: Array of parsed tensors
 *   - count: Number of tensors
 *   - config: Sharding configuration (NULL = use global config)
 * 
 * Returns: 0 on success, -1 on error.
 */
int numa_assign_layers(ggml_numa_tensor_t * tensors, 
                       int count,
                       const ggml_numa_shard_config_t * config);

/*
 * Pin a tensor's memory region to a specific NUMA node.
 * 
 * Uses mbind() on Linux or move_pages() for memory migration.
 * 
 * Parameters:
 *   - addr: Pointer to tensor memory
 *   - size: Size of tensor in bytes
 *   - node: Target NUMA node
 * 
 * Returns: 0 on success, -1 on error.
 */
int numa_pin_tensor(void * addr, size_t size, int node);

/*
 * Detect which NUMA node a given address belongs to.
 * 
 * Parameters:
 *   - addr: Memory address to query
 * 
 * Returns: NUMA node number (0-N), -1 if unknown.
 */
int numa_get_node_of_addr(const void * addr);

/*
 * Parse tensor name to determine layer type.
 * 
 * Patterns recognized:
 *   - "token_embd" / "embedding" → GGML_NUMA_LAYER_EMBEDDING
 *   - "blk.N." (N = layer index) → GGML_NUMA_LAYER_BLOCK
 *   - "attn." → GGML_NUMA_LAYER_ATTENTION
 *   - "ffn." / "feed_forward" → GGML_NUMA_LAYER_FFN
 *   - "output" / "lm_head" → GGML_NUMA_LAYER_OUTPUT
 *   - "ln" / "layer_norm" → GGML_NUMA_LAYER_NORM
 * 
 * Returns: Layer type enum.
 */
ggml_numa_layer_type_t numa_classify_tensor(const char * name);

/*
 * Get layer index from tensor name.
 * 
 * Extracts the layer number from names like "blk.12.attn_q.weight".
 * 
 * Parameters:
 *   - name: Tensor name
 * 
 * Returns: Layer index (0-N) or -1 if not a layered tensor.
 */
int numa_get_layer_index(const char * name);

/*
 * Print current sharding configuration (for debugging).
 */
void numa_print_config(void);

/*
 * Get NUMA node count on this system.
 * 
 * Returns: Number of NUMA nodes, or 1 if NUMA not available.
 */
int numa_get_node_count(void);

/*
 * Estimate memory bandwidth of a NUMA node (MB/s).
 * 
 * Uses simple memory copy benchmark.
 * 
 * Parameters:
 *   - node: NUMA node to test
 *   - size_mb: Size of test buffer in MB
 * 
 * Returns: Estimated bandwidth in MB/s, -1 on error.
 */
double numa_measure_node_bandwidth(int node, int size_mb);

/* ============================================================================
 * Implementation (header-only for single-file deployment)
 * ============================================================================ */

#if defined(GGML_NUMA_IMPLEMENTATION) || defined(GGML_NUMA_HEADER_ONLY)

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>

/* Global configuration */
ggml_numa_shard_config_t g_ggml_numa_config = {
    .node_count = 1,
    .attn_node = 3,
    .ffn_node = 2,
    .default_node = 0,
    .enabled = false,
    .verbose = false
};

/* NUMA headers (Linux only) */
#if GGML_NUMA_LINUX
    #define NUMA_VERSION1_COMPATIBILITY 1
    #include <numa.h>
    #include <numaif.h>
    #include <unistd.h>
    #include <sys/mman.h>
    #include <fcntl.h>
#endif

/* ============================================================================
 * Environment Variable Parsing
 * ============================================================================ */

static int parse_numa_map(const char * env_value) {
    if (!env_value || !*env_value) {
        return -1;
    }
    
    /* Reset layer mapping */
    memset(g_ggml_numa_config.layer_to_node, -1, sizeof(g_ggml_numa_config.layer_to_node));
    
    /* Parse comma-separated entries */
    char * buf = strdup(env_value);
    if (!buf) return -1;
    
    char * token = strtok(buf, ",");
    while (token) {
        char * colon = strchr(token, ':');
        if (colon) {
            *colon = '\0';
            const char * range = token;
            const char * node_str = colon + 1;
            
            int node = -1;
            if (strncmp(node_str, "node", 4) == 0) {
                node = atoi(node_str + 4);
            } else if (strcmp(node_str, "attn") == 0) {
                node = -2; /* Special marker for attention */
            } else if (strcmp(node_str, "ffn") == 0) {
                node = -3; /* Special marker for FFN */
            } else if (strcmp(node_str, "blk") == 0) {
                node = -4; /* Special marker for blocks */
            }
            
            if (node >= -4 && node < (int)GGML_NUMA_MAX_NODES) {
                /* Parse range or type */
                if (strcmp(range, "attn") == 0) {
                    g_ggml_numa_config.attn_node = (node == -2) ? 0 : node;
                } else if (strcmp(range, "ffn") == 0) {
                    g_ggml_numa_config.ffn_node = (node == -3) ? 0 : node;
                } else if (strcmp(range, "blk") == 0) {
                    g_ggml_numa_config.default_node = (node == -4) ? 0 : node;
                } else {
                    /* Range like "0-8" or single number */
                    char * dash = strchr(range, '-');
                    if (dash) {
                        int start = atoi(range);
                        int end = atoi(dash + 1);
                        for (int i = start; i <= end && i < 256; i++) {
                            g_ggml_numa_config.layer_to_node[i] = node;
                        }
                    } else {
                        int idx = atoi(range);
                        if (idx < 256) {
                            g_ggml_numa_config.layer_to_node[idx] = node;
                        }
                    }
                }
            }
        }
        token = strtok(NULL, ",");
    }
    
    free(buf);
    return 0;
}

int numa_init_sharding(void) {
#if GGML_NUMA_LINUX && GGML_NUMA_ARCH_POWER
    /* Initialize libnuma */
    if (numa_available() < 0) {
        if (g_ggml_numa_config.verbose) {
            fprintf(stderr, "[numa] NUMA not available on this system\n");
        }
        g_ggml_numa_config.enabled = false;
        return -1;
    }
    
    g_ggml_numa_config.node_count = numa_max_node() + 1;
    
    /* Parse GGML_NUMA_SHARD_MAP if set */
    const char * env_map = getenv("GGML_NUMA_SHARD_MAP");
    if (env_map) {
        if (parse_numa_map(env_map) == 0) {
            g_ggml_numa_config.enabled = true;
            if (g_ggml_numa_config.verbose) {
                fprintf(stderr, "[numa] Sharding enabled via GGML_NUMA_SHARD_MAP\n");
                fprintf(stderr, "[numa] Node count: %d, attn_node: %d, ffn_node: %d\n",
                        g_ggml_numa_config.node_count,
                        g_ggml_numa_config.attn_node,
                        g_ggml_numa_config.ffn_node);
            }
        }
    } else {
        /* Use POWER8-optimized defaults:
         * - Layers 0-7: Node 0 (embedding, early layers)
         * - Layers 8-19: Node 1 (mid layers)
         * - Layers 20-31: Node 2 (FFN heavy)
         * - Attention: Node 3 (attention compute)
         */
        g_ggml_numa_config.enabled = true;
        for (int i = 0; i < 256; i++) {
            if (i <= 7) g_ggml_numa_config.layer_to_node[i] = 0;
            else if (i <= 19) g_ggml_numa_config.layer_to_node[i] = 1;
            else if (i <= 31) g_ggml_numa_config.layer_to_node[i] = 2;
            else g_ggml_numa_config.layer_to_node[i] = 0;
        }
        g_ggml_numa_config.attn_node = 3;
        g_ggml_numa_config.ffn_node = 2;
        
        if (g_ggml_numa_config.verbose) {
            fprintf(stderr, "[numa] Using POWER8 default sharding policy\n");
        }
    }
    
    return g_ggml_numa_config.enabled ? 0 : -1;
#else
    g_ggml_numa_config.enabled = false;
    return -1;
#endif
}

/* ============================================================================
 * GGUF Tensor Metadata Parsing
 * ============================================================================ */

/* GGUF magic number */
#define GGUF_MAGIC 0x46554747  /* "GGUF" little-endian */

/* Tensor info structure (from GGUF spec) */
typedef struct {
    char     name[128];
    uint32_t n_dims;
    uint64_t dims[4];
    uint32_t dtype;
    uint64_t offset;
} __attribute__((packed)) gguf_tensor_info_t;

int numa_parse_gguf(const char * gguf_path,
                    ggml_numa_tensor_t * tensors,
                    int max_tensors) {
#if GGML_NUMA_LINUX
    int fd = open(gguf_path, O_RDONLY);
    if (fd < 0) {
        fprintf(stderr, "[numa] Cannot open GGUF file: %s\n", gguf_path);
        return -1;
    }
    
    ggml_numa_gguf_header_t header;
    if (read(fd, &header, sizeof(header)) != sizeof(header)) {
        fprintf(stderr, "[numa] Cannot read GGUF header\n");
        close(fd);
        return -1;
    }
    
    if (header.magic != GGUF_MAGIC) {
        fprintf(stderr, "[numa] Invalid GGUF magic: 0x%08X\n", header.magic);
        close(fd);
        return -1;
    }
    
    /* Skip metadata kv pairs */
    for (uint64_t i = 0; i < header.metadata_kv_count; i++) {
        char key[256];
        uint32_t tag;
        
        /* Read tag */
        if (read(fd, &tag, sizeof(tag)) != sizeof(tag)) break;
        
        /* Read key (tagged string) */
        uint32_t key_len;
        if (read(fd, &key_len, sizeof(key_len)) != sizeof(key_len)) break;
        if (key_len < sizeof(key)) {
            read(fd, key, key_len);
            key[key_len] = '\0';
        }
        
        /* Skip value based on tag */
        switch (tag) {
            case 3: { /* string */ uint32_t len; read(fd, &len, 4); lseek(fd, len, SEEK_CUR); break; }
            case 4: { /* uint32 */ lseek(fd, 4, SEEK_CUR); break; }
            case 5: { /* uint64 */ lseek(fd, 8, SEEK_CUR); break; }
            case 8: { /* float32 */ lseek(fd, 4, SEEK_CUR); break; }
            default: break;
        }
    }
    
    /* Read tensor info */
    int count = 0;
    for (uint64_t i = 0; i < header.tensor_count && count < max_tensors; i++) {
        gguf_tensor_info_t info;
        
        /* Read tensor info */
        uint32_t name_len;
        if (read(fd, &name_len, sizeof(name_len)) != sizeof(name_len)) break;
        if (name_len < sizeof(info.name)) {
            read(fd, info.name, name_len);
            info.name[name_len] = '\0';
        } else {
            read(fd, info.name, sizeof(info.name) - 1);
            info.name[sizeof(info.name) - 1] = '\0';
            lseek(fd, name_len - sizeof(info.name) + 1, SEEK_CUR);
        }
        
        read(fd, &info.n_dims, sizeof(info.n_dims));
        for (uint32_t d = 0; d < info.n_dims && d < 4; d++) {
            read(fd, &info.dims[d], sizeof(info.dims[d]));
        }
        read(fd, &info.dtype, sizeof(info.dtype));
        read(fd, &info.offset, sizeof(info.offset));
        
        /* Calculate tensor size */
        uint64_t size = 1;
        for (uint32_t d = 0; d < info.n_dims; d++) {
            size *= info.dims[d];
        }
        /* dtype size: 0=float32(4), 1=float16(2), 2=bfloat16(2), 3=fp8(1), 4=q8(1), 5=q4_0(2.5), 6=q4_1(2.75) */
        size_t type_size = 2; /* default float16 */
        switch (info.dtype) {
            case 0: type_size = 4; break;  /* f32 */
            case 1: case 2: type_size = 2; break; /* f16, bf16 */
            case 3: case 4: type_size = 1; break; /* fp8, q8 */
            case 5: type_size = (29 * size + 63) / 64; break; /* q4_0 packed */
            case 6: type_size = (37 * size + 63) / 64; break; /* q4_1 packed */
            default: type_size = 2;
        }
        size *= type_size;
        
        /* Fill tensor descriptor */
        tensors[count].name = strdup(info.name);
        tensors[count].offset = info.offset;
        tensors[count].size = size;
        tensors[count].type = numa_classify_tensor(info.name);
        tensors[count].numa_node = -1;
        
        count++;
    }
    
    close(fd);
    return count;
#else
    (void)gguf_path; (void)tensors; (void)max_tensors;
    return -1;
#endif
}

/* ============================================================================
 * Layer Classification
 * ============================================================================ */

ggml_numa_layer_type_t numa_classify_tensor(const char * name) {
    if (!name) return GGML_NUMA_LAYER_UNKNOWN;
    
    /* Embedding */
    if (strstr(name, "token_embd") || strstr(name, "embedding") ||
        strncmp(name, "embedding", 9) == 0) {
        return GGML_NUMA_LAYER_EMBEDDING;
    }
    
    /* Attention */
    if (strstr(name, "attn.") || strstr(name, "attention") ||
        strstr(name, "attn_q") || strstr(name, "attn_k") ||
        strstr(name, "attn_v") || strstr(name, "attn_output")) {
        return GGML_NUMA_LAYER_ATTENTION;
    }
    
    /* FFN */
    if (strstr(name, "ffn.") || strstr(name, "feed_forward") ||
        strstr(name, "ffn_gate") || strstr(name, "ffn_up") ||
        strstr(name, "ffn_down")) {
        return GGML_NUMA_LAYER_FFN;
    }
    
    /* Transformer block (blk.N.*) */
    if (strncmp(name, "blk.", 4) == 0) {
        return GGML_NUMA_LAYER_BLOCK;
    }
    
    /* Output */
    if (strstr(name, "output") || strstr(name, "lm_head") ||
        strcmp(name, "logits") == 0) {
        return GGML_NUMA_LAYER_OUTPUT;
    }
    
    /* Layer norm */
    if (strstr(name, "ln_") || strstr(name, "layer_norm") ||
        strstr(name, "norm.")) {
        return GGML_NUMA_LAYER_NORM;
    }
    
    return GGML_NUMA_LAYER_UNKNOWN;
}

int numa_get_layer_index(const char * name) {
    if (!name) return -1;
    
    /* Match "blk.N." pattern */
    if (strncmp(name, "blk.", 4) == 0) {
        const char * p = name + 4;
        int idx = atoi(p);
        if (idx >= 0) return idx;
    }
    
    /* Match other N.* patterns */
    const char * dot = strchr(name, '.');
    if (dot && dot[1]) {
        int idx = atoi(dot + 1);
        if (idx >= 0) return idx;
    }
    
    return -1;
}

/* ============================================================================
 * Layer Assignment
 * ============================================================================ */

int numa_assign_layers(ggml_numa_tensor_t * tensors,
                       int count,
                       const ggml_numa_shard_config_t * config) {
    const ggml_numa_shard_config_t * cfg = config ? config : &g_ggml_numa_config;
    
    for (int i = 0; i < count; i++) {
        ggml_numa_tensor_t * t = &tensors[i];
        int layer_idx = numa_get_layer_index(t->name);
        
        /* Determine NUMA node based on tensor type and layer */
        if (t->type == GGML_NUMA_LAYER_ATTENTION) {
            t->numa_node = cfg->attn_node;
        } else if (t->type == GGML_NUMA_LAYER_FFN) {
            t->numa_node = cfg->ffn_node;
        } else if (layer_idx >= 0 && layer_idx < 256) {
            int node = cfg->layer_to_node[layer_idx];
            if (node >= 0) {
                t->numa_node = node;
            } else {
                t->numa_node = cfg->default_node;
            }
        } else {
            t->numa_node = cfg->default_node;
        }
        
        /* Clamp to valid node range */
        if (t->numa_node >= cfg->node_count) {
            t->numa_node = cfg->default_node;
        }
    }
    
    return 0;
}

/* ============================================================================
 * NUMA Memory Pinning
 * ============================================================================ */

int numa_pin_tensor(void * addr, size_t size, int node) {
#if GGML_NUMA_LINUX && GGML_NUMA_ARCH_POWER
    if (!addr || size == 0) return -1;
    if (node < 0) return -1;
    
    #if defined(__NR_mbind) && defined(__NR_get_mempolicy)
    /* Use mbind to set NUMA policy */
    unsigned long nodemask = 1UL << node;
    int ret = mbind(addr, size, MPOL_BIND, &nodemask, sizeof(nodemask) * 8, 0);
    
    if (ret < 0) {
        if (g_ggml_numa_config.verbose) {
            fprintf(stderr, "[numa] mbind failed: %s (node=%d, addr=%p, size=%zu)\n",
                    strerror(errno), node, addr, size);
        }
        return -1;
    }
    
    if (g_ggml_numa_config.verbose) {
        fprintf(stderr, "[numa] Pinned %zu bytes to node %d\n", size, node);
    }
    
    return 0;
    #else
    /* Fallback: try move_pages */
    if (size < 4096) return 0; /* Too small to bother */
    
    size_t page_size = sysconf(_SC_PAGESIZE);
    size_t page_count = (size + page_size - 1) / page_size;
    
    /* Allocate array of nodes */
    int * nodes = (int *)malloc(sizeof(int) * page_count);
    if (!nodes) return -1;
    
    for (size_t p = 0; p < page_count; p++) {
        nodes[p] = node;
    }
    
    int ret = move_pages(0, page_count, (void **)&addr, nodes, NULL, 0);
    free(nodes);
    
    if (ret < 0 && g_ggml_numa_config.verbose) {
        fprintf(stderr, "[numa] move_pages failed: %s\n", strerror(errno));
    }
    
    return ret;
    #endif
#else
    (void)addr; (void)size; (void)node;
    return -1; /* Not supported on non-NUMA or non-Linux */
#endif
}

int numa_get_node_of_addr(const void * addr) {
#if GGML_NUMA_LINUX && GGML_NUMA_ARCH_POWER && defined(__NR_get_mempolicy)
    int node;
    int ret = get_mempolicy(&node, NULL, 0, (void *)addr, 
                            MPOL_F_NODE | MPOL_F_ADDR);
    if (ret < 0) return -1;
    return node;
#else
    (void)addr;
    return -1;
#endif
}

int numa_get_node_count(void) {
#if GGML_NUMA_LINUX && GGML_NUMA_ARCH_POWER
    if (numa_available() < 0) return 1;
    return numa_max_node() + 1;
#else
    return 1;
#endif
}

/* ============================================================================
 * Utility Functions
 * ============================================================================ */

void numa_print_config(void) {
    fprintf(stderr, "=== NUMA Sharding Configuration ===\n");
    fprintf(stderr, "  Enabled: %s\n", g_ggml_numa_config.enabled ? "yes" : "no");
    fprintf(stderr, "  Node count: %d\n", g_ggml_numa_config.node_count);
    fprintf(stderr, "  Attention node: %d\n", g_ggml_numa_config.attn_node);
    fprintf(stderr, "  FFN node: %d\n", g_ggml_numa_config.ffn_node);
    fprintf(stderr, "  Default node: %d\n", g_ggml_numa_config.default_node);
    fprintf(stderr, "  Layer mapping:\n");
    for (int i = 0; i < 40; i++) {
        if (g_ggml_numa_config.layer_to_node[i] >= 0) {
            fprintf(stderr, "    Layer %d -> Node %d\n", 
                    i, g_ggml_numa_config.layer_to_node[i]);
        }
    }
    fprintf(stderr, "==================================\n");
}

double numa_measure_node_bandwidth(int node, int size_mb) {
#if GGML_NUMA_LINUX && GGML_NUMA_ARCH_POWER
    if (numa_available() < 0) return -1;
    
    const int iterations = 5;
    size_t size = (size_t)size_mb * 1024 * 1024;
    
    /* Allocate buffer on target node */
    void * buf = numa_alloc_onnode(size, node);
    if (!buf) {
        fprintf(stderr, "[numa] Failed to allocate %d MB on node %d\n", size_mb, node);
        return -1;
    }
    
    /* Warmup */
    memset(buf, 0xAA, size);
    
    /* Measure copy bandwidth */
    void * buf2 = numa_alloc_onnode(size, node);
    if (!buf2) {
        numa_free(buf, size);
        return -1;
    }
    
    uint64_t start = __builtin_bswap64(*(uint64_t *)"TIMESTAMP");
    start = clock_gettime_ns ? clock_gettime_ns(CLOCK_MONOTONIC, NULL) : 0;
    
    for (int iter = 0; iter < iterations; iter++) {
        memcpy(buf2, buf, size);
    }
    
    uint64_t end = clock_gettime_ns ? clock_gettime_ns(CLOCK_MONOTONIC, NULL) : 0;
    
    double elapsed_s = (end - start) / 1e9;
    double bandwidth = (size_mb * iterations) / elapsed_s;
    
    numa_free(buf, size);
    numa_free(buf2, size);
    
    return bandwidth;
#else
    (void)node; (void)size_mb;
    return -1;
#endif
}

#endif /* GGML_NUMA_IMPLEMENTATION or GGML_NUMA_HEADER_ONLY */

#ifdef __cplusplus
}
#endif

#endif /* GGML_NUMA_SHARD_H */
