# RustChain PS1 Miner Makefile
# Uses PSn00bSDK toolchain

# PSn00bSDK path (adjust as needed)
PSNOOBSDK ?= /opt/PSn00bSDK

# Toolchain
CC = mips-linux-gnu-gcc
AS = mips-linux-gnu-as
LD = mips-linux-gnu-ld
OBJCOPY = mips-linux-gnu-objcopy

# If PSn00bSDK is available, use its toolchain
ifneq ($(wildcard $(PSNOOBSDK)/bin/mips-psn00b-gcc),)
    CC = $(PSNOOBSDK)/bin/mips-psn00b-gcc
    LD = $(PSNOOBSDK)/bin/mips-psn00b-ld
endif

# Target
TARGET = rustchain_ps1_miner
OUTPUT_BIN = $(TARGET).bin
OUTPUT_EXE = $(TARGET).exe

# Source files
SRCS = main.c sha256.c serial.c fingerprint.c memcard.c

# Object files
OBJS = $(SRCS:.c=.o)

# Compiler flags
CFLAGS = -mips1 -mcpu=3000
CFLAGS += -G0 -mno-abicalls -mno-plt
CFLAGS += -ffreestanding -fno-builtin
CFLAGS += -Wall -Wextra -O2
CFLAGS += -I$(PSNOOBSDK)/include
CFLAGS += -I.

# Linker flags
LDFLAGS = -T $(PSNOOBSDK)/lib/psx.ld
LDFLAGS += -nostdlib
LDFLAGS += -L$(PSNOOBSDK)/lib
LDFLAGS += -lpsxgpu -lpsxapi -lpsxpad -lc

# Default target
all: $(OUTPUT_BIN)

# Link
$(OUTPUT_EXE): $(OBJS)
	$(CC) $(LDFLAGS) -o $@ $^
	@echo "Linked $(OUTPUT_EXE)"

# Convert to binary
$(OUTPUT_BIN): $(OUTPUT_EXE)
	$(OBJCOPY) -O binary $< $@
	@echo "Created $(OUTPUT_BIN)"
	@ls -la $@

# Compile C files
%.o: %.c
	$(CC) $(CFLAGS) -c -o $@ $<

# Clean
clean:
	rm -f $(OBJS) $(OUTPUT_EXE) $(OUTPUT_BIN)
	@echo "Cleaned"

# Test with emulator (requires DuckStation CLI)
test: $(OUTPUT_BIN)
	@echo "Testing with DuckStation..."
	duckstation --batch --exit-on-startup $(OUTPUT_BIN)

# Install to memory card (requires PS1 Link Cable)
install: $(OUTPUT_BIN)
	@echo "Installing to PS1..."
	psn00b-link upload $(OUTPUT_BIN)

# Help
help:
	@echo "RustChain PS1 Miner Build System"
	@echo ""
	@echo "Targets:"
	@echo "  all       - Build miner binary (default)"
	@echo "  clean     - Remove build artifacts"
	@echo "  test      - Test with DuckStation emulator"
	@echo "  install   - Upload to PS1 via link cable"
	@echo "  help      - Show this help"
	@echo ""
	@echo "Requirements:"
	@echo "  - PSn00bSDK or MIPS cross-compiler"
	@echo "  - PS1 SDK libraries (libpsxgpu, libpsxapi, etc.)"

.PHONY: all clean test install help
