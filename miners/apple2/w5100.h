/*
 * w5100.h — WIZnet W5100 / Uthernet II register definitions
 *
 * The Uthernet II is an Apple II peripheral card that uses the WIZnet W5100
 * chip.  It provides hardware TCP/IP, relieving the 6502 of all protocol
 * processing.  The card lives in one of slots 1–7 and its registers are
 * memory-mapped at $C0x0–$C0x3 where x = slot number.
 *
 * Reference: WIZnet W5100 Datasheet Rev 1.2.1
 *            Uthernet II Technical Reference (A2Heaven)
 *
 * CC65 / Apple IIe target.  No floats, no 64-bit types.
 * All types are from <stdint.h> (provided by CC65 runtime).
 */

#ifndef W5100_H
#define W5100_H

#include <stdint.h>

/* ------------------------------------------------------------------ */
/* Slot-based I/O address                                               */
/* ------------------------------------------------------------------ */
/*
 * Apple II slot I/O space: $C080 + (slot * $10)
 * For Uthernet II, four consecutive bytes are the indirect access window.
 *
 * Slot 3 default:  base = $C0B0
 *   $C0B0 = MR    (mode register / address high byte)
 *   $C0B1 = AR    (address low byte — note: W5100 uses 16-bit indirect)
 *   $C0B2 = DR    (data register — read/write through current address)
 *   $C0B3 = (reserved / IDR on some revisions)
 *
 * The Uthernet II uses the W5100's "indirect bus interface" so all
 * register access goes through a 2-byte address latch + 1 data byte.
 */

/* Detect slot: scan $C0x0 for W5100 mode register signature (0x00 on reset) */
extern uint8_t w5100_slot;          /* 1-7, set by w5100_detect() */

#define W5100_IO_BASE(slot)  ((volatile uint8_t *)(0xC080u + ((slot) << 4)))

/* Indirect-mode register offsets within the 4-byte slot window */
#define W5100_REG_MR   0   /* Mode / indirect address high byte */
#define W5100_REG_AR   1   /* Indirect address low byte          */
#define W5100_REG_DR   2   /* Indirect data register             */

/* ------------------------------------------------------------------ */
/* W5100 Common Registers (indirect addresses)                          */
/* ------------------------------------------------------------------ */
#define W5100_MR       0x0000u   /* Mode Register                     */
#define W5100_GAR      0x0001u   /* Gateway Address (4 bytes)         */
#define W5100_SUBR     0x0005u   /* Subnet Mask (4 bytes)             */
#define W5100_SHAR     0x0009u   /* Source MAC (6 bytes)              */
#define W5100_SIPR     0x000Fu   /* Source IP (4 bytes)               */
#define W5100_RMSR     0x001Au   /* RX Memory Size Register           */
#define W5100_TMSR     0x001Bu   /* TX Memory Size Register           */

/* W5100 MR bits */
#define W5100_MR_RST   0x80u    /* Software reset                     */
#define W5100_MR_IND   0x01u    /* Indirect bus interface enable      */

/* ------------------------------------------------------------------ */
/* W5100 Socket Registers (socket 0 only — we use one socket)          */
/* ------------------------------------------------------------------ */
#define W5100_S0_BASE  0x0400u

