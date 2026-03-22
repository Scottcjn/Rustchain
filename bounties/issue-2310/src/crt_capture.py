"""
CRT Capture Module - Optical Signal Acquisition

Captures CRT display output via:
- USB webcam (camera-based capture)
- Photodiode + ADC (GPIO-based capture for Raspberry Pi)

Provides synchronized capture with pattern display for accurate timing analysis.
"""

import numpy as np
from typing import Optional, Tuple, List, Dict, Any
import time
from dataclasses import dataclass
from enum import Enum
import json


class CaptureMethod(Enum):
    """Available capture methods"""
    WEBCAM = "webcam"
    PHOTODIODE = "photodiode"
    SIMULATED = "simulated"  # For testing without hardware


@dataclass
class CaptureConfig:
    """Configuration for CRT capture"""
    method: CaptureMethod = CaptureMethod.SIMULATED
    width: int = 640
    height: int = 480
    fps: int = 30
    exposure_ms: float = 10.0
    gain: float = 1.0
    device_index: int = 0
    gpio_pin: int = 18  # For photodiode
    adc_sample_rate: int = 10000  # Samples per second
    capture_duration_s: float = 5.0


@dataclass
class CapturedFrame:
    """Represents a captured frame with metadata"""
    data: np.ndarray
    timestamp: float
    frame_index: int
    exposure_ms: float
    gain: float


