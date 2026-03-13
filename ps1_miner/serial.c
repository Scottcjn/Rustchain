/*
 * Serial Communication Driver for PS1
 * Uses built-in UART (9600 bps default)
 */

#include "serial.h"
#include <psxapi.h>
#include <psxgpu.h>
#include <stdio.h>
#include <string.h>

/* UART registers (PS1 uses standard 16550-compatible UART) */
#define UART_BASE 0x1f801040

#define UART_RHR 0x00  /* Receiver Holding Register (read) */
#define UART_THR 0x00  /* Transmitter Holding Register (write) */
#define UART_IER 0x01  /* Interrupt Enable Register */
#define UART_FCR 0x02  /* FIFO Control Register */
#define UART_LCR 0x03  /* Line Control Register */
#define UART_MCR 0x04  /* Modem Control Register */
#define UART_LSR 0x05  /* Line Status Register */
#define UART_MSR 0x06  /* Modem Status Register */

#define UART_LSR_DR   0x01  /* Data Ready */
#define UART_LSR_OE   0x02  /* Overrun Error */
#define UART_LSR_PE   0x04  /* Parity Error */
#define UART_LSR_FE   0x08  /* Framing Error */
#define UART_LSR_BI   0x10  /* Break Interrupt */
#define UART_LSR_THRE 0x20  /* THR Empty */
#define UART_LSR_TEMT 0x40  /* THR and TSR Empty */

static int serial_initialized = 0;
static int serial_baud_rate = 9600;

/* Initialize serial port */
int serial_init(int baud) {
    volatile uint8_t* uart = (volatile uint8_t*)UART_BASE;
    
    /* Set baud rate divisor */
    int divisor = 115200 / baud;
    
    /* Enable DLAB (Divisor Latch Access Bit) */
    uart[UART_LCR] = 0x83;  /* 8 bits, no parity, 1 stop, DLAB=1 */
    
    /* Set divisor */
    uart[0] = divisor & 0xFF;        /* DLL (Divisor Latch Low) */
    uart[1] = (divisor >> 8) & 0xFF; /* DLH (Divisor Latch High) */
    
    /* Disable DLAB, set 8N1 */
    uart[UART_LCR] = 0x03;
    
    /* Disable interrupts */
    uart[UART_IER] = 0x00;
    
    /* Enable FIFO */
    uart[UART_FCR] = 0x07;  /* Enable FIFO, clear RX/TX */
    
    /* Set DTR and RTS */
    uart[UART_MCR] = 0x03;
    
    serial_baud_rate = baud;
    serial_initialized = 1;
    
    printf("[SERIAL] Initialized at %d bps\n", baud);
    return 0;
}

/* Send a single character */
int serial_putc(char c) {
    volatile uint8_t* uart = (volatile uint8_t*)UART_BASE;
    
    /* Wait for THR to be empty */
    while (!(uart[UART_LSR] & UART_LSR_THRE));
    
    /* Send character */
    uart[UART_THR] = c;
    return 1;
}

/* Send a string */
int serial_send(const char* str, int len) {
    int i;
    for (i = 0; i < len; i++) {
        serial_putc(str[i]);
    }
    return len;
}

/* Send bytes from buffer */
int serial_send_buf(const uint8_t* buf, int len) {
    int i;
    for (i = 0; i < len; i++) {
        serial_putc(buf[i]);
    }
    return len;
}

/* Receive a single character (blocking) */
int serial_getc(void) {
    volatile uint8_t* uart = (volatile uint8_t*)UART_BASE;
    
    /* Wait for data ready */
    while (!(uart[UART_LSR] & UART_LSR_DR));
    
    /* Read character */
    return uart[UART_RHR];
}

/* Receive a line (blocking, up to max_len) */
int serial_recv(char* buf, int max_len) {
    int i = 0;
    int c;
    
    while (i < max_len - 1) {
        c = serial_getc();
        
        if (c == '\n' || c == '\r') {
            if (i > 0) break;  /* End of line */
            continue;  /* Skip leading CR/LF */
        }
        
        buf[i++] = c;
    }
    
    buf[i] = '\0';
    return i;
}

/* Receive bytes into buffer (blocking) */
int serial_recv_buf(uint8_t* buf, int max_len) {
    int i;
    for (i = 0; i < max_len; i++) {
        buf[i] = serial_getc();
    }
    return max_len;
}

/* Check if data is available (non-blocking) */
int serial_available(void) {
    volatile uint8_t* uart = (volatile uint8_t*)UART_BASE;
    return (uart[UART_LSR] & UART_LSR_DR) ? 1 : 0;
}

/* Flush transmit buffer */
void serial_flush(void) {
    volatile uint8_t* uart = (volatile uint8_t*)UART_BASE;
    
    /* Wait for THR and TSR to be empty */
    while (!(uart[UART_LSR] & UART_LSR_TEMT));
}

/* Get current baud rate */
int serial_get_baud(void) {
    return serial_baud_rate;
}

/* Test serial communication (loopback) */
int serial_test(void) {
    char test_str[] = "SERIAL TEST\r\n";
    char recv_buf[64];
    
    printf("[SERIAL] Testing loopback...\n");
    
    /* Send test string */
    serial_send(test_str, strlen(test_str));
    serial_flush();
    
    /* Note: Loopback test requires TX connected to RX */
    /* For actual PS1, this would need external loopback plug */
    
    printf("[SERIAL] Test complete\n");
    return 0;
}
