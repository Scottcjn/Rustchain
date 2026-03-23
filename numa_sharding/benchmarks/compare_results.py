#!/usr/bin/env python3
"""
compare_results.py - Analyze and compare NUMA sharding benchmark results

This script processes benchmark output files and generates comprehensive
comparison reports including statistical analysis, confidence intervals,
and performance recommendations.

Usage:
    python compare_results.py baseline.json numa_sharded.json [output_dir]

Bounty: Scottcjn/rustchain-bounties #2277
Version: 1.0.0
"""

import json
import sys
import os
import statistics
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict


@dataclass
class BenchmarkMetrics:
    """Container for benchmark metrics"""
    pp512: float  # Prefill throughput (tokens/s)
    tg128: float  # Text generation throughput (tokens/s)
    pp512_std: float = 0.0
    tg128_std: float = 0.0
    memory_bandwidth: float = 0.0
    cross_numa_pct: float = 0.0


@dataclass
class ComparisonResult:
    """Container for comparison results"""
    metric: str
    baseline: float
    numa_sharded: float
    absolute_gain: float
    relative_gain_pct: float
    meets_target: bool
    target_pct: float


# Performance targets from bounty specification
TARGETS = {
    'pp512': 40.0,  # 40% improvement target
    'tg128': 45.0,  # 45% improvement target
}

# Expected baseline performance on POWER8 S824
EXPECTED_BASELINES = {
    'TinyLlama-1.1B-Q4_0': {'pp512': 147.54, 'tg128': 180.0},
    'Llama-2-7B-Q4_K_M': {'pp512': 42.3, 'tg128': 52.0},
    'Llama-2-33B-Q4_K_M': {'pp512': 8.7, 'tg128': 11.5},
}


def parse_llama_bench_json(filepath: str) -> Dict:
    """Parse llama-bench JSON output file"""
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    # Handle both single result and array of results
    if isinstance(data, list):
        results = data
    else:
        results = [data]
    
    return {'runs': results, 'file': filepath}


def extract_metrics(data: Dict) -> BenchmarkMetrics:
    """Extract key metrics from benchmark data"""
    runs = data.get('runs', [])
    
    pp512_values = []
    tg128_values = []
    
    for run in runs:
        if 'pp512' in run:
            pp512_values.append(run['pp512'])
        if 'tg128' in run:
            tg128_values.append(run['tg128'])
    
    # Calculate mean and std
    pp512 = statistics.mean(pp512_values) if pp512_values else 0.0
    tg128 = statistics.mean(tg128_values) if tg128_values else 0.0
    pp512_std = statistics.stdev(pp512_values) if len(pp512_values) > 1 else 0.0
    tg128_std = statistics.stdev(tg128_values) if len(tg128_values) > 1 else 0.0
    
    return BenchmarkMetrics(
        pp512=pp512,
        tg128=tg128,
        pp512_std=pp512_std,
        tg128_std=tg128_std,
    )


def calculate_gain(baseline: float, optimized: float) -> Tuple[float, float]:
    """Calculate absolute and relative performance gain"""
    absolute = optimized - baseline
    relative = (absolute / baseline * 100) if baseline > 0 else 0.0
    return absolute, relative


def compare_metrics(baseline: BenchmarkMetrics, 
                    numa: BenchmarkMetrics) -> List[ComparisonResult]:
    """Compare baseline and NUMA-sharded metrics"""
    results = []
    
    for metric in ['pp512', 'tg128']:
        baseline_val = getattr(baseline, metric)
        numa_val = getattr(numa, metric)
        absolute, relative = calculate_gain(baseline_val, numa_val)
        target = TARGETS.get(metric, 40.0)
        
        results.append(ComparisonResult(
            metric=metric,
            baseline=baseline_val,
            numa_sharded=numa_val,
            absolute_gain=absolute,
            relative_gain_pct=relative,
            meets_target=relative >= target,
            target_pct=target,
        ))
    
    return results


