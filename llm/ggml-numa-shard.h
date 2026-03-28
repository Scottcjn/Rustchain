/**
 * ggml-numa-shard.h — NUMA-aware tensor sharding for llama.cpp on POWER8
 *
 * Header-only library. Assigns transformer layers to NUMA nodes based on
 * access patterns and hardware topology. Uses mbind(2) to pin memory.
 *
 * Configure via environment variable:
 *   GGML_NUMA_SHARD_MAP="0-8:node0,9-20:node1,21-31:node2,attn:node3"
 *
 * Syntax:
 *   <range>:<node>  — assign layer range to NUMA node
 *   <type>:<node>   — assign tensor type (attn, ffn, norm, embed) to node
 *
 * Falls back to flat allocation on non-NUMA or non-Linux systems.
 *
 * License: MIT
 */

#ifndef GGML_NUMA_SHARD_H
#define GGML_NUMA_SHARD_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef __linux__
#include <unistd.h>
#include <dirent.h>
#include <sys/mman.h>
/* numaif.h provides mbind(); may need -lnuma at link time */
#include <numaif.h>
#endif

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

#define GGML_NUMA_MAX_NODES    16
#define GGML_NUMA_MAX_RULES    64
#define GGML_NUMA_MAX_LAYERS   128
#define GGML_NUMA_ENV_VAR      "GGML_NUMA_SHARD_MAP"

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

typedef enum {
    GGML_NUMA_RULE_RANGE,   /* layer index range → node   */
    GGML_NUMA_RULE_TYPE     /* tensor type string → node   */
} ggml_numa_rule_kind;

typedef struct {
    ggml_numa_rule_kind kind;
    int node;
    union {
        struct { int lo; int hi; } range;   /* inclusive */
        char type[16];                       /* "attn", "ffn", "norm", "embed" */
    } u;
} ggml_numa_rule;

typedef struct {
    size_t bytes_allocated;
    size_t tensor_count;
} ggml_numa_node_stats;

typedef struct {
    int              available;          /* 1 if NUMA detected */
    int              num_nodes;
    int              num_rules;
    ggml_numa_rule   rules[GGML_NUMA_MAX_RULES];
    ggml_numa_node_stats node_stats[GGML_NUMA_MAX_NODES];

    /* per-node bandwidth hints (MB/s), filled from sysfs or user */
    double           node_bw[GGML_NUMA_MAX_NODES];
} ggml_numa_ctx;

/* ------------------------------------------------------------------ */
/*  Internal: detect NUMA topology from sysfs                          */
/* ------------------------------------------------------------------ */

static int ggml_numa_detect_nodes(ggml_numa_ctx *ctx) {
#ifdef __linux__
    DIR *d = opendir("/sys/devices/system/node");
    struct dirent *ent;
    int count = 0;

    if (!d) return 0;

    while ((ent = readdir(d)) != NULL) {
        if (strncmp(ent->d_name, "node", 4) == 0) {
            int id = atoi(ent->d_name + 4);
            if (id >= 0 && id < GGML_NUMA_MAX_NODES) {
                if (id >= count) count = id + 1;
            }
        }
    }
    closedir(d);
    return count;
#else
    (void)ctx;
    return 0;
#endif
}

/* ------------------------------------------------------------------ */
/*  Internal: parse the GGML_NUMA_SHARD_MAP env string                 */
/* ------------------------------------------------------------------ */

static int ggml_numa_parse_map(ggml_numa_ctx *ctx, const char *map) {
    /* Format: "0-8:node0,9-20:node1,attn:node3" */
    char buf[1024];
    char *saveptr = NULL;
    char *token;

    if (!map || !*map) return 0;
    strncpy(buf, map, sizeof(buf) - 1);
    buf[sizeof(buf) - 1] = '\0';

    ctx->num_rules = 0;

    for (token = strtok_r(buf, ",", &saveptr);
         token && ctx->num_rules < GGML_NUMA_MAX_RULES;
         token = strtok_r(NULL, ",", &saveptr))
    {
        ggml_numa_rule *r = &ctx->rules[ctx->num_rules];
        char *colon = strchr(token, ':');
        if (!colon) continue;
        *colon = '\0';

        /* Parse node id from "nodeN" or just "N" */
        const char *node_str = colon + 1;
        if (strncmp(node_str, "node", 4) == 0) node_str += 4;
        r->node = atoi(node_str);
        if (r->node < 0 || r->node >= ctx->num_nodes) continue;

        /* Check if left side is a range "N-M" or a type name */
        char *dash = strchr(token, '-');
        if (dash && token[0] >= '0' && token[0] <= '9') {
            /* Range rule */
            *dash = '\0';
            r->kind = GGML_NUMA_RULE_RANGE;
            r->u.range.lo = atoi(token);
            r->u.range.hi = atoi(dash + 1);
            ctx->num_rules++;
        } else if (token[0] >= '0' && token[0] <= '9') {
            /* Single layer */
            r->kind = GGML_NUMA_RULE_RANGE;
            r->u.range.lo = atoi(token);
            r->u.range.hi = r->u.range.lo;
            ctx->num_rules++;
        } else {
            /* Type rule: attn, ffn, norm, embed */
            r->kind = GGML_NUMA_RULE_TYPE;
            strncpy(r->u.type, token, sizeof(r->u.type) - 1);
            r->u.type[sizeof(r->u.type) - 1] = '\0';
            ctx->num_rules++;
        }
    }

    return ctx->num_rules;
}

