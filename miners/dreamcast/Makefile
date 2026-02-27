CC ?= cc
CFLAGS ?= -O2 -std=c99

all: miner-sh4-host

miner-sh4-host: miner_sh4.c
	$(CC) $(CFLAGS) -o $@ $<

# Placeholder for Dreamcast cross-compile target (sh-elf-gcc / KOS env)
dreamcast-build:
	@echo "TODO: wire Dreamcast SH4 cross toolchain target"

clean:
	rm -f miner-sh4-host