#define W5100_S0_MR    (W5100_S0_BASE + 0x00u)  /* Socket Mode         */
#define W5100_S0_CR    (W5100_S0_BASE + 0x01u)  /* Socket Command      */
#define W5100_S0_IR    (W5100_S0_BASE + 0x02u)  /* Socket Interrupt    */
#define W5100_S0_SR    (W5100_S0_BASE + 0x03u)  /* Socket Status       */
#define W5100_S0_PORT  (W5100_S0_BASE + 0x04u)  /* Source Port (2B)    */
#define W5100_S0_DHAR  (W5100_S0_BASE + 0x06u)  /* Dest MAC (6B)       */
#define W5100_S0_DIPR  (W5100_S0_BASE + 0x0Cu)  /* Dest IP (4B)        */
#define W5100_S0_DPORT (W5100_S0_BASE + 0x10u)  /* Dest Port (2B)      */
#define W5100_S0_TX_FSR (W5100_S0_BASE + 0x20u) /* TX Free Size (2B)   */
#define W5100_S0_TX_RD  (W5100_S0_BASE + 0x22u) /* TX Read Ptr (2B)    */
#define W5100_S0_TX_WR  (W5100_S0_BASE + 0x24u) /* TX Write Ptr (2B)   */
#define W5100_S0_RX_RSR (W5100_S0_BASE + 0x26u) /* RX Received Size (2B) */
#define W5100_S0_RX_RD  (W5100_S0_BASE + 0x28u) /* RX Read Ptr (2B)    */

/* Socket Mode bits */
#define W5100_SM_TCP   0x01u   /* TCP mode                            */
#define W5100_SM_ND    0x20u   /* No Delayed ACK                      */

/* Socket Commands */
#define W5100_CMD_OPEN    0x01u
#define W5100_CMD_CONNECT 0x04u
#define W5100_CMD_DISCON  0x08u
#define W5100_CMD_CLOSE   0x10u
#define W5100_CMD_SEND    0x20u
#define W5100_CMD_RECV    0x40u

/* Socket Status values */
#define W5100_SOCK_CLOSED      0x00u
#define W5100_SOCK_INIT        0x13u
#define W5100_SOCK_LISTEN      0x14u
#define W5100_SOCK_ESTABLISHED 0x17u
#define W5100_SOCK_CLOSE_WAIT  0x1Cu
#define W5100_SOCK_FIN_WAIT    0x18u

/* W5100 TX/RX buffer base addresses (socket 0) */
#define W5100_TX_BASE  0x4000u
#define W5100_RX_BASE  0x6000u
#define W5100_TX_MASK  0x07FFu   /* 2KB TX buffer mask (socket 0)    */
#define W5100_RX_MASK  0x07FFu   /* 2KB RX buffer mask (socket 0)    */

/* ------------------------------------------------------------------ */
/* Low-level indirect register access                                   */
/* ------------------------------------------------------------------ */

/* Write a single byte to W5100 register at 16-bit addr */
void w5100_write(uint16_t addr, uint8_t data);

/* Read a single byte from W5100 register at 16-bit addr */
uint8_t w5100_read(uint16_t addr);

/* Write 16-bit big-endian value */
void w5100_write16(uint16_t addr, uint16_t val);

/* Read 16-bit big-endian value */
uint16_t w5100_read16(uint16_t addr);

/* ------------------------------------------------------------------ */
/* High-level socket API                                                */
/* ------------------------------------------------------------------ */

/* Scan slots 1-7 for a W5100; sets w5100_slot. Returns 1 if found. */
uint8_t w5100_detect(void);

/* Initialise W5100: reset, set MAC/IP/GW/subnet from config. */
void w5100_init(const uint8_t *mac,    /* 6 bytes */
                const uint8_t *myip,   /* 4 bytes */
                const uint8_t *gw,     /* 4 bytes */
                const uint8_t *subnet  /* 4 bytes */);

/* Open a TCP socket and connect to dest_ip:dest_port.
 * Returns 1 on success, 0 on failure. */
uint8_t w5100_connect(const uint8_t *dest_ip, uint16_t dest_port);

/* Send len bytes from buf.  Returns bytes sent, or 0 on error. */
uint16_t w5100_send(const uint8_t *buf, uint16_t len);

/* Receive up to max_len bytes into buf.
 * Returns bytes received (0 = nothing yet, 0xFFFF = error). */
uint16_t w5100_recv(uint8_t *buf, uint16_t max_len);

/* Close the socket gracefully. */
void w5100_close(void);

/* Return 1 if socket is still connected. */
uint8_t w5100_connected(void);

#endif /* W5100_H */