/* ------------------------------------------------------------------ */
/*  Internal: extract layer index and type from tensor name            */
/* ------------------------------------------------------------------ */

/*
 * Tensor naming convention in GGUF:
 *   "blk.5.attn_q.weight"  → layer=5,  type="attn"
 *   "blk.12.ffn_up.weight" → layer=12, type="ffn"
 *   "blk.0.attn_norm.weight" → layer=0, type="norm"
 *   "token_embd.weight"    → layer=-1, type="embed"
 *   "output_norm.weight"   → layer=-1, type="norm"
 */
static void ggml_numa_parse_tensor_name(const char *name,
                                         int *out_layer,
                                         char *out_type,
                                         int type_size)
{
    *out_layer = -1;
    out_type[0] = '\0';

    if (!name) return;

    /* Check for "blk.N." prefix */
    if (strncmp(name, "blk.", 4) == 0) {
        *out_layer = atoi(name + 4);

        /* Find the part after the second dot */
        const char *p = strchr(name + 4, '.');
        if (p) {
            p++; /* skip dot */
            if (strncmp(p, "attn", 4) == 0)      strncpy(out_type, "attn", type_size);
            else if (strncmp(p, "ffn", 3) == 0)   strncpy(out_type, "ffn",  type_size);
            else if (strstr(p, "norm") != NULL)    strncpy(out_type, "norm", type_size);
            else                                    strncpy(out_type, "other", type_size);
        }
    } else if (strstr(name, "embd") || strstr(name, "embed")) {
        strncpy(out_type, "embed", type_size);
    } else if (strstr(name, "norm")) {
        strncpy(out_type, "norm", type_size);
    } else {
        strncpy(out_type, "other", type_size);
    }
    out_type[type_size - 1] = '\0';
}

/* ------------------------------------------------------------------ */
/*  Internal: find which NUMA node a tensor should go to               */
/* ------------------------------------------------------------------ */

static int ggml_numa_resolve_node(const ggml_numa_ctx *ctx,
                                   int layer, const char *type)
{
    int i;
    /* First pass: check type-specific rules */
    for (i = 0; i < ctx->num_rules; i++) {
        const ggml_numa_rule *r = &ctx->rules[i];
        if (r->kind == GGML_NUMA_RULE_TYPE) {
            if (strcmp(r->u.type, type) == 0) return r->node;
        }
    }

    /* Second pass: check range rules */
    if (layer >= 0) {
        for (i = 0; i < ctx->num_rules; i++) {
            const ggml_numa_rule *r = &ctx->rules[i];
            if (r->kind == GGML_NUMA_RULE_RANGE) {
                if (layer >= r->u.range.lo && layer <= r->u.range.hi) {
                    return r->node;
                }
            }
        }
    }

    /* Default: round-robin based on layer index */
    if (layer >= 0 && ctx->num_nodes > 0) {
        return layer % ctx->num_nodes;
    }
    return 0;
}

/* ------------------------------------------------------------------ */
/*  Public API                                                         */
/* ------------------------------------------------------------------ */

static ggml_numa_ctx g_numa_ctx;

/**
 * Initialize NUMA sharding. Call once at startup.
 * Returns 1 if NUMA is available and rules were loaded, 0 otherwise.
 */