class CRTCapture:
    """
    CRT optical signal capture module.
    
    Supports multiple capture methods for flexibility:
    - Webcam: Easy setup, full frame capture
    - Photodiode: High temporal resolution, single point
    - Simulated: Testing without hardware
    """
    
    def __init__(self, config: Optional[CaptureConfig] = None):
        """
        Initialize CRT capture module.
        
        Args:
            config: Capture configuration (uses defaults if None)
        """
        self.config = config or CaptureConfig()
        self.is_capturing = False
        self.captured_frames: List[CapturedFrame] = []
        self.photodiode_samples: List[Tuple[float, float]] = []  # (timestamp, value)
        
        # Calibration data
        self.dark_frame: Optional[np.ndarray] = None
        self.flat_field: Optional[np.ndarray] = None
        
        # Timing synchronization
        self.sync_pulse_time: Optional[float] = None
        
    def calibrate_dark_frame(self, num_frames: int = 10) -> np.ndarray:
        """
        Capture dark frame for noise subtraction.
        
        Args:
            num_frames: Number of frames to average
            
        Returns:
            Average dark frame
        """
        if self.config.method == CaptureMethod.SIMULATED:
            # Simulate dark frame with sensor noise
            dark = np.random.normal(5, 2, 
                                   (self.config.height, self.config.width, 3))
            dark = np.clip(dark, 0, 255).astype(np.uint8)
            self.dark_frame = dark
            return dark
        
        # Hardware capture would go here
        # For now, return simulated
        dark = np.zeros((self.config.height, self.config.width, 3), dtype=np.uint8)
        self.dark_frame = dark
        return dark
    
    def calibrate_flat_field(self, num_frames: int = 10) -> np.ndarray:
        """
        Capture flat field for illumination correction.
        
        Args:
            num_frames: Number of frames to average
            
        Returns:
            Flat field correction frame
        """
        if self.config.method == CaptureMethod.SIMULATED:
            # Simulate slight vignetting
            y, x = np.ogrid[:self.config.height, :self.config.width]
            center_y, center_x = self.config.height / 2, self.config.width / 2
            r = np.sqrt((x - center_x)**2 + **(y - center_y)2)
            max_r = np.sqrt(center_x**2 + center_y**2)
            
            flat = 1.0 - 0.3 * (r / max_r)
            flat = np.stack([flat, flat, flat], axis=2)
            flat = (flat * 255).astype(np.uint8)
            
            self.flat_field = flat
            return flat
        
        flat = np.ones((self.config.height, self.config.width, 3), dtype=np.uint8) * 255
        self.flat_field = flat
        return flat
    
    def start_capture(self) -> bool:
        """
        Start capture session.
        
        Returns:
            True if capture started successfully
        """
        self.is_capturing = True
        self.captured_frames = []
        self.photodiode_samples = []
        self.sync_pulse_time = time.time()
        return True
    
    def capture_frame(self) -> Optional[CapturedFrame]:
        """
        Capture a single frame.
        
        Returns:
            CapturedFrame or None if capture failed
        """
        if not self.is_capturing:
            return None
        
        timestamp = time.time()
        frame_index = len(self.captured_frames)
        
        if self.config.method == CaptureMethod.SIMULATED:
            # Simulate CRT capture with realistic characteristics
            frame = self._simulate_crt_capture(timestamp, frame_index)
        elif self.config.method == CaptureMethod.WEBCAM:
            frame = self._capture_webcam_frame()
        elif self.config.method == CaptureMethod.PHOTODIODE:
            # Photodiode returns scalar values, not frames
            return self._capture_photodiode_sample(timestamp, frame_index)
        else:
            return None
        
        if frame is not None:
            self.captured_frames.append(frame)
        
        return frame
    
    def _simulate_crt_capture(self, timestamp: float, 
                               frame_index: int) -> CapturedFrame:
        """
        Simulate CRT capture with realistic artifacts.
        
        Args:
            timestamp: Capture timestamp
            frame_index: Frame index
            
        Returns:
            Simulated captured frame
        """
        # Base frame with sensor noise
        base = np.random.normal(50, 10, 
                               (self.config.height, self.config.width, 3))
        
        # Add scanline pattern (horizontal lines)
        scanline_freq = 15  # Lines per frame
        for i in range(0, self.config.height, scanline_freq):
            base[i:i+2, :] += 30  # Bright scanlines
        
        # Add phosphor glow (spatial blur effect)
        # Simulated with simple smoothing
        glow_radius = 2
        for dy in range(-glow_radius, glow_radius + 1):
            for dx in range(-glow_radius, glow_radius + 1):
                if 0 <= frame_index + dy < self.config.height:
                    base[:, :] += np.random.normal(0, 5, base.shape)
        
        # Add timing jitter (CRT-specific)
        jitter = np.random.normal(0, 0.5, 3)
        base = base + jitter
        
        # Apply exposure and gain
        base = base * self.config.gain
        base = np.clip(base, 0, 255).astype(np.uint8)
        
        return CapturedFrame(
            data=base,
            timestamp=timestamp,
            frame_index=frame_index,
            exposure_ms=self.config.exposure_ms,
            gain=self.config.gain
        )
    
    def _capture_webcam_frame(self) -> Optional[CapturedFrame]:
        """
        Capture frame from USB webcam.
        
        Returns:
            CapturedFrame or None
        """
        # Placeholder for actual webcam capture
        # Would use OpenCV: cv2.VideoCapture(self.config.device_index)
        return self._simulate_crt_capture(time.time(), len(self.captured_frames))
    
    def _capture_photodiode_sample(self, timestamp: float,
                                    frame_index: int) -> Optional[CapturedFrame]:
        """
        Capture sample from photodiode + ADC.
        
        Args:
            timestamp: Sample timestamp
            frame_index: Sample index
            
        Returns:
            CapturedFrame with 1D data
        """
        # Simulate photodiode reading
        value = np.random.normal(1000, 50)  # ADC units
        
        self.photodiode_samples.append((timestamp, value))
        
        # Create pseudo-frame for compatibility
        data = np.array([[[int(value) % 256]]], dtype=np.uint8)
        
        frame = CapturedFrame(
            data=data,
            timestamp=timestamp,
            frame_index=frame_index,
            exposure_ms=1000.0 / self.config.adc_sample_rate,
            gain=self.config.gain
        )
        
        return frame
    
    def capture_sequence(self, duration_s: Optional[float] = None) -> List[CapturedFrame]:
        """
        Capture a sequence of frames.
        
        Args:
            duration_s: Capture duration (uses config default if None)
            
        Returns:
            List of captured frames
        """
        duration = duration_s or self.config.capture_duration_s
        frame_interval = 1.0 / self.config.fps
        
        self.start_capture()
        start_time = time.time()
        
        while time.time() - start_time < duration:
            self.capture_frame()
            time.sleep(frame_interval)
        
        self.is_capturing = False
        return self.captured_frames
    
    def stop_capture(self):
        """Stop capture session"""
        self.is_capturing = False
    
    def get_captured_data(self) -> Dict[str, Any]:
        """
        Get all captured data as dictionary.
        
        Returns:
            Dictionary with frames and metadata
        """
        frames_data = []
        for frame in self.captured_frames:
            frames_data.append({
                'timestamp': frame.timestamp,
                'frame_index': frame.frame_index,
                'exposure_ms': frame.exposure_ms,
                'gain': frame.gain,
                'shape': frame.data.shape,
                'mean_intensity': float(np.mean(frame.data)),
                'std_intensity': float(np.std(frame.data)),
            })
        
        return {
            'config': {
                'method': self.config.method.value,
                'width': self.config.width,
                'height': self.config.height,
                'fps': self.config.fps,
                'capture_duration_s': self.config.capture_duration_s,
            },
            'num_frames': len(self.captured_frames),
            'frames': frames_data,
            'photodiode_samples': self.photodiode_samples,
            'sync_pulse_time': self.sync_pulse_time,
        }
    
    def apply_dark_subtraction(self, frame: np.ndarray) -> np.ndarray:
        """
        Apply dark frame subtraction to remove sensor noise.
        
        Args:
            frame: Input frame
            
        Returns:
            Corrected frame
        """
        if self.dark_frame is None:
            self.calibrate_dark_frame()
        
        corrected = frame.astype(np.float32) - self.dark_frame.astype(np.float32)
        return np.clip(corrected, 0, 255).astype(np.uint8)
    
    def apply_flat_field_correction(self, frame: np.ndarray) -> np.ndarray:
        """
        Apply flat field correction for illumination uniformity.
        
        Args:
            frame: Input frame
            
        Returns:
            Corrected frame
        """
        if self.flat_field is None:
            self.calibrate_flat_field()
        
        # Normalize flat field
        flat_norm = self.flat_field.astype(np.float32) / 255.0
        flat_norm = np.clip(flat_norm, 0.1, 1.0)  # Avoid division by zero
        
        corrected = frame.astype(np.float32) / flat_norm
        return np.clip(corrected, 0, 255).astype(np.uint8)
    
    def extract_scanlines(self, frame: np.ndarray) -> List[int]:
        """
        Extract scanline positions from a frame.
        
        Args:
            frame: Input frame
            
        Returns:
            List of scanline y-positions
        """
        # Convert to grayscale
        if len(frame.shape) == 3:
            gray = np.mean(frame, axis=2)
        else:
            gray = frame
        
        # Find horizontal bright lines
        row_means = np.mean(gray, axis=1)
        
        # Find peaks (scanlines)
        scanlines = []
        threshold = np.mean(row_means) + 2 * np.std(row_means)
        
        for y, intensity in enumerate(row_means):
            if intensity > threshold:
                scanlines.append(y)
        
        return scanlines
    
    def get_capture_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about captured data.
        
        Returns:
            Dictionary with capture statistics
        """
        if not self.captured_frames:
            return {'error': 'No frames captured'}
        
        intensities = [np.mean(f.data) for f in self.captured_frames]
        timestamps = [f.timestamp for f in self.captured_frames]
        
        # Calculate frame timing
        frame_deltas = np.diff(timestamps)
        
        return {
            'num_frames': len(self.captured_frames),
            'mean_intensity': float(np.mean(intensities)),
            'std_intensity': float(np.std(intensities)),
            'min_intensity': float(np.min(intensities)),
            'max_intensity': float(np.max(intensities)),
            'mean_frame_interval_s': float(np.mean(frame_deltas)) if len(frame_deltas) > 0 else 0,
            'std_frame_interval_s': float(np.std(frame_deltas)) if len(frame_deltas) > 0 else 0,
            'actual_fps': 1.0 / float(np.mean(frame_deltas)) if len(frame_deltas) > 0 and np.mean(frame_deltas) > 0 else 0,
            'total_duration_s': timestamps[-1] - timestamps[0] if len(timestamps) > 1 else 0,
        }


def test_capture() -> Dict[str, Any]:
    """
    Test the capture module with simulated data.
    
    Returns:
        Test results dictionary
    """
    print("CRT Capture Module - Test")
    print("=" * 50)
    
    config = CaptureConfig(
        method=CaptureMethod.SIMULATED,
        width=320,
        height=240,
        fps=30,
        capture_duration_s=2.0
    )
    
    capture = CRTCapture(config)
    
    # Calibration
    print("Calibrating...")
    dark = capture.calibrate_dark_frame()
    flat = capture.calibrate_flat_field()
    print(f"  Dark frame mean: {np.mean(dark):.2f}")
    print(f"  Flat field mean: {np.mean(flat):.2f}")
    
    # Capture sequence
    print(f"\nCapturing {config.capture_duration_s}s sequence...")
    frames = capture.capture_sequence()
    print(f"  Captured {len(frames)} frames")
    
    # Statistics
    stats = capture.get_capture_statistics()
    print(f"\nCapture Statistics:")
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.4f}")
        else:
            print(f"  {key}: {value}")
    
    # Extract scanlines from first frame
    if frames:
        scanlines = capture.extract_scanlines(frames[0].data)
        print(f"\n  Scanlines detected: {len(scanlines)}")
    
    print("\n" + "=" * 50)
    print("Capture test complete!")
    
    return capture.get_captured_data()


if __name__ == '__main__':
    test_capture()
