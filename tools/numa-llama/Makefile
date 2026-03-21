# Makefile for NUMA-Aware llama.cpp Sharding
#
# Targets:
#   all         - Build POWER8 version (default)
#   x86         - Build x86 version (cross-platform)
#   benchmark   - Build benchmark harness
#   detect      - Build NUMA topology detection utility
#   clean       - Clean build artifacts
#   install     - Install headers and libs
#
# Usage:
#   make                    # POWER8 build
#   make x86                # x86 build
#   make benchmark          # Build benchmark
#   make detect             # Build topology detector
#   make clean              # Clean artifacts
#

# ============================================================================
# Configuration
# ============================================================================

PREFIX ?= /usr/local
INSTALL_INCLUDE = $(PREFIX)/include
INSTALL_LIB = $(PREFIX)/lib

# Build flags
CFLAGS ?= -O3 -Wall -Wextra -std=c11
LDFLAGS ?=

# ============================================================================
# POWER8 (IBM S824) Build
# ============================================================================

# POWER8-specific flags
POWER8_CFLAGS = -mcpu=power8 -mvsx -O3 -Wall -Wextra
POWER8_LDFLAGS = -lnuma -lpthread
POWER8_TARGETS = libnuma_shard.a benchmark detect

# ============================================================================
# x86 Build (cross-platform, NUMA code compiled out)
# ============================================================================

X86_CFLAGS = -O3 -Wall -Wextra -std=c11 -march=native
X86_LDFLAGS = -lpthread
X86_TARGETS = libnuma_shard_x86.a

# ============================================================================
# Source Files
# ============================================================================

NUMA_SHARD_H = ggml-numa-shard.h
NUMA_POLICY_H = numa_policy.h

BENCHMARK_SRC = numa_benchmark.c
BENCHMARK_OBJ = numa_benchmark.o

DETECT_SRC = numa_detect.c
DETECT_OBJ = numa_detect.o

LIB_OBJ = ggml-numa-shard.o

# ============================================================================
# Pattern Rules
# ============================================================================

.PHONY: all x86 power8 benchmark detect clean install

all: power8

power8: CFLAGS = $(POWER8_CFLAGS)
power8: LDFLAGS = $(POWER8_LDFLAGS)
power8: $(POWER8_TARGETS)
	@echo "POWER8 build complete"

x86: CFLAGS = $(X86_CFLAGS)
x86: LDFLAGS = $(X86_LDFLAGS)
x86: $(X86_TARGETS)
	@echo "x86 build complete"

# ============================================================================
# Build Rules
# ============================================================================

# NUMA Shard static library (POWER8)
libnuma_shard.a: $(LIB_OBJ)
	ar rcs $@ $(LIB_OBJ)
	@echo "Created $@"

ggml-numa-shard.o: $(NUMA_SHARD_H) $(NUMA_POLICY_H)
	$(CC) $(CFLAGS) -DGGML_NUMA_IMPLEMENTATION -c ggml-numa-shard.h -o $@

# NUMA Shard static library (x86 - no NUMA code)
libnuma_shard_x86.a: ggml-numa-shard-x86.o
	ar rcs $@ $<
	@echo "Created $@"

ggml-numa-shard-x86.o: $(NUMA_SHARD_H) $(NUMA_POLICY_H)
	$(CC) $(X86_CFLAGS) -DGGML_NUMA_ARCH_POWER=0 -DGGML_NUMA_LINUX=0 -c ggml-numa-shard.h -o $@

# Benchmark harness
benchmark: $(BENCHMARK_OBJ) libnuma_shard.a
	$(CC) $(CFLAGS) -o $@ $(BENCHMARK_OBJ) -L. -lnuma_shard $(LDFLAGS)
	@echo "Built benchmark"

numa_benchmark.o: $(BENCHMARK_SRC) $(NUMA_SHARD_H)
	$(CC) $(CFLAGS) -c $(BENCHMARK_SRC) -o $@

# NUMA topology detector
detect: $(DETECT_OBJ)
	$(CC) $(CFLAGS) -o $@ $(DETECT_OBJ) $(LDFLAGS)
	@echo "Built numa_detect"

numa_detect.o: $(DETECT_SRC)
	$(CC) $(CFLAGS) -c $(DETECT_SRC) -o $@

# ============================================================================
# Install
# ============================================================================

install:
	@echo "Installing NUMA-Shard headers..."
	install -d $(INSTALL_INCLUDE)
	install -m 644 $(NUMA_SHARD_H) $(INSTALL_INCLUDE)/
	install -m 644 $(NUMA_POLICY_H) $(INSTALL_INCLUDE)/
	@echo "Installing libraries..."
	install -d $(INSTALL_LIB)
	install -m 644 libnuma_shard.a $(INSTALL_LIB)/
	@echo "Install complete"

# ============================================================================
# Clean
# ============================================================================

clean:
	rm -f *.o *.a benchmark detect
	rm -f libnuma_shard.a libnuma_shard_x86.a

# ============================================================================
# Help
# ============================================================================

help:
	@echo "NUMA-Aware llama.cpp Sharding - Build System"
	@echo ""
	@echo "Targets:"
	@echo "  all       Build POWER8 version (default)"
	@echo "  power8    Build for IBM POWER8 (S824) with -mcpu=power8 -mvsx"
	@echo "  x86       Build cross-platform x86 version (NUMA compiled out)"
	@echo "  benchmark Build benchmark harness"
	@echo "  detect    Build NUMA topology detection utility"
	@echo "  clean     Remove build artifacts"
	@echo "  install   Install headers and libraries"
	@echo ""
	@echo "Environment variables:"
	@echo "  CFLAGS    Override compiler flags"
	@echo "  LDFLAGS   Override linker flags"
	@echo "  PREFIX    Install prefix (default: /usr/local)"
	@echo ""
	@echo "Examples:"
	@echo "  make                      # POWER8 build"
	@echo "  make x86                  # x86 build"
	@echo "  make benchmark CC=gcc-9   # POWER8 with specific compiler"
	@echo "  make install PREFIX=/opt  # Install to /opt"
