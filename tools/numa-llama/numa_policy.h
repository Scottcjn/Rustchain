/*
 * numa_policy.h - NUMA Policy Helpers
 * 
 * Environment variable parsing for GGML_NUMA_SHARD_MAP and
 * fallback defaults optimized for POWER8 topology.
 * 
 * Author: NUMA-LLAMA Team
 * License: MIT
 */

#ifndef NUMA_POLICY_H
#define NUMA_POLICY_H

#include <stdint.h>
#include <stdbool.h>

/* ============================================================================
 * Defaults for IBM POWER8 S824
 * 
 * Memory bandwidth characteristics (measured):
 *   Node 0/1: ~215-225 MB/s (slower, opposite memory controller)
 *   Node 2/3: ~400-425 MB/s (faster, adjacent memory controller)
 * 
 * Optimal placement:
 *   - Embeddings (high bandwidth, sequential): Node 0
 *   - Early transformer layers: Node 1
 *   - FFN layers (compute-heavy): Node 2
 *   - Attention layers (high BW, random access): Node 3
 * ============================================================================ */

/* POWER8 default layer-to-node mapping */
#define NUMA_POLICY_POWER8_DEFAULT \
    "0-7:node0,8-15:node1,16-23:node2,24-31:node3,attn:node3,ffn:node2"

/* Alternative: Focus attention on fastest nodes */
#define NUMA_POLICY_POWER8_ATTN_FOCUSED \
    "0-15:node0,16-31:node1,attn:node3,ffn:node2"

/* ============================================================================
 * Layer Type Tags
 * ============================================================================ */

typedef enum {
    NUMA_TAG_UNSPECIFIED = 0,
    NUMA_TAG_BLK,         /* Transformer block layers (blk.N.*) */
    NUMA_TAG_ATTN,         /* Attention layers (attn.*) */
    NUMA_TAG_FFN,          /* Feed-forward network (ffn.*, feed_forward.*) */
    NUMA_TAG_EMB,          /* Embeddings (token_embd.*, embedding.*) */
    NUMA_TAG_NORM,         /* Layer normalization (ln_*, norm.*) */
    NUMA_TAG_OUTPUT,       /* Output layer (output.*, lm_head.*) */
} numa_policy_tag_t;

/* ============================================================================
 * Policy Entry
 * ============================================================================ */

typedef struct {
    numa_policy_tag_t tag;
    int               node;
    bool              is_range;
    int               range_start;
    int               range_end;
} numa_policy_entry_t;

/* Maximum policy entries */
#define NUMA_MAX_POLICY_ENTRIES 32

/* ============================================================================
 * Policy Configuration
 * ============================================================================ */

typedef struct {
    numa_policy_entry_t entries[NUMA_MAX_POLICY_ENTRIES];
    int                  num_entries;
    int                  default_node;
    bool                 parse_error;
    char                 error_msg[256];
} numa_policy_t;

/* ============================================================================
 * API
 * ============================================================================ */

/*
 * Parse GGML_NUMA_SHARD_MAP environment variable.
 * 
 * Format: "range:node,type:node,..."
 *   - "0-7:node0"      → layers 0-7 to node 0
 *   - "8-15:node1"     → layers 8-15 to node 1
 *   - "attn:node3"     → attention tensors to node 3
 *   - "ffn:node2"      → FFN tensors to node 2
 *   - "blk:node1"      → transformer blocks to node 1
 * 
 * Parameters:
 *   - policy: Output policy structure
 *   - env_value: String from getenv("GGML_NUMA_SHARD_MAP")
 * 
 * Returns: 0 on success, -1 on error.
 */
int numa_policy_parse(numa_policy_t * policy, const char * env_value);

/*
 * Get the NUMA node for a given layer index and tensor type.
 * 
 * Parameters:
 *   - policy: Parsed policy
 *   - layer_index: Transformer layer index (-1 for non-layered tensors)
 *   - tag: Tensor type tag
 * 
 * Returns: NUMA node number.
 */
int numa_policy_get_node(const numa_policy_t * policy, 
                         int layer_index,
                         numa_policy_tag_t tag);