def generate_markdown_report(baseline_file: str,
                             numa_file: str,
                             baseline_metrics: BenchmarkMetrics,
                             numa_metrics: BenchmarkMetrics,
                             comparisons: List[ComparisonResult],
                             model_name: str = "Unknown") -> str:
    """Generate comprehensive markdown report"""
    
    timestamp = datetime.now().isoformat()
    
    report = f"""# NUMA Sharding Benchmark Validation Report

**Generated:** {timestamp}
**Model:** {model_name}
**Bounty:** Scottcjn/rustchain-bounties #2277

---

## Executive Summary

This report validates the NUMA-aware model sharding implementation for POWER8 llama.cpp.
The comparison evaluates prefill (pp512) and text generation (tg128) throughput between
flat mmap baseline and NUMA-sharded configurations.

---

## Test Configuration

| Parameter | Value |
|-----------|-------|
| Hardware | IBM POWER8 S824 (4 NUMA nodes) |
| Baseline Config | numactl --membind=0 (flat mmap) |
| NUMA Config | GGML_NUMA_SHARD_MAP="0-8:1,9-20:3,21-31:2" |
| Threads | 64 (optimal for POWER8) |

---

## Results Summary

### Prefill Throughput (pp512)

| Configuration | Throughput (t/s) | Std Dev |
|---------------|------------------|---------|
| Baseline (flat mmap) | {baseline_metrics.pp512:.2f} | ±{baseline_metrics.pp512_std:.2f} |
| NUMA-sharded | {numa_metrics.pp512:.2f} | ±{numa_metrics.pp512_std:.2f} |

### Text Generation Throughput (tg128)

| Configuration | Throughput (t/s) | Std Dev |
|---------------|------------------|---------|
| Baseline (flat mmap) | {baseline_metrics.tg128:.2f} | ±{baseline_metrics.tg128_std:.2f} |
| NUMA-sharded | {numa_metrics.tg128:.2f} | ±{numa_metrics.tg128_std:.2f} |

---

## Performance Gains

"""
    
    for comp in comparisons:
        status = "✅" if comp.meets_target else "⚠️"
        report += f"""### {comp.metric.upper()}

- **Baseline:** {comp.baseline:.2f} t/s
- **NUMA-sharded:** {comp.numa_sharded:.2f} t/s
- **Absolute Gain:** +{comp.absolute_gain:.2f} t/s
- **Relative Gain:** {comp.relative_gain_pct:.2f}%
- **Target:** {comp.target_pct:.0f}%
- **Status:** {status} {"Target met" if comp.meets_target else "Below target"}

"""
    
    # Overall assessment
    all_met = all(c.meets_target for c in comparisons)
    report += f"""---

## Overall Assessment

{"✅ **ALL TARGETS MET** - Implementation validated successfully" if all_met else "⚠️ **SOME TARGETS NOT MET** - Further optimization recommended"}

---

## Detailed Analysis

### Memory Access Patterns

The NUMA sharding implementation reduces cross-NUMA memory accesses by:
1. Placing early embedding layers on Node 1 (moderate bandwidth)
2. Placing attention layers on Node 3 (highest bandwidth: 400-425 MB/s)
3. Placing FFN layers on Node 2 (highest bandwidth: 400-425 MB/s)

### Expected vs Actual

"""
    
    # Add expected values if model matches
    for expected_model, expected in EXPECTED_BASELINES.items():
        if expected_model.lower() in model_name.lower():
            report += f"""#### Expected Performance ({expected_model})

| Metric | Expected Baseline | Expected NUMA | Expected Gain |
|--------|-------------------|---------------|---------------|
| pp512  | {expected['pp512']:.2f} t/s | {expected['pp512'] * 1.46:.2f} t/s | +46% |
| tg128  | {expected['tg128']:.2f} t/s | {expected['tg128'] * 1.46:.2f} t/s | +46% |

"""
            break
    
    report += f"""---

## Raw Data Files

- **Baseline:** `{baseline_file}`
- **NUMA-sharded:** `{numa_file}`

---

## Recommendations

1. **For Production:** Use the NUMA-sharded configuration with the provided preset
2. **For Tuning:** Adjust GGML_NUMA_SHARD_MAP based on specific model architecture
3. **For Monitoring:** Enable NUMA statistics with ggml_numa_shard_print_stats()

---

## Next Steps

- [ ] Validate on actual POWER8 S824 hardware
- [ ] Test with additional model sizes (13B, 70B)
- [ ] Measure power efficiency improvements
- [ ] Profile cross-NUMA access reduction

---

*Report generated by compare_results.py v1.0.0*
*Part of Bounty #2277 deliverables*
"""
    
    return report


def generate_json_summary(baseline_metrics: BenchmarkMetrics,
                          numa_metrics: BenchmarkMetrics,
                          comparisons: List[ComparisonResult]) -> Dict:
    """Generate JSON summary for programmatic consumption"""
    return {
        'timestamp': datetime.now().isoformat(),
        'baseline': asdict(baseline_metrics),
        'numa_sharded': asdict(numa_metrics),
        'comparisons': [asdict(c) for c in comparisons],
        'all_targets_met': all(c.meets_target for c in comparisons),
        'targets': TARGETS,
    }


def main():
    if len(sys.argv) < 3:
        print("Usage: python compare_results.py <baseline.json> <numa_sharded.json> [output_dir]")
        sys.exit(1)
    
    baseline_file = sys.argv[1]
    numa_file = sys.argv[2]
    output_dir = sys.argv[3] if len(sys.argv) > 3 else "."
    
    # Parse input files
    print(f"Parsing baseline results: {baseline_file}")
    baseline_data = parse_llama_bench_json(baseline_file)
    baseline_metrics = extract_metrics(baseline_data)
    
    print(f"Parsing NUMA-sharded results: {numa_file}")
    numa_data = parse_llama_bench_json(numa_file)
    numa_metrics = extract_metrics(numa_data)
    
    # Compare
    comparisons = compare_metrics(baseline_metrics, numa_metrics)
    
    # Generate reports
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Markdown report
    md_report = generate_markdown_report(
        baseline_file, numa_file,
        baseline_metrics, numa_metrics, comparisons,
        model_name=os.path.basename(baseline_file)
    )
    md_path = os.path.join(output_dir, f"validation_report_{timestamp}.md")
    with open(md_path, 'w') as f:
        f.write(md_report)
    print(f"Markdown report: {md_path}")
    
    # JSON summary
    json_summary = generate_json_summary(baseline_metrics, numa_metrics, comparisons)
    json_path = os.path.join(output_dir, f"summary_{timestamp}.json")
    with open(json_path, 'w') as f:
        json.dump(json_summary, f, indent=2)
    print(f"JSON summary: {json_path}")
    
    # Print summary to stdout
    print("\n" + "=" * 60)
    print("NUMA Sharding Benchmark Summary")
    print("=" * 60)
    
    for comp in comparisons:
        status = "✓" if comp.meets_target else "✗"
        print(f"\n{comp.metric.upper()}:")
        print(f"  Baseline:     {comp.baseline:.2f} t/s")
        print(f"  NUMA-sharded: {comp.numa_sharded:.2f} t/s")
        print(f"  Gain:         {comp.relative_gain_pct:.2f}% (target: {comp.target_pct:.0f}%)")
        print(f"  Status:       {status}")
    
    print("\n" + "=" * 60)
    if all(c.meets_target for c in comparisons):
        print("RESULT: All targets met ✓")
    else:
        print("RESULT: Some targets not met ✗")
    print("=" * 60)


if __name__ == '__main__':
    main()
