# N64 Mining ROM Makefile
# Requires: libdragon toolchain (https://github.com/DragonMinded/libdragon)
#
# Build:   make
# Clean:   make clean
# Test:    make test

ROM_NAME = n64_miner

# Libdragon paths (adjust for your installation)
ROOTDIR  ?= $(N64_INST)
GCCN64PREFIX = $(ROOTDIR)/bin/mips64-elf-
CC       = $(GCCN64PREFIX)gcc
AS       = $(GCCN64PREFIX)as
LD       = $(GCCN64PREFIX)ld
OBJCOPY  = $(GCCN64PREFIX)objcopy

N64TOOL  = $(ROOTDIR)/bin/n64tool
CHKSUM64 = $(ROOTDIR)/bin/chksum64

CFLAGS   = -std=gnu99 -march=vr4300 -mtune=vr4300 -O2 -Wall -Wextra \
           -I$(ROOTDIR)/mips64-elf/include -DN64_LIBDRAGON
LDFLAGS  = -L$(ROOTDIR)/mips64-elf/lib -ldragon -lc -lm -ldragonsys \
           -T$(ROOTDIR)/mips64-elf/lib/n64.ld
ASFLAGS  = -mtune=vr4300 -march=vr4300

SOURCES  = n64_miner.c fingerprint.c
OBJECTS  = $(SOURCES:.c=.o)

# ROM header
HEADER   = $(ROOTDIR)/mips64-elf/lib/header
ROM_SIZE = 1048576

.PHONY: all clean test

all: $(ROM_NAME).z64

$(ROM_NAME).z64: $(ROM_NAME).bin
	@echo "  [N64TOOL] $@"
	$(N64TOOL) -l $(ROM_SIZE) -h $(HEADER) -o $@ -t "RustChain N64 Miner" $<
	$(CHKSUM64) $@

$(ROM_NAME).bin: $(ROM_NAME).elf
	@echo "  [OBJCOPY] $@"
	$(OBJCOPY) -O binary $< $@

$(ROM_NAME).elf: $(OBJECTS)
	@echo "  [LD] $@"
	$(LD) -o $@ $^ $(LDFLAGS)

%.o: %.c
	@echo "  [CC] $<"
	$(CC) $(CFLAGS) -c -o $@ $<

clean:
	rm -f $(OBJECTS) $(ROM_NAME).elf $(ROM_NAME).bin $(ROM_NAME).z64

# Host-side tests (no N64 hardware needed)
test:
	python3 -m pytest test_host_relay.py test_fingerprint.py -v
