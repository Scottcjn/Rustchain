/*
 * Memory Card I/O Driver for PS1
 * Handles wallet and config storage
 */

#include "memcard.h"
#include <psxapi.h>
#include <stdio.h>
#include <string.h>

/* Memory card constants */
#define MC_BLOCK_SIZE 128
#define MC_TOTAL_BLOCKS 15  /* 128 KB card = 15 usable blocks */

/* Directory entry structure */
typedef struct {
    char name[32];
    int block;
    int size;
} mc_entry_t;

/* Open memory card directory */
static int mc_open_dir(const char* path) {
    /* Use PS1 system calls */
    return open(path, O_RDONLY);
}

/* Create directory on memory card */
int memcard_mkdir(const char* path) {
    int ret = mkdir(path);
    if (ret >= 0) {
        printf("[MEMCARD] Created directory: %s\n", path);
    }
    return ret;
}

/* Write data to memory card */
int memcard_write(const char* path, const void* data, int size) {
    int fd;
    int written;
    
    /* Open file for writing */
    fd = open(path, O_WRONLY | O_CREAT | O_TRUNC);
    if (fd < 0) {
        printf("[MEMCARD] Failed to open %s for writing\n", path);
        return -1;
    }
    
    /* Write data */
    written = write(fd, data, size);
    close(fd);
    
    if (written == size) {
        printf("[MEMCARD] Wrote %d bytes to %s\n", written, path);
        return 0;
    } else {
        printf("[MEMCARD] Write error: wrote %d of %d bytes\n", written, size);
        return -1;
    }
}

/* Read data from memory card */
int memcard_read(const char* path, void* buffer, int max_size) {
    int fd;
    int bytes_read;
    
    /* Open file for reading */
    fd = open(path, O_RDONLY);
    if (fd < 0) {
        printf("[MEMCARD] Failed to open %s for reading\n", path);
        return -1;
    }
    
    /* Read data */
    bytes_read = read(fd, buffer, max_size);
    close(fd);
    
    if (bytes_read > 0) {
        printf("[MEMCARD] Read %d bytes from %s\n", bytes_read, path);
        return bytes_read;
    } else {
        printf("[MEMCARD] Read error or empty file\n");
        return -1;
    }
}

/* Check if file exists */
int memcard_exists(const char* path) {
    int fd = open(path, O_RDONLY);
    if (fd >= 0) {
        close(fd);
        return 1;
    }
    return 0;
}

/* Delete file from memory card */
int memcard_delete(const char* path) {
    int ret = erase(path);
    if (ret >= 0) {
        printf("[MEMCARD] Deleted: %s\n", path);
    }
    return ret;
}

/* List files in directory */
int memcard_list(const char* path, char** files, int max_files) {
    /* Simplified - real implementation would use first() and next() */
    printf("[MEMCARD] Listing %s (not implemented)\n", path);
    return 0;
}

/* Get free space on memory card */
int memcard_free_space(void) {
    /* Return number of free blocks */
    /* Simplified - real implementation would query card */
    return MC_TOTAL_BLOCKS;
}

/* Format memory card (WARNING: erases all data!) */
int memcard_format(void) {
    printf("[MEMCARD] Format not supported via API\n");
    return -1;
}

/* Save wallet to memory card */
int memcard_save_wallet(const char* wallet_id) {
    char path[64];
    
    /* Create directory */
    memcard_mkdir("bu00:RUSTCHN");
    
    /* Build path */
    snprintf(path, sizeof(path), "bu00:RUSTCHN/WALLET.DAT");
    
    /* Write wallet */
    return memcard_write(path, wallet_id, strlen(wallet_id));
}

/* Load wallet from memory card */
int memcard_load_wallet(char* buffer, int max_len) {
    char path[64];
    int len;
    
    /* Build path */
    snprintf(path, sizeof(path), "bu00:RUSTCHN/WALLET.DAT");
    
    /* Check if exists */
    if (!memcard_exists(path)) {
        printf("[MEMCARD] Wallet file not found\n");
        return -1;
    }
    
    /* Read wallet */
    len = memcard_read(path, buffer, max_len - 1);
    if (len > 0) {
        buffer[len] = '\0';
        return len;
    }
    
    return -1;
}

/* Save configuration to memory card */
int memcard_save_config(const memcard_config_t* config) {
    char path[64];
    
    /* Create directory */
    memcard_mkdir("bu00:RUSTCHN");
    
    /* Build path */
    snprintf(path, sizeof(path), "bu00:RUSTCHN/CONFIG.DAT");
    
    /* Write config */
    return memcard_write(path, config, sizeof(memcard_config_t));
}

/* Load configuration from memory card */
int memcard_load_config(memcard_config_t* config) {
    char path[64];
    int len;
    
    /* Build path */
    snprintf(path, sizeof(path), "bu00:RUSTCHN/CONFIG.DAT");
    
    /* Check if exists */
    if (!memcard_exists(path)) {
        printf("[MEMCARD] Config file not found\n");
        return -1;
    }
    
    /* Read config */
    len = memcard_read(path, config, sizeof(memcard_config_t));
    if (len == sizeof(memcard_config_t)) {
        return 0;
    }
    
    return -1;
}

/* Test memory card I/O */
int memcard_test(void) {
    char test_data[] = "RustChain PS1 Miner Test";
    char read_data[64];
    char path[] = "bu00:RUSTCHN/TEST.DAT";
    
    printf("[MEMCARD] Running I/O test...\n");
    
    /* Create directory */
    memcard_mkdir("bu00:RUSTCHN");
    
    /* Write test data */
    if (memcard_write(path, test_data, strlen(test_data)) < 0) {
        printf("[MEMCARD] Write test FAILED\n");
        return -1;
    }
    
    /* Read test data */
    int len = memcard_read(path, read_data, sizeof(read_data));
    if (len < 0) {
        printf("[MEMCARD] Read test FAILED\n");
        return -1;
    }
    
    /* Verify */
    read_data[len] = '\0';
    if (strcmp(read_data, test_data) != 0) {
        printf("[MEMCARD] Verify FAILED: '%s' != '%s'\n", read_data, test_data);
        return -1;
    }
    
    /* Clean up */
    memcard_delete(path);
    
    printf("[MEMCARD] I/O test PASSED\n");
    return 0;
}
