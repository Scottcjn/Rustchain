CC ?= cc
CFLAGS ?= -O2 -std=c99

all: miner6502-host

miner6502-host: miner6502.c
	$(CC) $(CFLAGS) -o $@ $<

# Placeholder for cc65 pipeline (real Apple II target wiring to be added)
cc65-build:
	@echo "TODO: integrate cc65 target config and linker map for Apple II"

clean:
	rm -f miner6502-host
