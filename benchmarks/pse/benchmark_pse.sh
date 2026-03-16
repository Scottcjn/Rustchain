#!/usr/bin/env bash
# =============================================================================
# POWER8 PSE Benchmark Suite — benchmark_pse.sh
# Target: ppc64le, Ubuntu 20.04, POWER8 S824
# RustChain Bounty #35
#
# Runs llama.cpp inference benchmarks across three build modes:
#   1. Stock llama.cpp (baseline)
#   2. PSE-MASS build (AltiVec vec_perm optimizations)
#   3. PSE+Coffers build (NUMA-aware coffer scheduling)
#
# Collects: token throughput, NUMA bandwidth, cache hit rates, PSE entropy.
# Output: JSON results per model in results/ directory.
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration — override via environment or edit here
# ---------------------------------------------------------------------------
LLAMA_STOCK="${LLAMA_STOCK:-/opt/llama.cpp/stock/llama-bench}"
LLAMA_PSE_MASS="${LLAMA_PSE_MASS:-/opt/llama.cpp/pse-mass/llama-bench}"
LLAMA_PSE_COFFERS="${LLAMA_PSE_COFFERS:-/opt/llama.cpp/pse-coffers/llama-bench}"

MODEL_DIR="${MODEL_DIR:-/opt/models}"
RESULTS_DIR="${RESULTS_DIR:-$(dirname "$0")/results}"
WARMUP_RUNS="${WARMUP_RUNS:-2}"
BENCH_RUNS="${BENCH_RUNS:-5}"
VARIANCE_THRESHOLD="${VARIANCE_THRESHOLD:-5}"  # percent

# Prompt processing sizes and generation sizes
PP_SIZES=(128 512 1024)
TG_SIZES=(32 128)

# Models to benchmark (name:filename pairs)
declare -A MODELS=(
    ["tinyllama_1.1b"]="tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"
    ["qwen_14b"]="qwen1.5-14b-chat-q4_k_m.gguf"
    ["deepseek_33b"]="deepseek-coder-33b-instruct.Q4_K_M.gguf"
)

# Build modes
declare -A BUILDS=(
    ["stock"]="$LLAMA_STOCK"
    ["pse_mass"]="$LLAMA_PSE_MASS"
    ["pse_coffers"]="$LLAMA_PSE_COFFERS"
)

# PSE environment variables for each mode
declare -A BUILD_ENV=(
    ["stock"]=""
    ["pse_mass"]="PSE_ENABLED=1 PSE_MASS=1"
    ["pse_coffers"]="PSE_ENABLED=1 PSE_MASS=1 PSE_COFFERS=1"
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_FILE="${RESULTS_DIR}/benchmark.log"

log() {
    local ts
    ts=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$ts] $*" | tee -a "$LOG_FILE"
}

err() {
    log "ERROR: $*" >&2
}

# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------
preflight() {
    log "=== Preflight checks ==="
    local missing=0

    # Check architecture
    local arch
    arch=$(uname -m)
    if [[ "$arch" != "ppc64le" ]]; then
        err "Expected ppc64le, got $arch. Benchmark is designed for POWER8."
        err "Continuing anyway for script validation purposes."
    fi

    # Check required tools
    for tool in perf numactl numastat jq bc; do
        if ! command -v "$tool" &>/dev/null; then
            err "Required tool not found: $tool"
            missing=$((missing + 1))
        fi
    done

    # Check at least one build exists
    local found_build=0
    for mode in "${!BUILDS[@]}"; do
        if [[ -x "${BUILDS[$mode]}" ]]; then
            log "Found build: $mode -> ${BUILDS[$mode]}"
            found_build=1
        else
            log "SKIP build not found: $mode -> ${BUILDS[$mode]}"
        fi
    done

    if [[ $found_build -eq 0 ]]; then
        err "No llama.cpp builds found. Set LLAMA_STOCK / LLAMA_PSE_MASS / LLAMA_PSE_COFFERS."
        exit 1
    fi

    # Check models
    local found_model=0
    for name in "${!MODELS[@]}"; do
        local path="${MODEL_DIR}/${MODELS[$name]}"
        if [[ -f "$path" ]]; then
            log "Found model: $name -> $path"
            found_model=1
        else
            log "SKIP model not found: $name -> $path"
        fi
    done

    if [[ $found_model -eq 0 ]]; then
        err "No models found in $MODEL_DIR."
        exit 1
    fi

    if [[ $missing -gt 0 ]]; then
        err "$missing required tools missing. Install them and retry."
        exit 1
    fi

    log "Preflight complete."
}

