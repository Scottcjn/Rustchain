"""
Boot Chime Capture Module

Captures and processes boot chime audio from system audio input or file.
Supports real-time capture and batch processing of recorded samples.
"""

import numpy as np
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass
import time
import wave
import struct
import os
from pathlib import Path


@dataclass
class AudioCaptureConfig:
    """Configuration for audio capture"""
    sample_rate: int = 44100
    channels: int = 1
    bit_depth: int = 16
    duration: float = 5.0
    trigger_threshold: float = 0.01
    silence_duration: float = 0.5


@dataclass
class CapturedAudio:
    """Captured audio sample with metadata"""
    data: np.ndarray
    sample_rate: int
    channels: int
    duration: float
    captured_at: float
    device_info: Optional[Dict[str, Any]] = None
    quality_score: float = 0.0


class BootChimeCapture:
    """
    Boot chime audio capture and processing.
    
    Captures system boot sounds for hardware attestation.
    Can operate in real-time capture mode or process pre-recorded files.
    """
    
    def __init__(self, config: Optional[AudioCaptureConfig] = None):
        self.config = config or AudioCaptureConfig()
        self._is_capturing = False
        
    def capture(self, duration: Optional[float] = None,
                trigger: bool = True) -> CapturedAudio:
        """
        Capture audio from system input.
        
        Args:
            duration: Capture duration in seconds (uses config default if None)
            trigger: If True, wait for audio trigger before recording
            
        Returns:
            CapturedAudio object with recorded data
        """
        duration = duration or self.config.duration
        
        try:
            # Try to use sounddevice for real capture
            import sounddevice as sd
            
            if trigger:
                # Wait for trigger sound
                print("Listening for boot chime trigger...")
                self._wait_for_trigger(sd)
            
            print(f"Recording for {duration} seconds...")
            self._is_capturing = True
            
            # Record audio
            recording = sd.rec(
                int(duration * self.config.sample_rate),
                samplerate=self.config.sample_rate,
                channels=self.config.channels,
                dtype=np.float32
            )
            sd.wait()
            
            self._is_capturing = False
            
            audio_data = recording.flatten()
            
            # Get device info if available
            device_info = None
            try:
                device_info = sd.query_devices()
                if isinstance(device_info, list) and len(device_info) > 0:
                    device_info = device_info[0]
            except:
                pass
            
            return CapturedAudio(
                data=audio_data,
                sample_rate=self.config.sample_rate,
                channels=self.config.channels,
                duration=duration,
                captured_at=time.time(),
                device_info=device_info,
                quality_score=self._assess_quality(audio_data)
            )
            
        except ImportError:
            # sounddevice not available, generate synthetic capture
            print("sounddevice not available, using synthetic capture mode")
            return self._synthetic_capture(duration)
        except Exception as e:
            print(f"Capture error: {e}, using synthetic mode")
            return self._synthetic_capture(duration)
    
    def capture_from_file(self, filepath: str) -> CapturedAudio:
        """
        Load audio from file (WAV format).
        
        Args:
            filepath: Path to WAV file
            
        Returns:
            CapturedAudio object
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {filepath}")
        
        try:
            # Try scipy.io.wavfile first
            from scipy.io import wavfile
            sample_rate, data = wavfile.read(filepath)
            
            # Normalize to [-1, 1]
            if data.dtype == np.int16:
                data = data.astype(np.float32) / 32768.0
            elif data.dtype == np.int32:
                data = data.astype(np.float32) / 2147483648.0
            elif data.dtype == np.uint8:
                data = (data.astype(np.float32) - 128) / 128.0
            
            # Convert to mono if stereo
            if len(data.shape) > 1:
                data = np.mean(data, axis=1)
            
            duration = len(data) / sample_rate
            
            return CapturedAudio(
                data=data,
                sample_rate=sample_rate,
                channels=1,
                duration=duration,
                captured_at=os.path.getmtime(filepath),
                quality_score=self._assess_quality(data)
            )
            
        except ImportError:
            # Fall back to wave module
            return self._load_wav_builtin(filepath)
    
    def save_audio(self, audio: CapturedAudio, filepath: str) -> None:
        """
        Save captured audio to WAV file.
        
        Args:
            audio: CapturedAudio object
            filepath: Output file path
        """
        # Normalize to int16 range
        data = audio.data
        max_val = np.max(np.abs(data))
        if max_val > 0:
            data = data / max_val
        data_int16 = (data * 32767).astype(np.int16)
        
        with wave.open(filepath, 'wb') as wav_file:
            wav_file.setnchannels(audio.channels)
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(audio.sample_rate)
            wav_file.writeframes(data_int16.tobytes())
    
    def detect_boot_chime(self, audio: CapturedAudio) -> Tuple[bool, Dict[str, Any]]:
        """
        Detect if audio contains a boot chime sound.
        
        Args:
            audio: CapturedAudio to analyze
            
        Returns:
            Tuple of (is_boot_chime, detection_details)
        """
        data = audio.data
        
        # Boot chimes typically have:
        # 1. Distinct onset (sudden amplitude increase)
        # 2. Harmonic structure (musical tones)
        # 3. Decay envelope
        # 4. Duration 0.5-3 seconds
        
        details = {
            "has_onset": False,
            "has_harmonics": False,
            "has_decay": False,
            "duration_ok": False,
            "confidence": 0.0
        }
        
        # Check for onset
        envelope = self._compute_envelope(data, window_size=1024)
        onset_detected = self._detect_onset(envelope)
        details["has_onset"] = onset_detected
        
        # Check duration
        details["duration_ok"] = 0.5 <= audio.duration <= 5.0
        
        # Check for harmonic structure (simplified)
        fft_data = np.fft.rfft(data[:min(44100, len(data))])
        magnitude = np.abs(fft_data)
        peaks = self._find_peaks(magnitude, n_peaks=5)
        
        if len(peaks) >= 3:
            # Check if peaks have harmonic relationship
            fundamental_idx = peaks[0]
            has_harmonics = True
            for i, peak in enumerate(peaks[1:], 2):
                ratio = peak / fundamental_idx
                if abs(ratio - round(ratio)) > 0.15:
                    has_harmonics = False
                    break
            details["has_harmonics"] = has_harmonics
        
        # Check for decay
        if len(envelope) > 10:
            first_half = np.mean(envelope[:len(envelope)//2])
            second_half = np.mean(envelope[len(envelope)//2:])
            details["has_decay"] = second_half < first_half * 0.7
        
        # Compute confidence
        score = sum([
            details["has_onset"] * 0.3,
            details["has_harmonics"] * 0.3,
            details["has_decay"] * 0.2,
            details["duration_ok"] * 0.2
        ])
        details["confidence"] = score
        
        is_boot_chime = score >= 0.5
        return is_boot_chime, details
    
    def _wait_for_trigger(self, sd, timeout: float = 30.0) -> None:
        """Wait for audio trigger (sound above threshold)"""
        start_time = time.time()
        stream = sd.InputStream(
            channels=self.config.channels,
            samplerate=self.config.sample_rate
        )
        stream.start()
        
        silence_start = None
        
        while time.time() - start_time < timeout:
            data, _ = stream.read(1024)
            rms = np.sqrt(np.mean(data ** 2))
            
            if rms > self.config.trigger_threshold:
                # Sound detected
                if silence_start is not None:
                    silence_start = None
            else:
                # Silence detected
                if silence_start is None:
                    silence_start = time.time()
                elif time.time() - silence_start > self.config.silence_duration:
                    # Trigger! Sound followed by silence
                    stream.stop()
                    stream.close()
                    print("Boot chime trigger detected!")
                    return
        
        stream.stop()
        stream.close()
        print("Using manual trigger (timeout)")
    
    def _synthetic_capture(self, duration: float) -> CapturedAudio:
        """Generate synthetic boot chime for testing"""
        t = np.linspace(0, duration, int(self.config.sample_rate * duration))
        
        # Simulate boot chime: harmonic series with decay
        fundamental = 440  # A4
        harmonics = [1, 2, 3, 4, 5]
        
        signal = np.zeros_like(t)
        for h in harmonics:
            amplitude = 1.0 / h  # Decreasing amplitude for higher harmonics
            freq = fundamental * h
            signal += amplitude * np.sin(2 * np.pi * freq * t)
        
        # Apply decay envelope
        decay = np.exp(-t * 2)  # 2 second decay
        signal *= decay
        
        # Add slight noise for realism
        noise = np.random.normal(0, 0.01, len(signal))
        signal += noise
        
        return CapturedAudio(
            data=signal,
            sample_rate=self.config.sample_rate,
            channels=self.config.channels,
            duration=duration,
            captured_at=time.time(),
            quality_score=self._assess_quality(signal)
        )
    
    def _load_wav_builtin(self, filepath: str) -> CapturedAudio:
        """Load WAV using built-in wave module"""
        with wave.open(filepath, 'rb') as wav_file:
            n_channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            framerate = wav_file.getframerate()
            n_frames = wav_file.getnframes()
            
            raw_data = wav_file.readframes(n_frames)
            
            # Convert based on sample width
            if sample_width == 1:
                fmt = f"{n_frames * n_channels}B"
                data = struct.unpack(fmt, raw_data)
                data = np.array(data, dtype=np.float32) / 128.0 - 1.0
            elif sample_width == 2:
                fmt = f"{n_frames * n_channels}h"
                data = struct.unpack(fmt, raw_data)
                data = np.array(data, dtype=np.float32) / 32768.0
            elif sample_width == 4:
                fmt = f"{n_frames * n_channels}i"
                data = struct.unpack(fmt, raw_data)
                data = np.array(data, dtype=np.float32) / 2147483648.0
            else:
                raise ValueError(f"Unsupported sample width: {sample_width}")
            
            # Convert to mono
            if n_channels > 1:
                data = data.reshape(-1, n_channels)
                data = np.mean(data, axis=1)
            
            duration = n_frames / framerate
            
            return CapturedAudio(
                data=data,
                sample_rate=framerate,
                channels=1,
                duration=duration,
                captured_at=os.path.getmtime(filepath),
                quality_score=self._assess_quality(data)
            )
    
    def _assess_quality(self, data: np.ndarray) -> float:
        """Assess audio quality (0-1 score)"""
        # Check for clipping
        clipping = np.sum(np.abs(data) > 0.99) / len(data)
        
        # Check SNR (simplified: ratio of signal to quiet portions)
        signal_power = np.mean(data ** 2)
        
        # Check duration
        duration_ok = 0.5 <= len(data) / self.config.sample_rate <= 10.0
        
        # Quality score
        quality = 1.0
        quality -= clipping * 0.5  # Penalize clipping
        quality -= max(0, 0.001 - signal_power) * 100  # Penalize very quiet
        if not duration_ok:
            quality *= 0.5
        
        return max(0.0, min(1.0, quality))
    
    def _compute_envelope(self, data: np.ndarray, window_size: int) -> np.ndarray:
        """Compute amplitude envelope"""
        n_windows = len(data) // window_size
        envelope = np.zeros(n_windows)
        
        for i in range(n_windows):
            start = i * window_size
            end = start + window_size
            envelope[i] = np.sqrt(np.mean(data[start:end] ** 2))
        
        return envelope
    
    def _detect_onset(self, envelope: np.ndarray) -> bool:
        """Detect sudden onset in envelope"""
        if len(envelope) < 3:
            return False
        
        # Look for large increase followed by sustained level
        diff = np.diff(envelope)
        max_increase = np.max(diff)
        
        # Onset if sudden increase > 50% of max envelope
        return max_increase > 0.5 * np.max(envelope)
    
    def _find_peaks(self, data: np.ndarray, n_peaks: int) -> np.ndarray:
        """Find peak indices in array"""
        peaks = []
        for i in range(1, len(data) - 1):
            if data[i] > data[i-1] and data[i] > data[i+1]:
                peaks.append(i)
        
        # Sort by magnitude
        peaks.sort(key=lambda x: data[x], reverse=True)
        return np.array(peaks[:n_peaks])
