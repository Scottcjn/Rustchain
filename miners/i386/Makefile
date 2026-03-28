# Makefile — RustChain i386 Miner
#
# Targets:
#   make linux   — build for Linux/i386 (static)
#   make dos     — build for FreeDOS/DJGPP
#   make all     — build both (if both toolchains present)
#   make clean   — remove binaries
#
# Requirements:
#   Linux target : i386-linux-gnu-gcc (apt: gcc-i686-linux-gnu)
#   DOS target   : DJGPP cross-compiler (i586-pc-msdosdjgpp-gcc)
#                  + Watt-32 networking library

# ------------- toolchains ----------------------------------------- #

CC_LINUX = i386-linux-gnu-gcc
CC_DOS   = i586-pc-msdosdjgpp-gcc

# DJGPP Watt-32: set WATT_ROOT to your Watt-32 install directory.
WATT_ROOT ?= $(HOME)/watt32

# ------------- flags ----------------------------------------------- #

CFLAGS_COMMON = -O2 -march=i386 -std=gnu89 -Wall -Wextra \
                -Wno-unused-function \
                -I.

CFLAGS_LINUX  = $(CFLAGS_COMMON) -static
CFLAGS_DOS    = $(CFLAGS_COMMON) \
                -I$(WATT_ROOT)/inc \
                -D__DJGPP__ \
                -DWATT32

LDFLAGS_DOS   = -L$(WATT_ROOT)/lib -lwatt

# ------------- sources --------------------------------------------- #

SRCS   = miner386.c
HDRS   = sha256.h http_client.h

# ------------- targets --------------------------------------------- #

.PHONY: all linux dos clean

all: linux dos

linux: $(SRCS) $(HDRS)
	$(CC_LINUX) $(CFLAGS_LINUX) -o miner386 $(SRCS)
	@echo "Built: miner386 (Linux/i386 static)"

dos: $(SRCS) $(HDRS)
	$(CC_DOS) $(CFLAGS_DOS) -o miner386.exe $(SRCS) $(LDFLAGS_DOS)
	@echo "Built: miner386.exe (FreeDOS/DJGPP)"

# Quick compile-check using the host compiler (for CI)
check: $(SRCS) $(HDRS)
	$(CC) $(CFLAGS_COMMON) -fsyntax-only $(SRCS)
	@echo "Syntax OK"

clean:
	rm -f miner386 miner386.exe
