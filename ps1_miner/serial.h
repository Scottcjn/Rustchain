/*
 * Serial Communication Driver Header for PS1
 */

#ifndef SERIAL_H
#define SERIAL_H

#include <stdint.h>

/* Initialize serial port at specified baud rate */
int serial_init(int baud);

/* Send a single character */
int serial_putc(char c);

/* Send a string */
int serial_send(const char* str, int len);

/* Send bytes from buffer */
int serial_send_buf(const uint8_t* buf, int len);

/* Receive a single character (blocking) */
int serial_getc(void);

/* Receive a line (blocking, up to max_len) */
int serial_recv(char* buf, int max_len);

/* Receive bytes into buffer (blocking) */
int serial_recv_buf(uint8_t* buf, int max_len);

/* Check if data is available (non-blocking) */
int serial_available(void);

/* Flush transmit buffer */
void serial_flush(void);

/* Get current baud rate */
int serial_get_baud(void);

/* Test serial communication (loopback) */
int serial_test(void);

#endif /* SERIAL_H */
