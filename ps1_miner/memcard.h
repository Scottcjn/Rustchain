/*
 * Memory Card I/O Header for PS1
 */

#ifndef MEMCARD_H
#define MEMCARD_H

#include <stdint.h>

/* Configuration structure */
typedef struct {
    char wallet_id[64];       /* Wallet identifier */
    char node_url[128];       /* Node URL */
    int baud_rate;            /* Serial baud rate */
    uint32_t epoch_counter;   /* Last epoch number */
    uint32_t last_attestation;/* Last successful attestation epoch */
    uint8_t reserved[32];     /* Reserved for future use */
} memcard_config_t;

/* Create directory on memory card */
int memcard_mkdir(const char* path);

/* Write data to memory card */
int memcard_write(const char* path, const void* data, int size);

/* Read data from memory card */
int memcard_read(const char* path, void* buffer, int max_size);

/* Check if file exists */
int memcard_exists(const char* path);

/* Delete file from memory card */
int memcard_delete(const char* path);

/* List files in directory */
int memcard_list(const char* path, char** files, int max_files);

/* Get free space on memory card */
int memcard_free_space(void);

/* Format memory card (WARNING: erases all data!) */
int memcard_format(void);

/* Save wallet to memory card */
int memcard_save_wallet(const char* wallet_id);

/* Load wallet from memory card */
int memcard_load_wallet(char* buffer, int max_len);

/* Save configuration to memory card */
int memcard_save_config(const memcard_config_t* config);

/* Load configuration from memory card */
int memcard_load_config(memcard_config_t* config);

/* Test memory card I/O */
int memcard_test(void);

#endif /* MEMCARD_H */
