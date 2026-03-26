# ============================================================================
# RustChain Apple II Miner - Makefile
# ============================================================================
# Build configuration for CC65 assembler
#
# Targets:
#   all        - Build the complete miner
#   miner      - Assemble miner.s
#   networking - Assemble networking.s
#   sha256     - Assemble sha256.s
#   fingerprint - Assemble fingerprint.s
#   disk       - Create ProDOS disk image
#   clean      - Remove built files
#   test       - Run in emulator (if available)
#
# Usage:
#   make               # Build everything
#   make all           # Same as above
#   make disk          # Create disk image
#   make clean         # Clean build artifacts
#   make test          # Test in emulator
# ============================================================================

# Compiler and tools
AS      = ca65
LD      = ld65
AR      = ar65
NM      = nm65
OBJDUMP = objdmp65

# Assembler flags
ASFLAGS = -t apple2enh \
          --list-bytes 8 \
          --max-width 8 \
          -v

# Linker flags
LDFLAGS = -t apple2enh \
          --config apple2-asm.cfg \
          -v

# Output directories
BUILD_DIR = build
DISK_DIR = disk
OBJ_DIR = $(BUILD_DIR)/obj

# Output files
MINER_BIN = $(OBJ_DIR)/miner.o
NET_BIN = $(OBJ_DIR)/networking.o
SHA_BIN = $(OBJ_DIR)/sha256.o
FP_BIN = $(OBJ_DIR)/fingerprint.o
FINAL_BIN = $(BUILD_DIR)/miner.bin
DISK_IMAGE = $(DISK_DIR)/apple2-miner.po

# Source files
SOURCES = miner.s networking.s sha256.s fingerprint.s
OBJECTS = $(SOURCES:.s=$(_OBJ))

# Include paths
INCLUDES = -I./inc

# ============================================================================
# Default target
# ============================================================================

.PHONY: all
all: dirs $(FINAL_BIN) $(DISK_IMAGE)

# ============================================================================
# Directory setup
# ============================================================================

.PHONY: dirs
dirs:
	@mkdir -p $(BUILD_DIR)
	@mkdir -p $(OBJ_DIR)
	@mkdir -p $(DISK_DIR)

# ============================================================================
# Object files
# ============================================================================

miner.o: miner.s
	$(AS) $(ASFLAGS) -o $(MINER_BIN) miner.s

networking.o: networking.s
	$(AS) $(ASFLAGS) -o $(NET_BIN) networking.s

sha256.o: sha256.s
	$(AS) $(ASFLAGS) -o $(SHA_BIN) sha256.s

fingerprint.o: fingerprint.s
	$(AS) $(ASFLAGS) -o $(FP_BIN) fingerprint.s

# ============================================================================
# Final linked binary
# ============================================================================

$(FINAL_BIN): $(OBJECTS)
	$(LD) $(LDFLAGS) -o $@ $^

# ============================================================================
# Disk image creation
# ============================================================================

$(DISK_IMAGE): $(FINAL_BIN)
	@echo "Creating ProDOS disk image..."
	@# Create a basic ProDOS disk image
	@# This uses the cdrtools or similar tools if available
	@# For CC65, we use the toolbin utility

	@# First, create a blank ProDOS image
	python3 make_disk.py --output $(DISK_IMAGE) --input $(FINAL_BIN) --boot MINER

	@echo "Disk image created: $(DISK_IMAGE)"

# ============================================================================
# Individual assembly targets
# ============================================================================

.PHONY: miner networking sha256 fingerprint
miner: $(MINER_BIN)
	@echo "Miner assembled: $(MINER_BIN)"

networking: $(NET_BIN)
	@echo "Networking assembled: $(NET_BIN)"

sha256: $(SHA_BIN)
	@echo "SHA256 assembled: $(SHA_BIN)"

fingerprint: $(FP_BIN)
	@echo "Fingerprint assembled: $(FP_BIN)"

# ============================================================================
# Listing and debugging
# ============================================================================

.PHONY: list symbols
list: $(FINAL_BIN)
	$(OBJDUMP) -h $(FINAL_BIN)

symbols: $(FINAL_BIN)
	$(NM) $(FINAL_BIN)

# ============================================================================
# Clean
# ============================================================================

.PHONY: clean
clean:
	rm -rf $(BUILD_DIR)
	rm -rf $(DISK_DIR)
	rm -f *.o *.bin *.po *.dsk

# ============================================================================
# Test in emulator
# ============================================================================

.PHONY: test
test: $(DISK_IMAGE)
	@echo "Testing in emulator..."
	@if command -v AppleWin &> /dev/null; then \
		AppleWin $(DISK_IMAGE); \
	elif command -v xapplewin &> /dev/null; then \
		xapplewin $(DISK_IMAGE); \
	elif command -v open &> /dev/null; then \
		open -a OpenEmulator $(DISK_IMAGE) 2>/dev/null || \
		open $(DISK_IMAGE); \
	else \
		echo "No emulator found. Please install AppleWin, OpenEmulator, or MAME."; \
	fi

# ============================================================================
# Debug build
# ============================================================================

.PHONY: debug
debug: ASFLAGS += --debug
debug: all

# ============================================================================
# Verbose build
# ============================================================================

.PHONY: verbose
verbose:
	$(MAKE) ASFLAGS="-v" LD_FLAGS="-v"

# ============================================================================
# Help
# ============================================================================

.PHONY: help
help:
	@echo "RustChain Apple II Miner - Build Targets"
	@echo ""
	@echo "  all          - Build the complete miner (default)"
	@echo "  miner        - Assemble main miner module"
	@echo "  networking   - Assemble networking module"
	@echo "  sha256       - Assemble SHA256 module"
	@echo "  fingerprint  - Assemble fingerprint module"
	@echo "  disk         - Create ProDOS disk image"
	@echo "  clean        - Remove all built files"
	@echo "  test         - Run miner in emulator"
	@echo "  list         - Show binary sections"
	@echo "  symbols      - Show symbol table"
	@echo "  debug        - Build with debug info"
	@echo "  help         - Show this help"
	@echo ""
	@echo "Requirements:"
	@echo "  - CC65 assembler (ca65, ld65)"
	@echo "  - Python 3 (for disk image creation)"
	@echo "  - ProDOS image tools"
	@echo ""
	@echo "Install CC65:"
	@echo "  macOS:  brew install cc65"
	@echo "  Linux:  sudo apt install cc65"
	@echo "  Windows: Download from https://cc65.github.io/"

# ============================================================================
# Dependencies
# ============================================================================

-include $(SOURCES:.s=.d)

%.d: %.s
	$(AS) $(ASFLAGS) -o /dev/null -M $< > $@

# ============================================================================
# END OF FILE
# ============================================================================