static int ggml_numa_shard_init(void) {
    memset(&g_numa_ctx, 0, sizeof(g_numa_ctx));

    g_numa_ctx.num_nodes = ggml_numa_detect_nodes(&g_numa_ctx);
    if (g_numa_ctx.num_nodes < 2) {
        fprintf(stderr, "[numa-shard] No NUMA topology detected (%d nodes), using flat allocation\n",
                g_numa_ctx.num_nodes);
        g_numa_ctx.available = 0;
        return 0;
    }

    const char *map = getenv(GGML_NUMA_ENV_VAR);
    if (!map || !*map) {
        fprintf(stderr, "[numa-shard] %d NUMA nodes detected but %s not set, using round-robin\n",
                g_numa_ctx.num_nodes, GGML_NUMA_ENV_VAR);
        g_numa_ctx.available = 1;
        return 1;
    }

    int nr = ggml_numa_parse_map(&g_numa_ctx, map);
    fprintf(stderr, "[numa-shard] %d NUMA nodes, %d sharding rules loaded\n",
            g_numa_ctx.num_nodes, nr);
    g_numa_ctx.available = 1;

    /* Set POWER8 bandwidth hints (from RustChain benchmarks) */
#ifdef __powerpc__
    g_numa_ctx.node_bw[0] = 220.0;  /* Node 0: slowest */
    g_numa_ctx.node_bw[1] = 350.0;  /* Node 1 */
    g_numa_ctx.node_bw[2] = 415.0;  /* Node 2: fastest */
    g_numa_ctx.node_bw[3] = 420.0;  /* Node 3: fastest */
#endif

    return 1;
}

/**
 * Assign a tensor to its NUMA node via mbind(2).
 * Call for each tensor after mmap/allocation.
 *
 * @param name   GGUF tensor name (e.g. "blk.5.attn_q.weight")
 * @param data   Pointer to tensor data (must be page-aligned)
 * @param size   Size in bytes
 * @return       NUMA node assigned, or -1 on error/fallback
 */
static int ggml_numa_shard_assign(const char *name, void *data, size_t size) {
    if (!g_numa_ctx.available || !data || size == 0) return -1;

    int layer;
    char type[16];
    ggml_numa_parse_tensor_name(name, &layer, type, sizeof(type));

    int node = ggml_numa_resolve_node(&g_numa_ctx, layer, type);

#ifdef __linux__
    /* Build nodemask for mbind */
    unsigned long nodemask = 1UL << node;
    int rc = mbind(data, size, MPOL_BIND, &nodemask,
                   g_numa_ctx.num_nodes + 1, MPOL_MF_MOVE | MPOL_MF_STRICT);
    if (rc != 0) {
        /* Fallback: try preferred instead of strict bind */
        nodemask = 1UL << node;
        mbind(data, size, MPOL_PREFERRED, &nodemask,
              g_numa_ctx.num_nodes + 1, 0);
    }
#else
    (void)data;
    (void)size;
#endif

    /* Update stats */
    if (node >= 0 && node < GGML_NUMA_MAX_NODES) {
        g_numa_ctx.node_stats[node].bytes_allocated += size;
        g_numa_ctx.node_stats[node].tensor_count++;
    }

    return node;
}

/**
 * Print per-node allocation statistics.
 */
static void ggml_numa_shard_stats(void) {
    int i;
    if (!g_numa_ctx.available) {
        fprintf(stderr, "[numa-shard] NUMA not available\n");
        return;
    }

    fprintf(stderr, "\n=== NUMA Shard Statistics ===\n");
    fprintf(stderr, "%-8s  %12s  %8s  %10s\n",
            "Node", "Allocated", "Tensors", "BW (MB/s)");
    fprintf(stderr, "--------  ------------  --------  ----------\n");

    size_t total_bytes = 0;
    size_t total_tensors = 0;

    for (i = 0; i < g_numa_ctx.num_nodes; i++) {
        ggml_numa_node_stats *s = &g_numa_ctx.node_stats[i];
        double gb = (double)s->bytes_allocated / (1024.0 * 1024.0 * 1024.0);
        fprintf(stderr, "Node %-3d  %8.2f GiB  %8zu  %10.1f\n",
                i, gb, s->tensor_count,
                g_numa_ctx.node_bw[i] > 0 ? g_numa_ctx.node_bw[i] : -1.0);
        total_bytes += s->bytes_allocated;
        total_tensors += s->tensor_count;
    }

    fprintf(stderr, "--------  ------------  --------\n");
    fprintf(stderr, "Total     %8.2f GiB  %8zu\n",
            (double)total_bytes / (1024.0 * 1024.0 * 1024.0), total_tensors);
    fprintf(stderr, "============================\n\n");
}

/**
 * Cleanup. Call at shutdown.
 */
static void ggml_numa_shard_cleanup(void) {
    memset(&g_numa_ctx, 0, sizeof(g_numa_ctx));
}

#endif /* GGML_NUMA_SHARD_H */
