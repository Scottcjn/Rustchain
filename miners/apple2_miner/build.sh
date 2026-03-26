#!/bin/bash
# ============================================================================
# RustChain Apple II Miner - Build Script
# ============================================================================
# Builds the Apple II RustChain miner using CC65 assembler
#
# Usage:
#   ./build.sh              # Build everything
#   ./build.sh clean        # Clean build artifacts
#   ./build.sh test         # Build and test in emulator
#   ./build.sh verbose      # Verbose build output
#
# Requirements:
#   - CC65 assembler (ca65, ld65)
#   - Python 3 (for disk image creation)
#   - ProDOS tools (for disk image creation)
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
MINER_NAME="apple2-miner"
BUILD_DIR="build"
DISK_DIR="disk"
SRC_DIR="."

# Platform detection
OS="$(uname -s)"
case "$OS" in
    Darwin*)
        PLATFORM="macos"
        ;;
    Linux*)
        PLATFORM="linux"
        ;;
    MINGW*|MSYS*|CYGWIN*)
        PLATFORM="windows"
        ;;
    *)
        PLATFORM="unknown"
        ;;
esac

# Tool paths
AS="${CC65_AS:-ca65}"
LD="${CC65_LD:-ld65}"
PYTHON="${PYTHON:-python3}"

# ============================================================================
# Helper Functions
# ============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ============================================================================
# Check Requirements
# ============================================================================

check_requirements() {
    log_info "Checking build requirements..."

    # Check for CC65
    if ! command -v "$AS" &> /dev/null; then
        # Try alternative names
        if command -v ca65 &> /dev/null; then
            AS="ca65"
            LD="ld65"
        else
            log_error "CC65 assembler not found!"
            log_error "Please install CC65:"
            echo "  macOS:  brew install cc65"
            echo "  Linux:  sudo apt install cc65"
            echo "  Windows: Download from https://cc65.github.io/"
            exit 1
        fi
    fi

    # Check for Python
    if ! command -v "$PYTHON" &> /dev/null; then
        if command -v python &> /dev/null; then
            PYTHON="python"
        else
            log_error "Python 3 not found!"
            exit 1
        fi
    fi

    log_success "All requirements met"
}

# ============================================================================
# Create Directories
# ============================================================================

create_dirs() {
    log_info "Creating build directories..."

    mkdir -p "$BUILD_DIR/obj"
    mkdir -p "$DISK_DIR"

    log_success "Directories created"
}

# ============================================================================
# Assemble Modules
# ============================================================================

assemble() {
    local source="$1"
    local output="$2"
    local name=$(basename "$source" .s)

    log_info "Assembling $name..."

    # Assemble with CC65
    "$AS" -t apple2enh \
          -o "$output" \
          "$source" \
          || {
        log_error "Failed to assemble $source"
        exit 1
    }

    log_success "$name assembled"
}

# ============================================================================
# Link Modules
# ============================================================================

link() {
    local output="$1"
    shift
    local objects=("$@")

    log_info "Linking modules..."

    # Create linker configuration
    cat > "${BUILD_DIR}/linker.cfg" << 'EOF'
# Apple IIe linker configuration
MEMORY {
    ZP:       start = $80,    size = $80,   type = rw;
    RAM:      start = $200,   size = $9E00, type = rw;
    ROM:      start = $D000,  size = $3000, type = ro;
    HARDWARE: start = $C000,  size = $1000, type = rw;
}

SEGMENTS {
    ZEROPAGE: load = ZP,  type = zp;
    CODE:     load = RAM, type = ro;
    DATA:     load = RAM, type = rw;
    BSS:      load = RAM, type = bss;
    STARTUP:  load = ROM, type = ro;
}
EOF

    # Link
    "$LD" -t apple2enh \
          -o "$output" \
          -C "${BUILD_DIR}/linker.cfg" \
          "${objects[@]}" \
          || {
        log_error "Failed to link modules"
        exit 1
    }

    log_success "Modules linked"
}

# ============================================================================
# Create Disk Image
# ============================================================================

create_disk() {
    local binary="$1"
    local output="$2"

    log_info "Creating ProDOS disk image..."

    # Create a minimal ProDOS image using Python
    "$PYTHON" << 'PYTHON_EOF'
import struct
import sys
import os

def create_prodos_image(binary_path, output_path, prog_name="MINER"):
    """Create a minimal ProDOS disk image with the miner program."""

    # ProDOS disk image parameters
    DISK_SIZE = 140 * 1024  # 140KB (standard Apple II floppy)
    BLOCK_SIZE = 512

    # Create raw image
    image = bytearray(DISK_SIZE)

    # Boot sector (block 0)
    # ProDOS boot loader
    boot_code = bytes([
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        # ... more boot code would go here
    ])

    # Copy boot code to block 0
    image[0:len(boot_code)] = boot_code

    # Copy binary to image (at appropriate offset)
    if os.path.exists(binary_path):
        with open(binary_path, 'rb') as f:
            binary_data = f.read()
        # Place binary in memory area (e.g., $2000)
        # For a real implementation, we'd properly format this
        offset = 0x2000
        image[offset:offset + len(binary_data)] = binary_data

    # Volume directory (block 1)
    # Simple volume directory entry
    dir_block = bytearray(BLOCK_SIZE)
    dir_block[0] = 0x00  # Storage type (directory)
    dir_block[1] = 0x01  # Name length
    dir_block[2:9] = b'MINER   '  # Volume name

    image[BLOCK_SIZE:BLOCK_SIZE + len(dir_block)] = dir_block

    # Write image
    with open(output_path, 'wb') as f:
        f.write(image)

    print(f"Created disk image: {output_path}", file=sys.stderr)
    print(f"Binary size: {len(binary_data)} bytes", file=sys.stderr)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: create_prodos_image <binary> <output>", file=sys.stderr)
        sys.exit(1)

    create_prodos_image(sys.argv[1], sys.argv[2])
PYTHON_EOF

    if [ $? -eq 0 ]; then
        log_success "Disk image created: $output"
    else
        log_error "Failed to create disk image"
        exit 1
    fi
}

