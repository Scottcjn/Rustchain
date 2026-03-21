"""
CRT Pattern Generators - Deterministic visual patterns for CRT attestation.

Generates checkered patterns, gradient sweeps, timing bars, and other
deterministic patterns designed to expose CRT-specific characteristics
like phosphor decay, scanline timing, and brightness nonlinearity.
"""

import numpy as np
from typing import Tuple, Optional, List
import hashlib
import json


class CRTPatternGenerator:
    """
    Generates deterministic visual patterns for CRT optical fingerprinting.
    
    Each pattern is designed to reveal specific CRT characteristics:
    - Checkered: Phosphor cross-talk and pixel coupling
    - Gradient sweep: Brightness nonlinearity across the screen
    - Timing bars: Vertical sync and scanline timing
    - Phosphor burst: Exponential decay measurement
    """
    
    # Standard CRT refresh rates
    REFRESH_RATES = [60, 72, 75, 85, 100]
    # Phosphor types and their decay characteristics
    PHOSPHOR_TYPES = {
        "P22": {"decay_time": 0.3, "color": "green", "spectrum": "peak at 545nm"},
        "P43": {"decay_time": 1.0, "color": "green-yellow", "spectrum": "peak at 543nm"},
        "P1": {"decay_time": 0.025, "color": "blue", "spectrum": "peak at 365nm"},
        "P11": {"decay_time": 0.001, "color": "blue", "spectrum": "peak at 460nm"},
        "P24": {"decay_time": 0.0004, "color": "green", "spectrum": "fast decay"},
    }
    
    def __init__(self, width: int = 1920, height: int = 1080, seed: Optional[int] = None):
        """
        Initialize pattern generator.
        
        Args:
            width: Screen width in pixels
            height: Screen height in pixels  
            seed: Random seed for deterministic pattern generation
        """
        self.width = width
        self.height = height
        self.seed = seed or 42
        self._rng = np.random.RandomState(self.seed)
        
    def _deterministic_hash(self, pattern_name: str, frame: int) -> str:
        """Generate deterministic hash for pattern + frame combination."""
        data = f"{pattern_name}:{frame}:{self.seed}:{self.width}x{self.height}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def checkered_pattern(self, square_size: int = 8, brightness: Tuple[int, int] = (255, 0)) -> np.ndarray:
        """
        Generate checkered pattern - exposes phosphor cross-talk and pixel coupling.
        
        Args:
            square_size: Size of each checkered square in pixels
            brightness: (high, low) brightness values as RGB
            
        Returns:
            numpy array (height, width, 3) of uint8 values
        """
        high, low = brightness
        pattern = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        for y in range(self.height):
            for x in range(self.width):
                checker = ((y // square_size) + (x // square_size)) % 2
                val = high if checker else low
                pattern[y, x] = [val, val, val]
        
        return pattern
    
    def gradient_sweep_pattern(self, direction: str = "horizontal") -> np.ndarray:
        """
        Generate gradient sweep - exposes brightness nonlinearity and gamma.
        
        Args:
            direction: 'horizontal', 'vertical', or 'radial'
            
        Returns:
            numpy array (height, width, 3) of uint8 values
        """
        pattern = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        if direction == "horizontal":
            gradient = np.linspace(0, 255, self.width, dtype=np.uint8)
            pattern = np.tile(gradient, (self.height, 1, 1))
            # Add subtle deterministic variation
            for y in range(self.height):
                variation = (self._rng.random() * 4 - 2).astype(np.int16)
                pattern[y] = np.clip(pattern[y].astype(np.int16) + variation, 0, 255).astype(np.uint8)
                
        elif direction == "vertical":
            gradient = np.linspace(0, 255, self.height, dtype=np.uint8)
            pattern = np.transpose(np.tile(gradient, (self.width, 1)), axes=(1, 0, 2))
            
        elif direction == "radial":
            cx, cy = self.width // 2, self.height // 2
            y_coords, x_coords = np.ogrid[:self.height, :self.width]
            dist = np.sqrt((x_coords - cx)**2 + (y_coords - cy)**2)
            dist_max = np.sqrt(cx**2 + cy**2)
            gradient = (dist / dist_max * 255).astype(np.uint8)
            pattern[:, :, 0] = gradient
            pattern[:, :, 1] = gradient
            pattern[:, :, 2] = gradient
            
        return pattern
    
    def timing_bars_pattern(self, num_bars: int = 8, flash_frames: int = 4) -> List[np.ndarray]:
        """
        Generate timing bars pattern - exposes vertical sync and flyback timing.
        
        Each frame shows a different vertical bar configuration to measure
        scanline timing jitter and refresh rate accuracy.
        
        Args:
            num_bars: Number of vertical bars
            flash_frames: Number of frames per bar configuration
            
        Returns:
            List of numpy arrays, one per frame
        """
        frames = []
        bar_width = self.width // num_bars
        
        for frame in range(flash_frames * num_bars):
            pattern = np.zeros((self.height, self.width, 3), dtype=np.uint8)
            bar_idx = frame % num_bars
            
            # Deterministic bar brightness based on frame
            brightness = int(255 * (frame / (flash_frames * num_bars)))
            
            # Draw single bright bar at current position
            x_start = bar_idx * bar_width
            x_end = x_start + bar_width
            pattern[:, x_start:x_end] = [brightness, brightness, brightness]
            
            frames.append(pattern)
            
        return frames
    
    def phosphor_burst_pattern(self, burst_length: int = 16) -> List[np.ndarray]:
        """
        Generate phosphor burst pattern - measures phosphor decay curve.
        
        Displays a bright flash then captures the exponential decay,
        characteristic of the phosphor type (P22, P43, etc.)
        
        Args:
            burst_length: Number of frames to record after flash
            
        Returns:
            List of numpy arrays showing decay
        """
        frames = []
        
        for frame in range(burst_length):
            pattern = np.zeros((self.height, self.width, 3), dtype=np.uint8)
            
            if frame == 0:
                # Initial burst - full white
                pattern[:, :] = [255, 255, 255]
            else:
                # Exponential decay - deterministic based on phosphor type
                decay_rate = 0.15  # Typical for P43 phosphor
                intensity = 255 * np.exp(-decay_rate * frame)
                
                # Add deterministic noise based on frame
                noise = int(self._rng.random() * 4 - 2)
                intensity = max(0, min(255, int(intensity) + noise))
                
                pattern[:, :] = [intensity, intensity, intensity]
                
            frames.append(pattern)
            
        return frames
    
    def scanline_pattern(self, line_spacing: int = 2, brightness: int = 255) -> np.ndarray:
        """
        Generate scanline pattern - exposes scanline timing jitter.
        
        Args:
            line_spacing: Gap between bright scanlines
            brightness: Brightness of scanlines
            
        Returns:
            numpy array (height, width, 3)
        """
        pattern = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        for y in range(0, self.height, line_spacing):
            pattern[y, :] = [brightness, brightness, brightness]
            
        return pattern
    
    def rgb_separated_pattern(self) -> np.ndarray:
        """
        Generate RGB separated pattern - exposes color channel timing differences.
        
        Each color channel is shifted slightly to expose channel delay.
        
        Returns:
            numpy array (height, width, 3)
        """
        pattern = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # Red channel - full frame
        pattern[:, :, 0] = 255
        
        # Green channel - shifted right by 2 pixels
        pattern[:, 2:, 1] = 255
        
        # Blue channel - shifted right by 4 pixels  
        pattern[:, 4:, 2] = 255
        
        return pattern
    
    def single_pixel_flash_pattern(self, positions: Optional[List[Tuple[int, int]]] = None) -> np.ndarray:
        """
        Generate single pixel flash pattern - for precise timing measurement.
        
        Args:
            positions: List of (x, y) pixel positions to flash, or None for deterministic
            
        Returns:
            numpy array (height, width, 3)
        """
        pattern = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        if positions is None:
            # Deterministic positions based on seed
            positions = [
                (self.width // 4, self.height // 4),
                (self.width // 2, self.height // 2),
                (3 * self.width // 4, self.height // 4),
                (self.width // 2, 3 * self.height // 4),
            ]
            
        # Add positions to pattern
        hash_val = self._deterministic_hash("single_pixel", 0)
        active_pos = positions[int(hash_val[:2], 16) % len(positions)]
        
        x, y = active_pos
        if 0 <= x < self.width and 0 <= y < self.height:
            pattern[y, x] = [255, 255, 255]
            
        return pattern
    
    def full_brightness_pulse(self, pulse_frames: int = 2) -> List[np.ndarray]:
        """
        Generate full brightness pulse - for overall timing and brightness measurement.
        
        Args:
            pulse_frames: Number of frames for pulse cycle
            
        Returns:
            List of frames (black, white, black pattern)
        """
        frames = []
        
        for frame in range(pulse_frames * 2):
            if frame % 2 == 0:
                # White frame
                pattern = np.full((self.height, self.width, 3), 255, dtype=np.uint8)
            else:
                # Black frame
                pattern = np.zeros((self.height, self.width, 3), dtype=np.uint8)
            frames.append(pattern)
            
        return frames
    
    def generate_attestation_pattern(self, seed: Optional[int] = None) -> Tuple[np.ndarray, dict]:
        """
        Generate the primary attestation pattern combining multiple tests.
        
        This is the main pattern used for CRT fingerprinting, combining:
        - Edge regions for sharpness measurement
        - Center gradient for gamma
        - Corner markers for geometry
        - Phosphor test regions
        
        Args:
            seed: Optional seed override
            
        Returns:
            Tuple of (pattern_array, metadata_dict)
        """
        if seed is not None:
            self._rng = np.random.RandomState(seed)
            
        pattern = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # Top region - horizontal gradient (gamma test)
        gradient_height = self.height // 4
        gradient = np.linspace(0, 255, self.width, dtype=np.uint8)
        for y in range(gradient_height):
            variation = int(self._rng.random() * 4 - 2)
            brightness = np.clip(gradient + variation, 0, 255).astype(np.uint8)
            pattern[y, :] = np.stack([brightness, brightness, brightness], axis=1)
        
        # Middle region - checkered (phosphor cross-talk)
        checker_height = self.height // 2
        checker_top = gradient_height
        square_size = 16
        
        for y in range(checker_top, checker_top + checker_height):
            for x in range(self.width):
                checker = ((y // square_size) + (x // square_size)) % 2
                val = 255 if checker else 0
                # Add deterministic variation
                var = int(self._rng.random() * 2)
                val = min(255, val + var)
                pattern[y, x] = [val, val, val]
        
        # Bottom region - scanlines (timing test)
        scanline_top = checker_top + checker_height
        for y in range(scanline_top, self.height):
            if y % 3 == 0:
                pattern[y, :] = [200, 200, 200]
        
        # Corner markers - 4 corners for geometry check
        marker_size = 40
        corners = [
            (0, 0), (self.width - marker_size, 0),
            (0, self.height - marker_size), (self.width - marker_size, self.height - marker_size)
        ]
        for cx, cy in corners:
            pattern[cy:cy+marker_size, cx:cx+marker_size] = [255, 0, 0]  # Red markers
            
        # Metadata about the pattern
        hash_input = f"attestation:{self.seed}:{self.width}x{self.height}"
        pattern_hash = hashlib.sha256(hash_input.encode()).hexdigest()
        
        metadata = {
            "pattern_seed": self.seed,
            "dimensions": f"{self.width}x{self.height}",
            "pattern_hash": pattern_hash,
            "generation_params": {
                "gradient_height": gradient_height,
                "checker_square_size": square_size,
                "scanline_spacing": 3,
                "marker_size": marker_size
            }
        }
        
        return pattern, metadata
    
    def get_pattern_hash(self, pattern_name: str, frame: int = 0) -> str:
        """
        Get deterministic hash for a pattern type.
        
        Args:
            pattern_name: Name of the pattern method
            frame: Frame number for animated patterns
            
        Returns:
            16-character hex hash
        """
        return self._deterministic_hash(pattern_name, frame)
    
    def get_phosphor_info(self, phosphor_type: str) -> dict:
        """Get information about a phosphor type."""
        return self.PHOSPHOR_TYPES.get(phosphor_type, {})
    
    def list_patterns(self) -> List[str]:
        """List all available pattern generators."""
        return [
            "checkered_pattern",
            "gradient_sweep_pattern", 
            "timing_bars_pattern",
            "phosphor_burst_pattern",
            "scanline_pattern",
            "rgb_separated_pattern",
            "single_pixel_flash_pattern",
            "full_brightness_pulse",
            "generate_attestation_pattern",
        ]


def create_pattern_generator(width: int = 1920, height: int = 1080, seed: int = 42) -> CRTPatternGenerator:
    """
    Factory function to create a CRT pattern generator.
    
    Args:
        width: Screen width
        height: Screen height
        seed: Random seed for deterministic generation
        
    Returns:
        CRTPatternGenerator instance
    """
    return CRTPatternGenerator(width=width, height=height, seed=seed)


if __name__ == "__main__":
    # Demo: generate and display patterns
    gen = CRTPatternGenerator(width=800, height=600, seed=42)
    
    print("CRT Pattern Generator - Demo")
    print(f"Screen size: {gen.width}x{gen.height}")
    print(f"Available patterns: {gen.list_patterns()}")
    
    # Generate attestation pattern
    pattern, metadata = gen.generate_attestation_pattern()
    print(f"\nAttestation pattern hash: {metadata['pattern_hash']}")
    print(f"Pattern shape: {pattern.shape}")
    
    # Generate phosphor burst frames
    burst_frames = gen.phosphor_burst_pattern(burst_length=8)
    print(f"\nPhosphor burst: {len(burst_frames)} frames")
    
    # Phosphor type info
    for ptype, info in gen.PHOSPHOR_TYPES.items():
        print(f"\n{ptype}: decay={info['decay_time']}s, color={info['color']}")
