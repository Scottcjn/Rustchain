# SPDX-License-Identifier: MIT
# Makefile for Dreamcast SH4 RustChain Miner
# Cross-compile for SH4 (SH7750) using gcc-sh4-linux-gnu

CC      ?= sh4-linux-gnu-gcc
AS      ?= sh4-linux-gnu-as
LD      ?= sh4-linux-gnu-ld
OBJCOPY ?= sh4-linux-gnu-objcopy
STRIP   ?= sh4-linux-gnu-strip
CFLAGS  ?= -O2 -march=sh4 -ml -mb -ffunction-sections -fdata-sections -Wall
ASFLAGS ?= -march=sh4 -ml -mb
LDFLAGS ?= -static -Wl,--gc-sections

TARGET  = dreamcast_miner
SRCS    = miner.c fingerprint.c networking.c
OBJS    = $(SRCS:.c=.o)
ASMSRC  = sha256.S
ASMOBJ  = $(ASMSRC:.S=.o)

INCLUDES = -I.

.PHONY: all clean info

all: info $(TARGET)

info:
	@echo "Building $(TARGET) for SH4 (Dreamcast)"
	@echo "  CC      = $(CC)"
	@echo "  CFLAGS  = $(CFLAGS)"

$(TARGET): $(OBJS) $(ASMOBJ)
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $^ -lm
	$(STRIP) -s $@

%.o: %.c fingerprint.h networking.h
	$(CC) $(CFLAGS) $(INCLUDES) -c -o $@ $<

%.o: %.S
	$(AS) $(ASFLAGS) -o $@ $<

clean:
	rm -f $(OBJS) $(ASMOBJ) $(TARGET)
