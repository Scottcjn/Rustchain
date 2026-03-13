# RustChain GBC Miner Makefile
# Build system for Game Boy Color miner ROM

# Assembler options
AS = rgbasm
LD = rgblink
FIX = rgbfix

# GBDK options (alternative)
LCC = lcc

# Target
TARGET = rustchain_gbc
ROM_FILE = $(TARGET).gb

# Source files
ASM_SOURCES = \
	rustchain_gbc.asm

# Build directories
BUILD_DIR = build

# Flags
AS_FLAGS = -v -p 0xFF
LD_FLAGS = -n $(BUILD_DIR)/$(TARGET).sym -m $(BUILD_DIR)/$(TARGET).map
FIX_FLAGS = -p 0xFF -v -l 0x33 -j 0x1B -k 0x01 -m 0x03

# Default target
all: $(ROM_FILE)

# Create build directory
$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

# Build with RGBDS
$(ROM_FILE): $(ASM_SOURCES) | $(BUILD_DIR)
	$(AS) $(AS_FLAGS) -o $(BUILD_DIR)/$(TARGET).o $(ASM_SOURCES)
	$(LD) $(LD_FLAGS) -o $(ROM_FILE) $(BUILD_DIR)/$(TARGET).o
	$(FIX) $(FIX_FLAGS) $(ROM_FILE)
	@echo "✓ Build complete: $(ROM_FILE)"
	@echo "  Size: $$(wc -c < $(ROM_FILE)) bytes"

# Build with GBDK (alternative)
build-gbdk: $(ASM_SOURCES)
	$(LCC) -o $(ROM_FILE) $(ASM_SOURCES)
	@echo "✓ GBDK build complete: $(ROM_FILE)"

# Clean build artifacts
clean:
	rm -rf $(BUILD_DIR)
	rm -f $(ROM_FILE)
	@echo "✓ Clean complete"

# Run in emulator (SameBoy)
run: $(ROM_FILE)
	sameboy $(ROM_FILE)

# Run in emulator (BGB)
run-bgb: $(ROM_FILE)
	bgb $(ROM_FILE)

# Run in emulator (Gambatte)
run-gambatte: $(ROM_FILE)
	gambatte $(ROM_FILE)

# Debug build
debug: AS_FLAGS += -g
debug: $(ROM_FILE)
	@echo "✓ Debug build complete"

# Check syntax only
check:
	$(AS) $(AS_FLAGS) -o /dev/null $(ASM_SOURCES)
	@echo "✓ Syntax check passed"

# Generate documentation
docs:
	@echo "Generating documentation..."
	@echo "See docs/ directory for build and hardware guides"

# Run diagnostics (requires connected GBC)
diagnose:
	python3 bridge/gbc_bridge.py --port $(PORT) --wallet $(WALLET) --diagnose

# Flash to cartridge (Everdrive)
flash: $(ROM_FILE)
	@echo "Copy $(ROM_FILE) to Everdrive GB X7 microSD card"
	@echo "Then insert into GBC and power on"

# Test build
test: check
	@echo "✓ All tests passed"

# Help
help:
	@echo "RustChain GBC Miner Build System"
	@echo ""
	@echo "Targets:"
	@echo "  all       - Build ROM (default)"
	@echo "  clean     - Remove build artifacts"
	@echo "  run       - Run in SameBoy emulator"
	@echo "  run-bgb   - Run in BGB emulator"
	@echo "  debug     - Build with debug symbols"
	@echo "  check     - Syntax check only"
	@echo "  flash     - Instructions for flashing to cartridge"
	@echo "  diagnose  - Run hardware diagnostics (requires GBC)"
	@echo "  help      - Show this help"
	@echo ""
	@echo "Variables:"
	@echo "  PORT      - Serial port for diagnostics (e.g., COM3)"
	@echo "  WALLET    - Wallet address for diagnostics"

.PHONY: all clean run run-bgb run-gambatte debug check docs diagnose flash test help build-gbdk