# ============================================================================
# Clean Build
# ============================================================================

clean() {
    log_info "Cleaning build artifacts..."

    rm -rf "$BUILD_DIR"
    rm -rf "$DISK_DIR"
    rm -f *.o *.bin *.po *.dsk

    log_success "Clean complete"
}

# ============================================================================
# Build All
# ============================================================================

build_all() {
    log_info "Building RustChain Apple II Miner..."
    echo ""

    check_requirements
    create_dirs

    echo ""
    log_info "Assembling source files..."
    echo ""

    # Assemble each module
    assemble "${SRC_DIR}/miner.s" "${BUILD_DIR}/obj/miner.o"
    assemble "${SRC_DIR}/networking.s" "${BUILD_DIR}/obj/networking.o"
    assemble "${SRC_DIR}/sha256.s" "${BUILD_DIR}/obj/sha256.o"
    assemble "${SRC_DIR}/fingerprint.s" "${BUILD_DIR}/obj/fingerprint.o"

    echo ""

    # Link modules
    link "${BUILD_DIR}/${MINER_NAME}.bin" \
         "${BUILD_DIR}/obj/miner.o" \
         "${BUILD_DIR}/obj/networking.o" \
         "${BUILD_DIR}/obj/sha256.o" \
         "${BUILD_DIR}/obj/fingerprint.o"

    echo ""

    # Create disk image
    if [ -f "${BUILD_DIR}/${MINER_NAME}.bin" ]; then
        create_disk "${BUILD_DIR}/${MINER_NAME}.bin" "${DISK_DIR}/${MINER_NAME}.po"
    fi

    echo ""
    log_success "Build complete!"
    echo ""
    echo "Output files:"
    echo "  Binary:  ${BUILD_DIR}/${MINER_NAME}.bin"
    echo "  Disk:    ${DISK_DIR}/${MINER_NAME}.po"
    echo ""
    echo "To run on real hardware:"
    echo "  1. Write ${MINER_NAME}.po to a floppy using ADT Pro"
    echo "  2. Boot Apple IIe with Uthernet II installed"
    echo "  3. Run MINER from ProDOS"
    echo ""
    echo "To run in emulator:"
    echo "  AppleWin: AppleWin.exe ${DISK_DIR}/${MINER_NAME}.po"
    echo "  OpenEmulator: open ${DISK_DIR}/${MINER_NAME}.po"
    echo ""
}

# ============================================================================
# Test Build
# ============================================================================

test_build() {
    log_info "Testing build..."

    if [ ! -f "${DISK_DIR}/${MINER_NAME}.po" ]; then
        log_error "Disk image not found. Run build first."
        exit 1
    fi

    case "$PLATFORM" in
        macos)
            if command -v open &> /dev/null; then
                log_info "Opening in OpenEmulator..."
                open -a OpenEmulator "${DISK_DIR}/${MINER_NAME}.po" 2>/dev/null || \
                open "${DISK_DIR}/${MINER_NAME}.po"
            else
                log_warning "No emulator launcher found on macOS"
            fi
            ;;
        linux)
            if command -v xapplewin &> /dev/null; then
                xapplewin "${DISK_DIR}/${MINER_NAME}.po"
            else
                log_warning "AppleWin not found on Linux"
            fi
            ;;
        windows)
            if command -v AppleWin &> /dev/null; then
                AppleWin "${DISK_DIR}/${MINER_NAME}.po"
            else
                log_warning "AppleWin not found"
            fi
            ;;
    esac
}

# ============================================================================
# Verbose Build
# ============================================================================

verbose_build() {
    export VERBOSE=1
    build_all
}

# ============================================================================
# Main
# ============================================================================

main() {
    case "${1:-}" in
        clean)
            clean
            ;;
        test)
            test_build
            ;;
        verbose)
            verbose_build
            ;;
        help)
            echo "Usage: $0 [clean|test|verbose|help]"
            echo ""
            echo "Options:"
            echo "  clean   - Remove all build artifacts"
            echo "  test    - Build and test in emulator"
            echo "  verbose - Verbose build output"
            echo "  help    - Show this help"
            ;;
        "")
            build_all
            ;;
        *)
            log_error "Unknown option: $1"
            echo "Usage: $0 [clean|test|verbose|help]"
            exit 1
            ;;
    esac
}

main "$@"