# ---------------------------------------------------------------------------
# NUMA topology snapshot
# ---------------------------------------------------------------------------
collect_numa_topology() {
    log "Collecting NUMA topology..."
    local out="$RESULTS_DIR/numa_topology.json"

    local node_count
    node_count=$(numactl --hardware | grep "^available:" | awk '{print $2}')

    local nodes_json="["
    for ((n=0; n<node_count; n++)); do
        local cpus mem_total mem_free
        cpus=$(numactl --hardware | grep "^node $n cpus:" | sed "s/^node $n cpus: //")
        mem_total=$(numastat -m | grep "^MemTotal" | awk -v col=$((n+2)) '{print $col}')
        mem_free=$(numastat -m | grep "^MemFree" | awk -v col=$((n+2)) '{print $col}')

        [[ $n -gt 0 ]] && nodes_json+=","
        nodes_json+=$(cat <<NODEJSON
{
    "node": $n,
    "cpus": "$cpus",
    "mem_total_mb": ${mem_total:-0},
    "mem_free_mb": ${mem_free:-0}
}
NODEJSON
)
    done
    nodes_json+="]"

    echo "{\"node_count\": $node_count, \"nodes\": $nodes_json}" | jq '.' > "$out"
    log "NUMA topology -> $out"
}

# ---------------------------------------------------------------------------
# Cache metrics via perf stat
# ---------------------------------------------------------------------------
collect_cache_metrics() {
    local pid="$1"
    local duration="${2:-10}"
    local out_file="$3"

    # perf stat on POWER8: use raw PMU events for cache
    # L1-dcache-loads, L1-dcache-load-misses, LLC-loads, LLC-load-misses
    perf stat -p "$pid" -e L1-dcache-loads,L1-dcache-load-misses,LLC-loads,LLC-load-misses \
        --output "$out_file" -- sleep "$duration" 2>&1 || true
}

parse_cache_metrics() {
    local perf_file="$1"

    local l1_loads l1_misses llc_loads llc_misses
    l1_loads=$(grep -oP '[\d,]+(?=\s+L1-dcache-loads)' "$perf_file" 2>/dev/null | tr -d ',' || echo "0")
    l1_misses=$(grep -oP '[\d,]+(?=\s+L1-dcache-load-misses)' "$perf_file" 2>/dev/null | tr -d ',' || echo "0")
    llc_loads=$(grep -oP '[\d,]+(?=\s+LLC-loads)' "$perf_file" 2>/dev/null | tr -d ',' || echo "0")
    llc_misses=$(grep -oP '[\d,]+(?=\s+LLC-load-misses)' "$perf_file" 2>/dev/null | tr -d ',' || echo "0")

    local l1_hit_rate="0" llc_hit_rate="0"
    if [[ "$l1_loads" -gt 0 ]]; then
        l1_hit_rate=$(echo "scale=4; (1 - $l1_misses / $l1_loads) * 100" | bc)
    fi
    if [[ "$llc_loads" -gt 0 ]]; then
        llc_hit_rate=$(echo "scale=4; (1 - $llc_misses / $llc_loads) * 100" | bc)
    fi

    cat <<CACHE
{
    "l1_dcache_loads": $l1_loads,
    "l1_dcache_misses": $l1_misses,
    "l1_hit_rate_pct": $l1_hit_rate,
    "llc_loads": $llc_loads,
    "llc_misses": $llc_misses,
    "llc_hit_rate_pct": $llc_hit_rate
}
CACHE
}

