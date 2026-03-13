/*
 * PIT Implementation
 */

#include <dos.h>
#include "pit.h"

/*
 * Initialize PIT counter 0 as square wave generator
 */
void pit_init(void)
{
    /* Configure counter 0: mode 3 (square wave), binary counting */
    outp(PIT_CONTROL, 0x36);
}

/*
 * Read counter 0
 */
unsigned int pit_read_counter0(void)
{
    unsigned int count;
    
    /* Latch counter 0 */
    outp(PIT_CONTROL, 0x00);
    
    /* Read low byte, then high byte */
    count = inp(PIT_COUNTER0);
    count |= (inp(PIT_COUNTER0) << 8);
    
    return count;
}

/*
 * Read counter 1
 */
unsigned int pit_read_counter1(void)
{
    unsigned int count;
    
    /* Latch counter 1 */
    outp(PIT_CONTROL, 0x40);
    
    count = inp(PIT_COUNTER1);
    count |= (inp(PIT_COUNTER1) << 8);
    
    return count;
}

/*
 * Read counter 2
 */
unsigned int pit_read_counter2(void)
{
    unsigned int count;
    
    /* Latch counter 2 */
    outp(PIT_CONTROL, 0x80);
    
    count = inp(PIT_COUNTER2);
    count |= (inp(PIT_COUNTER2) << 8);
    
    return count;
}

/*
 * Delay using PIT
 * Note: This is approximate; for accurate timing use BIOS INT 0x15
 */
void pit_delay_ms(unsigned int ms)
{
    /* Use BIOS delay for simplicity */
    /* INT 0x15, AH=0x86 - Wait (microseconds in CX:DX) */
    /* For now, use simple loop */
    
    unsigned long i;
    unsigned long loops = (unsigned long)ms * 10000UL;
    
    for (i = 0; i < loops; i++) {
        __asm {
            nop
        }
    }
}

/*
 * Measure time interval
 * This is a placeholder - would need two PIT readings
 */
unsigned long pit_measure_interval(void)
{
    unsigned int start = pit_read_counter0();
    /* Do something */
    unsigned int end = pit_read_counter0();
    
    /* Calculate difference (handle wraparound) */
    unsigned int diff;
    if (end > start) {
        diff = (65536 - start) + end;
    } else {
        diff = start - end;
    }
    
    /* Convert to microseconds */
    /* Each PIT tick = 1/1.193182 MHz = 0.838 microseconds */
    return (unsigned long)diff * 838UL / 1000;
}
