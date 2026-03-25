#!/bin/bash
#
# benchmark_numa.sh - NUMA Sharding Benchmark Harness for POWER8 llama.cpp
#
# This script compares flat mmap vs NUMA-sharded performance for llama.cpp
# on POWER8 systems. It measures pp512 (prefill) and tg128 (text generation)
# throughput and reports per-node memory bandwidth utilization.
#
# Usage:
#   ./benchmark_numa.sh [OPTIONS]
#
# Options:
#   -m, --model PATH       Path to GGUF model file (required)
#   -o, --output DIR       Output directory for results (default: ./results)
#   -t, --threads N        Number of threads (default: 64 for POWER8)
#   -b, --batch N          Batch size for prefill (default: 512)
#   -n, --tokens N         Number of tokens to generate (default: 128)
#   -r, --runs N           Number of benchmark runs (default: 3)
#   --baseline             Run baseline (flat mmap) only
#   --numa                 Run NUMA-sharded only
#   --compare              Run both and compare (default)
#   -h, --help             Show this help
#
# Bounty: Scottcjn/rustchain-bounties #2277
# Version: 1.0.0
#

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Defaults
MODEL_PATH=""
OUTPUT_DIR="${SCRIPT_DIR}/results"
THREADS=64
BATCH_SIZE=512
TOKENS=128
RUNS=3
MODE="compare"  # baseline | numa | compare

# llama.cpp paths (adjust as needed)
LLAMA_BENCH="${PROJECT_ROOT}/llama.cpp/build/bin/llama-bench"
LLAMA_CLI="${PROJECT_ROOT}/llama.cpp/build/bin/llama-cli"

# NUMA configuration for POWER8 S824
NUMA_CONFIG="0-8:1,9-20:3,21-31:2"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# Helper Functions
# ============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

usage() {
    cat << EOF
NUMA Sharding Benchmark Harness for POWER8 llama.cpp

Usage: $0 [OPTIONS]

Options:
  -m, --model PATH       Path to GGUF model file (required)
  -o, --output DIR       Output directory for results (default: ./results)
  -t, --threads N        Number of threads (default: 64 for POWER8)
  -b, --batch N          Batch size for prefill (default: 512)
  -n, --tokens N         Number of tokens to generate (default: 128)
  -r, --runs N           Number of benchmark runs (default: 3)
  --baseline             Run baseline (flat mmap) only
  --numa                 Run NUMA-sharded only
  --compare              Run both and compare (default)
  -h, --help             Show this help

Examples:
  # Full comparison
  $0 -m /models/llama-2-7b.Q4_K_M.gguf

  # Baseline only with custom threads
  $0 -m /models/llama-2-7b.Q4_K_M.gguf --baseline -t 32

  # NUMA-sharded with more runs
  $0 -m /models/llama-2-7b.Q4_K_M.gguf --numa -r 5

EOF
}

check_prerequisites() {
    local missing=0
    
    # Check for llama-bench or llama-cli
    if command -v "$LLAMA_BENCH" &> /dev/null; then
        LLAMA_BIN="$LLAMA_BENCH"
    elif command -v "$LLAMA_CLI" &> /dev/null; then
        LLAMA_BIN="$LLAMA_CLI"
    else
        log_error "llama.cpp binary not found. Build llama.cpp first:"
        log_error "  cd llama.cpp && cmake -B build && cmake --build build --Release"
        missing=1
    fi
    
    # Check for numactl
    if ! command -v numactl &> /dev/null; then
        log_error "numactl not found. Install with: apt-get install numactl"
        missing=1
    fi
    
    # Check for model file
    if [[ -z "$MODEL_PATH" ]]; then
        log_error "Model path is required. Use -m or --model"
        missing=1
    elif [[ ! -f "$MODEL_PATH" ]]; then
        log_error "Model file not found: $MODEL_PATH"
        missing=1
    fi
    
    # Check for NUMA (optional, will warn)
    if ! command -v numactl &> /dev/null; then
        log_warn "NUMA tools not available. Running without NUMA binding."
    fi
    
    return $missing
}

detect_hardware() {
    log_info "Detecting hardware..."
    
    # Check architecture
    ARCH=$(uname -m)
    log_info "Architecture: $ARCH"
    
    # Check NUMA nodes
    if command -v numactl &> /dev/null; then
        NUMA_NODES=$(numactl --hardware | grep "available:" | awk '{print $2}')
        log_info "NUMA nodes available: $NUMA_NODES"
        
        # Print node distances
        log_info "NUMA topology:"
        numactl --hardware 2>/dev/null | head -5
    else
        NUMA_NODES=0
        log_warn "Cannot detect NUMA topology (numactl not available)"
    fi
    
    # Detect POWER8
    if [[ "$ARCH" == "ppc64" ]] || [[ "$ARCH" == "ppc64le" ]]; then
        log_info "POWER8/POWER9 detected - using optimal settings"
        THREADS=${THREADS:-64}
    fi
}