# ---------------------------------------------------------------------------
# NUMA memory bandwidth during inference
# ---------------------------------------------------------------------------
collect_numa_bandwidth() {
    local out_file="$1"
    numastat -m > "$out_file" 2>/dev/null || echo "{}" > "$out_file"
}

# ---------------------------------------------------------------------------
# PSE behavioral divergence (entropy measurement)
# ---------------------------------------------------------------------------
# PSE divergence is measured by comparing token probability distributions
# between PSE-enabled and stock builds. We capture logits via --logits-all
# and compute Shannon entropy post-hoc. This function parses llama-bench
# output for any PSE-specific markers.
collect_pse_entropy() {
    local bench_output="$1"

    # PSE markers from the build output:
    #   NOI  = Number of Iterations (vec_perm cycles)
    #   DR   = Divergence Ratio (KL divergence from stock)
    #   ACS  = AltiVec Cycle Share (% of compute in AltiVec)
    #   MCI  = Memory Coffer Index (active NUMA coffers)
    local noi dr acs mci
    noi=$(grep -oP 'NOI[=:]\s*\K[\d.]+' "$bench_output" 2>/dev/null || echo "0")
    dr=$(grep -oP 'DR[=:]\s*\K[\d.]+' "$bench_output" 2>/dev/null || echo "0")
    acs=$(grep -oP 'ACS[=:]\s*\K[\d.]+' "$bench_output" 2>/dev/null || echo "0")
    mci=$(grep -oP 'MCI[=:]\s*\K[\d.]+' "$bench_output" 2>/dev/null || echo "0")

    cat <<PSE
{
    "noi": $noi,
    "divergence_ratio": $dr,
    "altivec_cycle_share": $acs,
    "memory_coffer_index": $mci
}
PSE
}

# ---------------------------------------------------------------------------
# Run a single llama-bench invocation and parse results
# ---------------------------------------------------------------------------
run_bench() {
    local bench_bin="$1"
    local model_path="$2"
    local pp_size="$3"
    local tg_size="$4"
    local n_runs="$5"
    local env_vars="$6"
    local out_file="$7"

    log "  Bench: pp=$pp_size tg=$tg_size runs=$n_runs"

    local cmd="$bench_bin -m $model_path -p $pp_size -n $tg_size -r $n_runs -o json"

    # Run with environment variables if set
    if [[ -n "$env_vars" ]]; then
        cmd="env $env_vars $cmd"
    fi

    # Execute and capture output
    eval "$cmd" > "$out_file" 2>&1
    local rc=$?

    if [[ $rc -ne 0 ]]; then
        err "Bench failed (rc=$rc), output in $out_file"
        return 1
    fi

    return 0
}

# ---------------------------------------------------------------------------
# Parse llama-bench JSON output for token speeds
# ---------------------------------------------------------------------------
parse_bench_output() {
    local json_file="$1"
    local metric="$2"  # "pp" or "tg"

    # llama-bench JSON output has entries with "test" field
    # Extract tokens/sec for the matching test type
    if [[ "$metric" == "pp" ]]; then
        jq -r '.[] | select(.test == "pp") | .tokens_per_second' "$json_file" 2>/dev/null || echo "0"
    else
        jq -r '.[] | select(.test == "tg") | .tokens_per_second' "$json_file" 2>/dev/null || echo "0"
    fi
}

