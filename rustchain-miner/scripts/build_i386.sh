#!/bin/bash
# Intel 386 Cross-Compilation Build Script for RustChain Miner
#
# Bounty #435: Port RustChain Miner to Intel 386
# https://github.com/Scottcjn/rustchain-bounties/issues/435
#
# This script builds the RustChain miner for Intel 386 (i686) architectures.
# The 80386 launched in 1985 - the CPU that started the x86 era.
#
# Usage:
#   ./build_i386.sh [OPTIONS]
#
# Options:
#   --musl          Build for musl (static linking, recommended for vintage)
#   --release       Build in release mode
#   --clean         Clean before building
#   --test          Run tests after building
#   --docker        Use Docker-based build environment
#   --help          Show this help message

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default options
MUSL=true  # Default to musl for static linking (better for vintage systems)
RELEASE=true
CLEAN=false
TEST=false
DOCKER=false

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MINER_DIR="$(dirname "$SCRIPT_DIR")"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --musl)
            MUSL=true
            shift
            ;;
        --gnu)
            MUSL=false
            shift
            ;;
        --release)
            RELEASE=true
            shift
            ;;
        --debug)
            RELEASE=false
            shift
            ;;
        --clean)
            CLEAN=true
            shift
            ;;
        --test)
            TEST=true
            shift
            ;;
        --docker)
            DOCKER=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --musl          Build for musl (static linking) [default]"
            echo "  --gnu            Build for glibc (dynamic linking)"
            echo "  --release        Build in release mode [default]"
            echo "  --debug          Build in debug mode"
            echo "  --clean          Clean before building"
            echo "  --test           Run tests after building"
            echo "  --docker         Use Docker-based build environment"
            echo "  --help           Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Set target based on musl option
if [ "$MUSL" = true ]; then
    TARGET="i686-unknown-linux-musl"
    TARGET_NAME="Intel 386 (i686-musl static)"
else
    TARGET="i686-unknown-linux-gnu"
    TARGET_NAME="Intel 386 (i686-glibc)"
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  RustChain Miner Intel 386 Build${NC}"
echo -e "${BLUE}  Bounty #435${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${GREEN}Target:${NC} $TARGET_NAME"
echo -e "${GREEN}Release:${NC} $RELEASE"
echo -e "${GREEN}Clean:${NC} $CLEAN"
echo -e "${GREEN}Test:${NC} $TEST"
echo -e "${GREEN}Docker:${NC} $DOCKER"
echo ""

# Function to check prerequisites
check_prerequisites() {
    echo -e "${YELLOW}Checking prerequisites...${NC}"

    # Check for Rust
    if ! command -v rustc &> /dev/null; then
        echo -e "${RED}Error: Rust is not installed${NC}"
        echo "Install from: https://rustup.rs/"
        exit 1
    fi

    # Check for cross tool (optional but recommended)
    if ! command -v cross &> /dev/null; then
        echo -e "${YELLOW}Warning: 'cross' is not installed. Installing...${NC}"
        cargo install cross --git https://github.com/cross-rs/cross
    fi

    # Check for Docker if using Docker build
    if [ "$DOCKER" = true ]; then
        if ! command -v docker &> /dev/null; then
            echo -e "${RED}Error: Docker is not installed${NC}"
            exit 1
        fi
    fi

    # Check for i386 toolchain (only for native builds)
    if [ "$DOCKER" = false ]; then
        if ! command -v i686-linux-gnu-gcc &> /dev/null && ! command -v i686-linux-musl-gcc &> /dev/null; then
            echo -e "${YELLOW}i386/i686 toolchain not found. Installing...${NC}"

            # Detect OS
            if [[ "$OSTYPE" == "linux-gnu"* ]]; then
                if command -v apt-get &> /dev/null; then
                    if [ "$MUSL" = true ]; then
                        sudo apt-get update
                        sudo apt-get install -y gcc-i686-linux-musl libc6-dev-i386-cross musl-tools
                    else
                        sudo apt-get update
                        sudo apt-get install -y gcc-i686-linux-gnu g++-i686-linux-gnu libc6-dev-i386-cross
                    fi
                elif command -v dnf &> /dev/null; then
                    if [ "$MUSL" = true ]; then
                        sudo dnf install -y gcc-i686-linux-musl musl-devel
                    else
                        sudo dnf install -y gcc-i686-linux-gnu glibc-devel.i686 libstdc++-devel.i686
                    fi
                elif command -v pacman &> /dev/null; then
                    sudo pacman -S i686-linux-gnu-gcc
                fi
            elif [[ "$OSTYPE" == "darwin"* ]]; then
                echo -e "${RED}Error: Native i386 cross-compile not supported on macOS${NC}"
                echo "Use --docker option for Docker-based build"
                exit 1
            fi
        fi
    fi

    echo -e "${GREEN}✓ Prerequisites check passed${NC}"
    echo ""
}

# Function to clean build artifacts
clean_build() {
    echo -e "${YELLOW}Cleaning build artifacts...${NC}"
    cd "$MINER_DIR"
    cargo clean
    rm -rf target/$TARGET
    echo -e "${GREEN}✓ Clean complete${NC}"
    echo ""
}