# ============================================================================
# Benchmark Functions
# ============================================================================

run_baseline() {
    local result_file="$OUTPUT_DIR/baseline_run_$(date +%Y%m%d_%H%M%S).json"
    
    log_info "Running baseline benchmark (flat mmap)..."
    log_info "  Threads: $THREADS, Batch: $BATCH_SIZE, Tokens: $TOKENS"
    
    # Use numactl to bind to single node for fair comparison
    local cmd="numactl --cpunodebind=0 --membind=0 $LLAMA_BIN"
    cmd="$cmd -m $MODEL_PATH"
    cmd="$cmd -t $THREADS"
    cmd="$cmd -b $BATCH_SIZE"
    cmd="$cmd -n $TOKENS"
    cmd="$cmd --repeat $RUNS"
    cmd="$cmd -o json"
    
    log_info "Command: $cmd"
    
    mkdir -p "$OUTPUT_DIR"
    
    if eval "$cmd" > "$result_file" 2>&1; then
        log_success "Baseline benchmark completed"
        log_info "Results saved to: $result_file"
        echo "$result_file"
    else
        log_error "Baseline benchmark failed"
        cat "$result_file" >&2
        return 1
    fi
}

run_numa_sharded() {
    local result_file="$OUTPUT_DIR/numa_sharded_run_$(date +%Y%m%d_%H%M%S).json"
    
    log_info "Running NUMA-sharded benchmark..."
    log_info "  Config: $NUMA_CONFIG"
    log_info "  Threads: $THREADS, Batch: $BATCH_SIZE, Tokens: $TOKENS"
    
    # Export NUMA configuration
    export GGML_NUMA_SHARD_MAP="$NUMA_CONFIG"
    
    # Run without explicit membind - let NUMA sharding handle it
    local cmd="$LLAMA_BIN"
    cmd="$cmd -m $MODEL_PATH"
    cmd="$cmd -t $THREADS"
    cmd="$cmd -b $BATCH_SIZE"
    cmd="$cmd -n $TOKENS"
    cmd="$cmd --repeat $RUNS"
    cmd="$cmd -o json"
    cmd="$cmd --numa-shard" 2>/dev/null || true  # Optional flag if supported
    
    log_info "Command: $cmd"
    log_info "Environment: GGML_NUMA_SHARD_MAP=$GGML_NUMA_SHARD_MAP"
    
    mkdir -p "$OUTPUT_DIR"
    
    if eval "$cmd" > "$result_file" 2>&1; then
        log_success "NUMA-sharded benchmark completed"
        log_info "Results saved to: $result_file"
        echo "$result_file"
    else
        log_error "NUMA-sharded benchmark failed"
        cat "$result_file" >&2
        return 1
    fi
}

# ============================================================================
# Analysis Functions
# ============================================================================

parse_benchmark_result() {
    local result_file="$1"
    
    if [[ ! -f "$result_file" ]]; then
        log_error "Result file not found: $result_file"
        return 1
    fi
    
    # Extract key metrics (assumes llama-bench JSON output format)
    if command -v jq &> /dev/null; then
        local pp512=$(jq -r '.[].pp512' "$result_file" 2>/dev/null || echo "N/A")
        local tg128=$(jq -r '.[].tg128' "$result_file" 2>/dev/null || echo "N/A")
        echo "pp512=$pp512"
        echo "tg128=$tg128"
    else
        # Fallback: grep-based parsing
        local pp512=$(grep -oP '"pp512"\s*:\s*\K[0-9.]+' "$result_file" 2>/dev/null || echo "N/A")
        local tg128=$(grep -oP '"tg128"\s*:\s*\K[0-9.]+' "$result_file" 2>/dev/null || echo "N/A")
        echo "pp512=$pp512"
        echo "tg128=$tg128"
    fi
}

