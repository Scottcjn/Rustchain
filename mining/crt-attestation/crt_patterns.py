#!/usr/bin/env python3
"""
CRT Test Pattern Generator

Generates deterministic visual patterns for CRT fingerprinting.
Patterns are designed to expose CRT-specific optical characteristics
that LCDs cannot replicate.

Bounty: rustchain-bounties#2310 (140 RTC)
"""

import hashlib
import math
from typing import List, Tuple

# ── Pattern Types ────────────────────────────────────────────────

PATTERN_CHECKERBOARD = "checkerboard"
PATTERN_GRADIENT = "gradient"
PATTERN_TIMING_BARS = "timing_bars"
PATTERN_PHOSPHOR_TEST = "phosphor_test"
PATTERN_SCANLINE_GRID = "scanline_grid"

ALL_PATTERNS = [
    PATTERN_CHECKERBOARD,
    PATTERN_GRADIENT,
    PATTERN_TIMING_BARS,
    PATTERN_PHOSPHOR_TEST,
    PATTERN_SCANLINE_GRID,
]


def generate_checkerboard(width: int, height: int, block_size: int = 8) -> List[List[int]]:
    """
    Alternating black/white blocks.
    
    CRT reveals:
    - Phosphor bleeding at edges (CRT-specific)
    - Convergence errors in color CRTs (RGB guns misaligned)
    - Moiré with shadow mask/aperture grille
    """
    grid = []
    for y in range(height):
        row = []
        for x in range(width):
            bx = x // block_size
            by = y // block_size
            val = 255 if (bx + by) % 2 == 0 else 0
            row.append(val)
        grid.append(row)
    return grid


def generate_gradient(width: int, height: int) -> List[List[int]]:
    """
    Horizontal gradient from black to white.
    
    CRT reveals:
    - Brightness nonlinearity (electron gun gamma curve)
    - Phosphor saturation at high brightness
    - Beam current limiting (right side dimmer on aging CRTs)
    """
    grid = []
    for y in range(height):
        row = [int(255 * x / max(1, width - 1)) for x in range(width)]
        grid.append(row)
    return grid


def generate_timing_bars(width: int, height: int, 
                          num_bars: int = 16) -> List[List[int]]:
    """
    Vertical bars with precise timing (alternating on/off at sub-pixel rate).
    
    CRT reveals:
    - Scanline timing accuracy
    - Horizontal retrace artifacts
    - Bandwidth limitations (high-frequency bars blur on CRT)
    """
    grid = []
    bar_width = max(1, width // num_bars)
    for y in range(height):
        row = []
        for x in range(width):
            bar_idx = x // bar_width
            val = 255 if bar_idx % 2 == 0 else 0
            row.append(val)
        grid.append(row)
    return grid


def generate_phosphor_test(width: int, height: int) -> List[List[int]]:
    """
    Flash pattern: full white for 1 frame, then black for N frames.
    The decay rate from white to black reveals phosphor type.
    
    P22 (green): ~1ms decay to 10%
    P43 (green): ~1ms 
    P31 (green): ~32μs (very fast)
    P4 (white):  ~60μs
    
    LCD: instant transition (0 decay)
    """
    # Top half: white (flash), bottom half: reference black
    grid = []
    mid = height // 2
    for y in range(height):
        if y < mid:
            row = [255] * width  # Flash zone
        else:
            row = [0] * width    # Reference black
        grid.append(row)
    return grid


def generate_scanline_grid(width: int, height: int) -> List[List[int]]:
    """
    Single-pixel horizontal lines separated by black.
    
    CRT reveals:
    - Real scanline structure (visible on low-res CRTs)
    - Vertical deflection linearity
    - Interlace artifacts on interlaced CRTs
    
    LCD: uniform — no scanline structure
    """
    grid = []
    for y in range(height):
        if y % 2 == 0:
            row = [255] * width
        else:
            row = [0] * width
        grid.append(row)
    return grid


def pattern_hash(pattern_name: str, width: int, height: int) -> str:
    """Deterministic hash for a pattern configuration."""
    data = f"{pattern_name}:{width}x{height}"
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def generate_pattern(name: str, width: int = 640, 
                      height: int = 480) -> List[List[int]]:
    """Generate a named test pattern."""
    generators = {
        PATTERN_CHECKERBOARD: generate_checkerboard,
        PATTERN_GRADIENT: generate_gradient,
        PATTERN_TIMING_BARS: generate_timing_bars,
        PATTERN_PHOSPHOR_TEST: generate_phosphor_test,
        PATTERN_SCANLINE_GRID: generate_scanline_grid,
    }
    gen = generators.get(name)
    if not gen:
        raise ValueError(f"Unknown pattern: {name}")
    return gen(width, height)


if __name__ == "__main__":
    for name in ALL_PATTERNS:
        h = pattern_hash(name, 640, 480)
        print(f"  {name:20s} → {h}")