/*
 * Initialize policy with POWER8 defaults.
 * 
 * Parameters:
 *   - policy: Output policy structure
 *   - node_count: Number of NUMA nodes (typically 4 on POWER8 S824)
 */
void numa_policy_init_power8(numa_policy_t * policy, int node_count);

/*
 * Print policy for debugging.
 */
void numa_policy_print(const numa_policy_t * policy);

/*
 * Get tag from tensor name prefix.
 * 
 * Returns: Tag type or NUMA_TAG_UNSPECIFIED.
 */
numa_policy_tag_t numa_policy_tag_from_name(const char * name);

/* ============================================================================
 * Implementation
 * ============================================================================ */

#ifdef NUMA_POLICY_IMPLEMENTATION

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>

int numa_policy_parse(numa_policy_t * policy, const char * env_value) {
    if (!policy || !env_value) return -1;
    
    memset(policy, 0, sizeof(*policy));
    policy->default_node = 0;
    policy->parse_error = false;
    
    /* Make a working copy */
    char * buf = strdup(env_value);
    if (!buf) return -1;
    
    char * saveptr;
    char * entry = strtok_r(buf, ",", &saveptr);
    
    while (entry && policy->num_entries < NUMA_MAX_POLICY_ENTRIES) {
        /* Skip whitespace */
        while (*entry && isspace(*entry)) entry++;
        
        /* Find colon separator */
        char * colon = strchr(entry, ':');
        if (!colon) {
            snprintf(policy->error_msg, sizeof(policy->error_msg),
                    "Invalid entry '%s' - missing colon", entry);
            policy->parse_error = true;
            break;
        }
        
        *colon = '\0';
        const char * key = entry;
        const char * value = colon + 1;
        
        numa_policy_entry_t e = {0};
        
        /* Parse key (range or type) */
        if (strcmp(key, "attn") == 0) {
            e.tag = NUMA_TAG_ATTN;
            e.is_range = false;
        } else if (strcmp(key, "ffn") == 0) {
            e.tag = NUMA_TAG_FFN;
            e.is_range = false;
        } else if (strcmp(key, "blk") == 0) {
            e.tag = NUMA_TAG_BLK;
            e.is_range = false;
        } else if (strcmp(key, "emb") == 0 || strcmp(key, "embedding") == 0) {
            e.tag = NUMA_TAG_EMB;
            e.is_range = false;
        } else if (strcmp(key, "norm") == 0) {
            e.tag = NUMA_TAG_NORM;
            e.is_range = false;
        } else if (strcmp(key, "output") == 0) {
            e.tag = NUMA_TAG_OUTPUT;
            e.is_range = false;
        } else {
            /* Try as range: "0-7" or "0" */
            char * dash = strchr(key, '-');
            if (dash) {
                e.tag = NUMA_TAG_BLK;
                e.is_range = true;
                e.range_start = atoi(key);
                e.range_end = atoi(dash + 1);
            } else {
                e.tag = NUMA_TAG_BLK;
                e.is_range = true;
                e.range_start = atoi(key);
                e.range_end = e.range_start;
            }
        }
        
        /* Parse node: "nodeN" or just "N" */
        if (strncmp(value, "node", 4) == 0) {
            e.node = atoi(value + 4);
        } else {
            e.node = atoi(value);
        }
        
        policy->entries[policy->num_entries++] = e;
        
        entry = strtok_r(NULL, ",", &saveptr);
    }
    
    free(buf);
    return policy->parse_error ? -1 : 0;
}

int numa_policy_get_node(const numa_policy_t * policy, 
                         int layer_index,
                         numa_policy_tag_t tag) {
    if (!policy) return 0;
    
    /* Search entries in order */
    for (int i = 0; i < policy->num_entries; i++) {
        const numa_policy_entry_t * e = &policy->entries[i];
        
        if (e->is_range) {
            if (layer_index >= e->range_start && layer_index <= e->range_end) {
                return e->node;
            }
        } else {
            if (e->tag == tag) {
                return e->node;
            }
        }
    }
    
    return policy->default_node;
}