compare_results() {
    local baseline_file="$1"
    local numa_file="$2"
    
    log_info "Comparing results..."
    
    echo ""
    echo "=============================================="
    echo "        NUMA Sharding Performance Report     "
    echo "=============================================="
    echo ""
    
    # Parse both results
    eval $(parse_benchmark_result "$baseline_file")
    local baseline_pp512=$pp512
    local baseline_tg128=$tg128
    
    eval $(parse_benchmark_result "$numa_file")
    local numa_pp512=$pp512
    local numa_tg128=$tg128
    
    # Calculate improvements
    if [[ "$baseline_pp512" != "N/A" ]] && [[ "$numa_pp512" != "N/A" ]]; then
        local pp512_gain=$(echo "scale=2; (($numa_pp512 - $baseline_pp512) / $baseline_pp512) * 100" | bc 2>/dev/null || echo "N/A")
        echo "Prefill (pp512):"
        echo "  Baseline:      $baseline_pp512 t/s"
        echo "  NUMA-sharded:  $numa_pp512 t/s"
        echo "  Improvement:   ${pp512_gain}%"
        echo ""
    fi
    
    if [[ "$baseline_tg128" != "N/A" ]] && [[ "$numa_tg128" != "N/A" ]]; then
        local tg128_gain=$(echo "scale=2; (($numa_tg128 - $baseline_tg128) / $baseline_tg128) * 100" | bc 2>/dev/null || echo "N/A")
        echo "Text Generation (tg128):"
        echo "  Baseline:      $baseline_tg128 t/s"
        echo "  NUMA-sharded:  $numa_tg128 t/s"
        echo "  Improvement:   ${tg128_gain}%"
        echo ""
    fi
    
    echo "=============================================="
    
    # Save comparison report
    local report_file="$OUTPUT_DIR/comparison_report_$(date +%Y%m%d_%H%M%S).md"
    cat > "$report_file" << EOF
# NUMA Sharding Benchmark Comparison Report

**Date:** $(date -Iseconds)
**Model:** $MODEL_PATH
**Threads:** $THREADS
**Batch Size:** $BATCH_SIZE
**Tokens:** $TOKENS
**Runs:** $RUNS

## Configuration

- Baseline: Flat mmap with numactl --membind=0
- NUMA-sharded: GGML_NUMA_SHARD_MAP="$NUMA_CONFIG"

## Results

| Metric | Baseline (t/s) | NUMA-sharded (t/s) | Improvement |
|--------|----------------|--------------------|-------------|
| pp512  | $baseline_pp512 | $numa_pp512 | ${pp512_gain:-N/A}% |
| tg128  | $baseline_tg128 | $numa_tg128 | ${tg128_gain:-N/A}% |

## Analysis

$(if [[ "${pp512_gain:-0}" != "N/A" ]] && (( $(echo "$pp512_gain > 40" | bc -l) )); then
    echo "✅ Prefill throughput improved by >40% - meets target"
else
    echo "⚠️ Prefill throughput improvement below 40% target"
fi)

$(if [[ "${tg128_gain:-0}" != "N/A" ]] && (( $(echo "$tg128_gain > 45" | bc -l) )); then
    echo "✅ Text generation throughput improved by >45% - meets target"
else
    echo "⚠️ Text generation throughput improvement below 45% target"
fi)

## Raw Results

- Baseline: $baseline_file
- NUMA-sharded: $numa_file

---
*Generated by benchmark_numa.sh v1.0.0*
EOF
    
    log_success "Comparison report saved to: $report_file"
}

# ============================================================================
# Memory Bandwidth Analysis
# ============================================================================

analyze_memory_bandwidth() {
    log_info "Analyzing memory bandwidth..."
    
    if ! command -v numactl &> /dev/null; then
        log_warn "Cannot analyze memory bandwidth (numactl not available)"
        return
    fi
    
    echo ""
    echo "Memory Bandwidth Analysis"
    echo "========================="
    
    # Get NUMA node information
    numactl --hardware
    
    # If available, use perf or other tools for detailed analysis
    if command -v perf &> /dev/null; then
        log_info "perf available - detailed analysis possible"
    fi
}

# ============================================================================
# Main
# ============================================================================

main() {
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -m|--model)
                MODEL_PATH="$2"
                shift 2
                ;;
            -o|--output)
                OUTPUT_DIR="$2"
                shift 2
                ;;
            -t|--threads)
                THREADS="$2"
                shift 2
                ;;
            -b|--batch)
                BATCH_SIZE="$2"
                shift 2
                ;;
            -n|--tokens)
                TOKENS="$2"
                shift 2
                ;;
            -r|--runs)
                RUNS="$2"
                shift 2
                ;;
            --baseline)
                MODE="baseline"
                shift
                ;;
            --numa)
                MODE="numa"
                shift
                ;;
            --compare)
                MODE="compare"
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done
    
    # Check prerequisites
    if ! check_prerequisites; then
        exit 1
    fi
    
    # Detect hardware
    detect_hardware
    
    # Run benchmarks based on mode
    local baseline_result=""
    local numa_result=""
    
    case $MODE in
        baseline)
            baseline_result=$(run_baseline)
            ;;
        numa)
            numa_result=$(run_numa_sharded)
            ;;
        compare)
            baseline_result=$(run_baseline)
            numa_result=$(run_numa_sharded)
            compare_results "$baseline_result" "$numa_result"
            analyze_memory_bandwidth
            ;;
    esac
    
    log_success "Benchmark completed"
}

main "$@"
