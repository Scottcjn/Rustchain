/*
 * PIT (Programmable Interval Timer) Operations
 * 
 * Intel 8253/8254 PIT chip
 * Ports: 0x40-0x43
 * Frequency: 1.193182 MHz
 */

#ifndef PIT_H
#define PIT_H

#ifdef __cplusplus
extern "C" {
#endif

/* PIT port addresses */
#define PIT_COUNTER0    0x40
#define PIT_COUNTER1    0x41
#define PIT_COUNTER2    0x42
#define PIT_CONTROL     0x43

/* PIT frequency */
#define PIT_FREQUENCY   1193182UL  /* 1.193182 MHz */

/*
 * Initialize PIT counter 0
 */
void pit_init(void);

/*
 * Read counter 0 value
 */
unsigned int pit_read_counter0(void);

/*
 * Read counter 1 value
 */
unsigned int pit_read_counter1(void);

/*
 * Read counter 2 value (used for speaker)
 */
unsigned int pit_read_counter2(void);

/*
 * Wait for specified milliseconds using PIT
 */
void pit_delay_ms(unsigned int ms);

/*
 * Measure time interval using PIT
 * Returns: Time in microseconds
 */
unsigned long pit_measure_interval(void);

#ifdef __cplusplus
}
#endif

#endif /* PIT_H */