void numa_policy_init_power8(numa_policy_t * policy, int node_count) {
    if (!policy) return;
    
    memset(policy, 0, sizeof(*policy));
    policy->default_node = 0;
    
    /* POWER8 S824 with 4 nodes:
     * Node 0: slowest (215-225 MB/s) - embeddings, early layers
     * Node 1: medium (215-225 MB/s) - mid layers
     * Node 2: fast (400-425 MB/s) - FFN
     * Node 3: fastest (400-425 MB/s) - attention
     */
    
    numa_policy_entry_t entries[] = {
        {NUMA_TAG_BLK,  0, true,  0,  7},   /* Early layers → Node 0 */
        {NUMA_TAG_BLK,  1, true,  8, 15},   /* Mid layers → Node 1 */
        {NUMA_TAG_BLK,  2, true, 16, 23},   /* Later layers → Node 2 */
        {NUMA_TAG_BLK,  3, true, 24, 31},   /* Late layers → Node 3 */
        {NUMA_TAG_ATTN, 3, false, 0,  0},   /* Attention → Node 3 */
        {NUMA_TAG_FFN,  2, false, 0,  0},   /* FFN → Node 2 */
        {NUMA_TAG_EMB,  0, false, 0,  0},   /* Embeddings → Node 0 */
        {NUMA_TAG_NORM, 1, false, 0,  0},   /* Norm → Node 1 */
    };
    
    int num_entries = sizeof(entries) / sizeof(entries[0]);
    for (int i = 0; i < num_entries && policy->num_entries < NUMA_MAX_POLICY_ENTRIES; i++) {
        policy->entries[policy->num_entries++] = entries[i];
    }
    
    (void)node_count; /* node_count not used in POWER8 defaults */
}

void numa_policy_print(const numa_policy_t * policy) {
    if (!policy) return;
    
    printf("NUMA Policy Configuration:\n");
    printf("  Default node: %d\n", policy->default_node);
    printf("  Entries (%d):\n", policy->num_entries);
    
    for (int i = 0; i < policy->num_entries; i++) {
        const numa_policy_entry_t * e = &policy->entries[i];
        const char * tag_name = "???";
        
        switch (e->tag) {
            case NUMA_TAG_ATTN:   tag_name = "attn"; break;
            case NUMA_TAG_FFN:    tag_name = "ffn"; break;
            case NUMA_TAG_BLK:    tag_name = "blk"; break;
            case NUMA_TAG_EMB:    tag_name = "emb"; break;
            case NUMA_TAG_NORM:   tag_name = "norm"; break;
            case NUMA_TAG_OUTPUT: tag_name = "output"; break;
            default:              tag_name = "???"; break;
        }
        
        if (e->is_range) {
            printf("    %s[%d-%d] → node%d\n", 
                   tag_name, e->range_start, e->range_end, e->node);
        } else {
            printf("    %s → node%d\n", tag_name, e->node);
        }
    }
    
    if (policy->parse_error) {
        printf("  PARSE ERROR: %s\n", policy->error_msg);
    }
}

numa_policy_tag_t numa_policy_tag_from_name(const char * name) {
    if (!name) return NUMA_TAG_UNSPECIFIED;
    
    if (strstr(name, "attn.") || strstr(name, "attention")) {
        return NUMA_TAG_ATTN;
    }
    if (strstr(name, "ffn.") || strstr(name, "feed_forward")) {
        return NUMA_TAG_FFN;
    }
    if (strncmp(name, "blk.", 4) == 0) {
        return NUMA_TAG_BLK;
    }
    if (strstr(name, "token_embd") || strstr(name, "embedding")) {
        return NUMA_TAG_EMB;
    }
    if (strstr(name, "ln_") || strstr(name, "norm.")) {
        return NUMA_TAG_NORM;
    }
    if (strstr(name, "output") || strstr(name, "lm_head")) {
        return NUMA_TAG_OUTPUT;
    }
    
    return NUMA_TAG_UNSPECIFIED;
}

#endif /* NUMA_POLICY_IMPLEMENTATION */

#endif /* NUMA_POLICY_H */
