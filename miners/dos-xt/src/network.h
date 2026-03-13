/*
 * Network Module for DOS
 * 
 * Supports mTCP and WATTCP network stacks
 * Provides HTTP client functionality for node communication
 */

#ifndef NETWORK_H
#define NETWORK_H

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Initialize network stack
 * Returns: 0 on success, -1 on error
 */
int network_init(void);

/*
 * Cleanup network stack
 */
void network_cleanup(void);

/*
 * Check if network is available
 * Returns: 1 if available, 0 if not
 */
int network_is_available(void);

/*
 * HTTP POST request
 *
 * Parameters:
 *   base_url  - Base URL (e.g., "https://50.28.86.131")
 *   path      - Path (e.g., "/attest/challenge")
 *   data      - POST data (JSON string)
 *   response  - Output buffer for response
 *   resp_size - Response buffer size
 *
 * Returns: 0 on success, -1 on error
 */
int http_post(const char *base_url, const char *path, 
              const char *data, char *response, unsigned int resp_size);

/*
 * HTTP GET request
 */
int http_get(const char *base_url, const char *path,
             char *response, unsigned int resp_size);

/*
 * Resolve hostname to IP address
 * Returns: 0 on success, -1 on error
 */
int resolve_hostname(const char *hostname, char *ip_addr, unsigned int ip_size);

/*
 * Check network connectivity
 * Returns: 0 if connected, -1 if not
 */
int check_connectivity(const char *test_url);

#ifdef __cplusplus
}
#endif

#endif /* NETWORK_H */