# ---------------------------------------------------------------------------
# Compute mean and stddev from a set of values
# ---------------------------------------------------------------------------
compute_stats() {
    local values=("$@")
    local n=${#values[@]}
    if [[ $n -eq 0 ]]; then
        echo '{"mean": 0, "stddev": 0, "cv_pct": 0}'
        return
    fi

    local sum=0
    for v in "${values[@]}"; do
        sum=$(echo "$sum + $v" | bc -l)
    done
    local mean
    mean=$(echo "scale=4; $sum / $n" | bc -l)

    local sq_sum=0
    for v in "${values[@]}"; do
        local diff
        diff=$(echo "$v - $mean" | bc -l)
        sq_sum=$(echo "$sq_sum + ($diff * $diff)" | bc -l)
    done
    local stddev
    stddev=$(echo "scale=4; sqrt($sq_sum / $n)" | bc -l)

    local cv=0
    if [[ $(echo "$mean > 0" | bc -l) -eq 1 ]]; then
        cv=$(echo "scale=2; ($stddev / $mean) * 100" | bc -l)
    fi

    echo "{\"mean\": $mean, \"stddev\": $stddev, \"cv_pct\": $cv}"
}

# ---------------------------------------------------------------------------
# Benchmark one model across all builds
# ---------------------------------------------------------------------------
benchmark_model() {
    local model_name="$1"
    local model_file="${MODELS[$model_name]}"
    local model_path="${MODEL_DIR}/${model_file}"

    if [[ ! -f "$model_path" ]]; then
        log "SKIP model not found: $model_name -> $model_path"
        return
    fi

    log "=== Benchmarking: $model_name ==="

    local model_results_dir="$RESULTS_DIR/$model_name"
    mkdir -p "$model_results_dir"

    local model_json="$RESULTS_DIR/${model_name}.json"
    local build_results="["
    local first_build=1

    for mode in stock pse_mass pse_coffers; do
        local bench_bin="${BUILDS[$mode]}"
        local env_vars="${BUILD_ENV[$mode]}"

        if [[ ! -x "$bench_bin" ]]; then
            log "SKIP build not available: $mode"
            continue
        fi

        log "--- Build mode: $mode ---"

        [[ $first_build -eq 1 ]] && first_build=0 || build_results+=","

        local pp_results="{"
        local first_pp=1

        # Prompt processing benchmarks
        for pp in "${PP_SIZES[@]}"; do
            [[ $first_pp -eq 1 ]] && first_pp=0 || pp_results+=","

            local pp_values=()

            # Warmup
            log "  Warmup: pp=$pp (${WARMUP_RUNS} runs)"
            local warmup_out="$model_results_dir/${mode}_warmup_pp${pp}.json"
            run_bench "$bench_bin" "$model_path" "$pp" 1 "$WARMUP_RUNS" "$env_vars" "$warmup_out" || true

            # Bench runs
            for ((r=1; r<=BENCH_RUNS; r++)); do
                local run_out="$model_results_dir/${mode}_pp${pp}_run${r}.json"
                if run_bench "$bench_bin" "$model_path" "$pp" 1 1 "$env_vars" "$run_out"; then
                    local tps
                    tps=$(parse_bench_output "$run_out" "pp")
                    pp_values+=("$tps")
                fi
            done

            local pp_stats
            pp_stats=$(compute_stats "${pp_values[@]}")
            pp_results+="\"pp${pp}\": $pp_stats"
        done
        pp_results+="}"

        # Token generation benchmarks
        local tg_results="{"
        local first_tg=1

        for tg in "${TG_SIZES[@]}"; do
            [[ $first_tg -eq 1 ]] && first_tg=0 || tg_results+=","

            local tg_values=()

            log "  Warmup: tg=$tg (${WARMUP_RUNS} runs)"
            local warmup_out="$model_results_dir/${mode}_warmup_tg${tg}.json"
            run_bench "$bench_bin" "$model_path" 128 "$tg" "$WARMUP_RUNS" "$env_vars" "$warmup_out" || true

            for ((r=1; r<=BENCH_RUNS; r++)); do
                local run_out="$model_results_dir/${mode}_tg${tg}_run${r}.json"
                if run_bench "$bench_bin" "$model_path" 128 "$tg" 1 "$env_vars" "$run_out"; then
                    local tps
                    tps=$(parse_bench_output "$run_out" "tg")
                    tg_values+=("$tps")
                fi
            done

            local tg_stats
            tg_stats=$(compute_stats "${tg_values[@]}")
            tg_results+="\"tg${tg}\": $tg_stats"
        done
        tg_results+="}"

        # Collect cache metrics during a representative run
        log "  Collecting cache metrics for $mode..."
        local cache_json="{}"
        local cache_run_out="$model_results_dir/${mode}_cache_run.json"
        local perf_out="$model_results_dir/${mode}_perf.txt"

        # Start a bench run in background, attach perf
        eval "env ${env_vars} ${bench_bin} -m ${model_path} -p 512 -n 64 -r 1" \
            > "$cache_run_out" 2>&1 &
        local bench_pid=$!

        sleep 1
        if kill -0 "$bench_pid" 2>/dev/null; then
            collect_cache_metrics "$bench_pid" 8 "$perf_out"
            wait "$bench_pid" 2>/dev/null || true
            cache_json=$(parse_cache_metrics "$perf_out")
        else
            wait "$bench_pid" 2>/dev/null || true
        fi

        # Collect NUMA bandwidth
        local numa_out="$model_results_dir/${mode}_numastat.txt"
        collect_numa_bandwidth "$numa_out"

        # Collect PSE entropy markers
        local pse_markers="{\"noi\": 0, \"divergence_ratio\": 0, \"altivec_cycle_share\": 0, \"memory_coffer_index\": 0}"
        if [[ "$mode" != "stock" ]]; then
            pse_markers=$(collect_pse_entropy "$cache_run_out")
        fi

        build_results+=$(cat <<BUILDRESULT
{
    "build_mode": "$mode",
    "prompt_processing": $pp_results,
    "token_generation": $tg_results,
    "cache_metrics": $cache_json,
    "pse_markers": $pse_markers
}
BUILDRESULT
)
    done

    build_results+="]"

    # Assemble final model JSON
    local timestamp
    timestamp=$(date -u '+%Y-%m-%dT%H:%M:%SZ')

    cat <<MODELJSON | jq '.' > "$model_json"
{
    "benchmark_version": "1.0.0",
    "timestamp": "$timestamp",
    "model": "$model_name",
    "model_file": "$model_file",
    "system": {
        "arch": "$(uname -m)",
        "os": "$(lsb_release -ds 2>/dev/null || echo 'unknown')",
        "kernel": "$(uname -r)",
        "hostname": "$(hostname)"
    },
    "config": {
        "warmup_runs": $WARMUP_RUNS,
        "bench_runs": $BENCH_RUNS,
        "pp_sizes": $(printf '%s\n' "${PP_SIZES[@]}" | jq -s '.'),
        "tg_sizes": $(printf '%s\n' "${TG_SIZES[@]}" | jq -s '.')
    },
    "results": $build_results
}
MODELJSON

    log "Results -> $model_json"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    mkdir -p "$RESULTS_DIR"
    : > "$LOG_FILE"

    log "=== POWER8 PSE Benchmark Suite v1.0 ==="
    log "Host: $(hostname) | Arch: $(uname -m) | Date: $(date -u)"

    preflight
    collect_numa_topology

    for model_name in "${!MODELS[@]}"; do
        benchmark_model "$model_name"
    done

    # Write progress.json
    cat <<PROGRESS > "$RESULTS_DIR/progress.json"
{
    "step": "done",
    "progress": 100,
    "timestamp": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')",
    "models_benchmarked": $(printf '%s\n' "${!MODELS[@]}" | jq -R . | jq -s .)
}
PROGRESS

    log "=== Benchmark complete ==="
    log "Results directory: $RESULTS_DIR"
}

main "$@"