# Function to run tests
run_tests() {
    echo -e "${YELLOW}Running tests...${NC}"
    cd "$MINER_DIR"

    if [ "$DOCKER" = true ]; then
        cross test --target $TARGET
    else
        cargo test --target $TARGET
    fi

    echo -e "${GREEN}✓ Tests complete${NC}"
    echo ""
}

# Function to build with Docker
build_docker() {
    echo -e "${YELLOW}Building with Docker...${NC}"

    # Create Dockerfile for i386 build
    DOCKERFILE_CONTENT=$(cat <<'EOF'
FROM i386/ubuntu:20.04

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    pkg-config \
    libssl-dev \
    openssl \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Rust
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y

ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /workspace
EOF
)

    echo "$DOCKERFILE_CONTENT" > "$MINER_DIR/Dockerfile.i386"

    # Build Docker image
    docker build -t rustchain-i386-builder -f "$MINER_DIR/Dockerfile.i386" "$MINER_DIR"

    # Run build in container
    docker run --rm \
        -v "$MINER_DIR":/workspace \
        -w /workspace \
        rustchain-i386-builder \
        bash -c "rustup target add $TARGET && cargo build --target $TARGET $( [ "$RELEASE" = true ] && echo '--release' )"

    # Cleanup
    rm "$MINER_DIR/Dockerfile.i386"

    echo -e "${GREEN}✓ Docker build complete${NC}"
    echo ""
}

# Function to build natively
build_native() {
    echo -e "${YELLOW}Building natively...${NC}"
    cd "$MINER_DIR"

    # Add target if not already installed
    rustup target add $TARGET 2>/dev/null || true

    # Set environment variables for cross-compilation
    if [ "$MUSL" = true ]; then
        export CARGO_TARGET_I686_UNKNOWN_LINUX_MUSL_LINKER=i686-linux-musl-gcc
    else
        export CARGO_TARGET_I686_UNKNOWN_LINUX_GNU_LINKER=i686-linux-gnu-gcc
    fi
    export PKG_CONFIG_ALLOW_CROSS=1

    if [ "$RELEASE" = true ]; then
        cargo build --target $TARGET --release
    else
        cargo build --target $TARGET
    fi

    echo -e "${GREEN}✓ Native build complete${NC}"
    echo ""
}

# Function to display build results
show_results() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  Build Results${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    if [ "$RELEASE" = true ]; then
        BINARY_PATH="$MINER_DIR/target/$TARGET/release/rustchain-miner"
    else
        BINARY_PATH="$MINER_DIR/target/$TARGET/debug/rustchain-miner"
    fi

    if [ -f "$BINARY_PATH" ]; then
        echo -e "${GREEN}✓ Binary created:${NC} $BINARY_PATH"
        echo ""

        # Show binary info
        echo -e "${YELLOW}Binary Information:${NC}"
        file "$BINARY_PATH" 2>/dev/null || echo "  (file command not available)"
        echo ""

        # Show binary size
        ls -lh "$BINARY_PATH" 2>/dev/null | awk '{print "Size: " $5}' || echo "Size: (unknown)"

        # Try to show architecture (if readelf is available)
        if command -v readelf &> /dev/null; then
            echo ""
            echo -e "${YELLOW}Architecture:${NC}"
            readelf -h "$BINARY_PATH" 2>/dev/null | grep -E "Machine|Class" || true
        fi
    else
        echo -e "${RED}✗ Build failed - binary not found${NC}"
        exit 1
    fi

    echo ""
}

# Main build process
main() {
    check_prerequisites

    if [ "$CLEAN" = true ]; then
        clean_build
    fi

    if [ "$TEST" = true ]; then
        run_tests
    fi

    if [ "$DOCKER" = true ]; then
        build_docker
    else
        build_native
    fi

    show_results

    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Intel 386 Build Complete!${NC}"
    echo -e "${GREEN}  Bounty #435${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "${YELLOW}Note on 386 Compatibility:${NC}"
    echo "  The i686 target is the closest modern target to i386."
    echo "  For true i386 compatibility, consider using ELKS or"
    echo "  building with -march=i386 -mtune=i486."
    echo ""
    echo -e "To deploy to Intel 386 hardware:"
    echo -e "  1. Copy binary to your 386 system"
    echo -e "  2. Ensure you have ELKS or a compatible Linux distribution"
    echo -e "  3. Configure networking (NE2000 compatible card recommended)"
    echo -e "  4. Run: ${YELLOW}./rustchain-miner --wallet YOUR_WALLET${NC}"
    echo ""
    echo -e "Hardware Requirements for Intel 386 Mining:"
    echo -e "  - Intel 80386DX or 80386SX"
    echo -e "  - 4MB RAM minimum (8MB+ recommended)"
    echo -e "  - NE2000 compatible Ethernet"
    echo -e "  - Boot media (CF-to-IDE or floppy)"
    echo ""
    echo -e "Antiquity Multiplier: 4.0x (MAXIMUM)"
    echo "This is the highest possible reward tier in RustChain!"
    echo ""
}

main
