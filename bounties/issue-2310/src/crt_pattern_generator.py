"""
CRT Pattern Generator - Deterministic Visual Patterns for CRT Attestation

Generates deterministic visual patterns optimized for CRT fingerprinting:
- Checkered patterns for geometry analysis
- Gradient sweeps for brightness nonlinearity
- Timing bars for refresh rate measurement
- Phosphor excitation patterns for decay analysis
"""

import numpy as np
from typing import Tuple, Optional
import hashlib
import time


class CRTPatternGenerator:
    """Generates deterministic visual patterns for CRT attestation"""
    
    # Standard CRT refresh rates
    REFRESH_RATES = {
        'NTSC': 60.0,
        'PAL_50': 50.0,
        'PAL_72': 72.0,
        'VESA_75': 75.0,
        'VESA_85': 85.0,
        'VESA_100': 100.0,
    }
    
    # Phosphor types with characteristic decay times (ms)
    PHOSPHOR_TYPES = {
        'P1': 0.250,    # Green, short persistence
        'P4': 0.080,    # White, TV tubes
        'P22': 0.033,   # Color TV (RGB)
        'P31': 0.020,   # Green, oscilloscopes
        'P43': 0.200,   # Yellow-green, long persistence
        'P45': 0.030,   # Blue, short persistence
    }
    
    def __init__(self, width: int = 1920, height: int = 1080, 
                 refresh_rate: float = 60.0, phosphor_type: str = 'P22'):
        """
        Initialize CRT pattern generator.
        
        Args:
            width: Output frame width in pixels
            height: Output frame height in pixels
            refresh_rate: Target refresh rate in Hz
            phosphor_type: Phosphor type for decay simulation
        """
        self.width = width
        self.height = height
        self.refresh_rate = refresh_rate
        self.phosphor_type = phosphor_type
        self.phosphor_decay = self.PHOSPHOR_TYPES.get(phosphor_type, 0.033)
        self.frame_duration = 1.0 / refresh_rate
        
        # Seed for deterministic generation
        self.seed = 42
        np.random.seed(self.seed)
    
    def generate_checkered_pattern(self, square_size: int = 100,
                                    contrast: float = 0.9) -> np.ndarray:
        """
        Generate a checkered pattern for geometry and convergence analysis.
        
        Args:
            square_size: Size of each square in pixels
            contrast: Contrast ratio between light and dark squares
            
        Returns:
            RGB frame as numpy array (uint8)
        """
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        for y in range(0, self.height, square_size):
            for x in range(0, self.width, square_size):
                # Determine if this square should be bright
                is_bright = ((x // square_size) + (y // square_size)) % 2 == 0
                
                if is_bright:
                    intensity = int(255 * contrast)
                    frame[y:y+square_size, x:x+square_size] = [intensity, intensity, intensity]
        
        return frame
    
    def generate_gradient_sweep(self, direction: str = 'horizontal',
                                 start: int = 0, end: int = 255) -> np.ndarray:
        """
        Generate a gradient sweep for brightness nonlinearity analysis.

        Args:
            direction: 'horizontal' or 'vertical'
            start: Starting intensity (0-255)
            end: Ending intensity (0-255)

        Returns:
            RGB frame as numpy array (uint8)
        """
        if direction == 'horizontal':
            gradient = np.linspace(start, end, self.width, dtype=np.uint8)
            frame = np.stack([gradient] * self.height, axis=0)
        else:  # vertical
            gradient = np.linspace(start, end, self.height, dtype=np.uint8)
            frame = np.stack([gradient] * self.width, axis=1)

        # Replicate across RGB channels
        frame = np.stack([frame, frame, frame], axis=2)

        return frame
    
    def generate_timing_bars(self, num_bars: int = 10,
                             bar_width: Optional[int] = None) -> np.ndarray:
        """
        Generate vertical timing bars for refresh rate and scanline analysis.
        
        Args:
            num_bars: Number of timing bars
            bar_width: Width of each bar (default: width / num_bars)
            
        Returns:
            RGB frame as numpy array (uint8)
        """
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        if bar_width is None:
            bar_width = self.width // num_bars
        
        for i in range(num_bars):
            x_start = i * bar_width
            x_end = x_start + bar_width // 2  # 50% duty cycle
            
            # Alternating colors for edge detection
            color = [255, 0, 0] if i % 2 == 0 else [0, 255, 0]
            frame[:, x_start:x_end] = color
        
        return frame
    
    def generate_phosphor_test_pattern(self, pattern_type: str = 'flash') -> np.ndarray:
        """
        Generate a pattern optimized for phosphor decay measurement.
        
        Args:
            pattern_type: 'flash', 'pulse', or 'zone'
            
        Returns:
            RGB frame as numpy array (uint8)
        """
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        if pattern_type == 'flash':
            # Full white flash for decay curve measurement
            frame[:, :] = [255, 255, 255]
            
        elif pattern_type == 'pulse':
            # Central pulse zone
            h_start, h_end = self.height // 4, 3 * self.height // 4
            w_start, w_end = self.width // 4, 3 * self.width // 4
            frame[h_start:h_end, w_start:w_end] = [255, 255, 255]
            
        elif pattern_type == 'zone':
            # Quadrant zones for spatial decay analysis
            h_mid, w_mid = self.height // 2, self.width // 2
            frame[:h_mid, :w_mid] = [255, 0, 0]      # Red quadrant
            frame[:h_mid, w_mid:] = [0, 255, 0]      # Green quadrant
            frame[h_mid:, :w_mid] = [0, 0, 255]      # Blue quadrant
            frame[h_mid:, w_mid:] = [255, 255, 255]  # White quadrant
        
        return frame
    
    def generate_composite_pattern(self) -> np.ndarray:
        """
        Generate a composite pattern combining multiple test elements.
        
        Returns:
            RGB frame as numpy array (uint8)
        """
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # Background: subtle checkerboard
        checkered = self.generate_checkered_pattern(square_size=200, contrast=0.3)
        frame = checkered
        
        # Center: gradient circle for geometry
        center_y, center_x = self.height // 2, self.width // 2
        radius = min(self.width, self.height) // 4
        
        for y in range(self.height):
            for x in range(self.width):
                dist = np.sqrt((x - center_x)**2 + (y - center_y)**2)
                if dist < radius:
                    intensity = int(255 * (1 - dist / radius))
                    frame[y, x] = [intensity, intensity, intensity]
        
        # Timing marks on edges (draw vertical first, then horizontal to overlap corners)
        frame[:, 0:10] = [255, 0, 0]      # Left red line
        frame[:, -10:] = [0, 255, 0]      # Right green line
        frame[0:10, :] = [255, 255, 255]  # Top white line
        frame[-10:, :] = [255, 255, 255]  # Bottom white line

        return frame
    
    def generate_sequence(self, duration_seconds: float = 5.0,
                          fps: int = 30) -> np.ndarray:
        """
        Generate a sequence of frames for dynamic analysis.
        
        Args:
            duration_seconds: Total sequence duration
            fps: Frames per second
            
        Returns:
            Sequence of frames as numpy array (N, H, W, 3)
        """
        num_frames = int(duration_seconds * fps)
        frames = []
        
        for i in range(num_frames):
            # Cycle through patterns
            pattern_idx = i % 5
            
            if pattern_idx == 0:
                frame = self.generate_checkered_pattern()
            elif pattern_idx == 1:
                frame = self.generate_gradient_sweep()
            elif pattern_idx == 2:
                frame = self.generate_timing_bars()
            elif pattern_idx == 3:
                frame = self.generate_phosphor_test_pattern('flash')
            else:
                frame = self.generate_composite_pattern()
            
            frames.append(frame)
        
        return np.array(frames, dtype=np.uint8)
    
    def compute_pattern_hash(self, frame: np.ndarray) -> str:
        """
        Compute a deterministic hash of a pattern frame.
        
        Args:
            frame: RGB frame as numpy array
            
        Returns:
            SHA-256 hash as hex string
        """
        # Normalize to ensure determinism
        normalized = frame.astype(np.uint8)
        
        # Compute hash
        hash_obj = hashlib.sha256(normalized.tobytes())
        return hash_obj.hexdigest()
    
    def generate_fingerprint_seed(self) -> str:
        """
        Generate a deterministic seed for fingerprint generation.
        
        Returns:
            Fingerprint seed string
        """
        seed_data = {
            'width': self.width,
            'height': self.height,
            'refresh_rate': self.refresh_rate,
            'phosphor_type': self.phosphor_type,
            'timestamp': int(time.time() // 60),  # 1-minute resolution
        }
        
        seed_str = '|'.join(f"{k}:{v}" for k, v in sorted(seed_data.items()))
        return hashlib.sha256(seed_str.encode()).hexdigest()[:16]
    
    def get_pattern_metadata(self) -> dict:
        """
        Get metadata describing the pattern configuration.
        
        Returns:
            Dictionary with pattern metadata
        """
        return {
            'width': self.width,
            'height': self.height,
            'refresh_rate': self.refresh_rate,
            'refresh_rate_hz': f"{self.refresh_rate}Hz",
            'phosphor_type': self.phosphor_type,
            'phosphor_decay_ms': self.phosphor_decay * 1000,
            'frame_duration_ms': self.frame_duration * 1000,
            'fingerprint_seed': self.generate_fingerprint_seed(),
        }


def generate_test_patterns(output_dir: str = '.') -> dict:
    """
    Generate all standard test patterns and save metadata.
    
    Args:
        output_dir: Directory to save patterns (not implemented, returns data)
        
    Returns:
        Dictionary with patterns and metadata
    """
    generator = CRTPatternGenerator()
    
    patterns = {
        'checkered': generator.generate_checkered_pattern(),
        'gradient_h': generator.generate_gradient_sweep('horizontal'),
        'gradient_v': generator.generate_gradient_sweep('vertical'),
        'timing_bars': generator.generate_timing_bars(),
        'phosphor_flash': generator.generate_phosphor_test_pattern('flash'),
        'phosphor_pulse': generator.generate_phosphor_test_pattern('pulse'),
        'phosphor_zone': generator.generate_phosphor_test_pattern('zone'),
        'composite': generator.generate_composite_pattern(),
    }
    
    metadata = generator.get_pattern_metadata()
    
    # Compute hashes for verification
    hashes = {name: generator.compute_pattern_hash(frame) 
              for name, frame in patterns.items()}
    
    return {
        'patterns': patterns,
        'metadata': metadata,
        'hashes': hashes,
    }


if __name__ == '__main__':
    import sys
    
    print("CRT Pattern Generator - Test Run")
    print("=" * 50)
    
    # Test with different configurations
    configs = [
        (640, 480, 60.0, 'P22'),
        (1024, 768, 72.0, 'P43'),
        (1920, 1080, 85.0, 'P22'),
    ]
    
    for width, height, refresh, phosphor in configs:
        print(f"\nConfiguration: {width}x{height} @ {refresh}Hz ({phosphor})")
        gen = CRTPatternGenerator(width, height, refresh, phosphor)
        meta = gen.get_pattern_metadata()
        print(f"  Phosphor decay: {meta['phosphor_decay_ms']:.2f}ms")
        print(f"  Frame duration: {meta['frame_duration_ms']:.2f}ms")
        print(f"  Fingerprint seed: {meta['fingerprint_seed']}")
        
        # Generate and hash a pattern
        pattern = gen.generate_checkered_pattern()
        pattern_hash = gen.compute_pattern_hash(pattern)
        print(f"  Checkered pattern hash: {pattern_hash[:32]}...")
    
    print("\n" + "=" * 50)
    print("Pattern generation test complete!")
