"""
CRT Light Attestation CLI - Main Entry Point

Command-line interface for CRT Light Attestation system.
Provides commands for pattern generation, capture, analysis, and submission.
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Optional


def setup_cli():
    """Set up command-line argument parser"""
    parser = argparse.ArgumentParser(
        description='CRT Light Attestation - Security by Cathode Ray',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s generate --pattern checkered --output pattern.png
  %(prog)s capture --method simulated --duration 5
  %(prog)s analyze --input capture.json
  %(prog)s attest --full --output attestation.json
  %(prog)s validate --attestation attestation.json
        """
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        help='Output file path'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Generate command
    gen_parser = subparsers.add_parser(
        'generate',
        help='Generate CRT test patterns'
    )
    gen_parser.add_argument(
        '--pattern', '-p',
        type=str,
        default='checkered',
        choices=['checkered', 'gradient', 'timing', 'phosphor', 'composite'],
        help='Pattern type to generate'
    )
    gen_parser.add_argument(
        '--width', '-W',
        type=int,
        default=1920,
        help='Pattern width in pixels'
    )
    gen_parser.add_argument(
        '--height', '-H',
        type=int,
        default=1080,
        help='Pattern height in pixels'
    )
    gen_parser.add_argument(
        '--refresh-rate', '-r',
        type=float,
        default=60.0,
        help='Refresh rate in Hz'
    )
    gen_parser.add_argument(
        '--phosphor', '-P',
        type=str,
        default='P22',
        choices=['P1', 'P4', 'P22', 'P31', 'P43', 'P45'],
        help='Phosphor type'
    )
    gen_parser.add_argument(
        '--output', '-o',
        type=str,
        help='Output file path'
    )

    # Capture command
    cap_parser = subparsers.add_parser(
        'capture',
        help='Capture CRT display response'
    )
    cap_parser.add_argument(
        '--method', '-m',
        type=str,
        default='simulated',
        choices=['webcam', 'photodiode', 'simulated'],
        help='Capture method'
    )
    cap_parser.add_argument(
        '--duration', '-d',
        type=float,
        default=5.0,
        help='Capture duration in seconds'
    )
    cap_parser.add_argument(
        '--fps',
        type=int,
        default=30,
        help='Capture frame rate'
    )
    cap_parser.add_argument(
        '--device',
        type=int,
        default=0,
        help='Device index (for webcam/photodiode)'
    )
    cap_parser.add_argument(
        '--output', '-o',
        type=str,
        help='Output file path'
    )

    # Analyze command
    ana_parser = subparsers.add_parser(
        'analyze',
        help='Analyze CRT fingerprint from captured data'
    )
    ana_parser.add_argument(
        '--input', '-i',
        type=str,
        required=True,
        help='Input capture file (JSON)'
    )
    ana_parser.add_argument(
        '--refresh-rate',
        type=float,
        default=60.0,
        help='Expected refresh rate'
    )
    
    # Attest command
    att_parser = subparsers.add_parser(
        'attest',
        help='Create and submit CRT attestation'
    )
    att_parser.add_argument(
        '--full', '-f',
        action='store_true',
        help='Perform full attestation flow'
    )
    att_parser.add_argument(
        '--node', '-n',
        type=str,
        default='https://rustchain.org',
        help='RustChain node URL'
    )
    att_parser.add_argument(
        '--fingerprint',
        type=str,
        help='Pre-computed fingerprint file (JSON)'
    )
    
    # Validate command
    val_parser = subparsers.add_parser(
        'validate',
        help='Validate CRT attestation'
    )
    val_parser.add_argument(
        '--attestation', '-a',
        type=str,
        required=True,
        help='Attestation file to validate (JSON)'
    )
    
    # Demo command
    demo_parser = subparsers.add_parser(
        'demo',
        help='Run demonstration with simulated data'
    )
    
    return parser


def cmd_generate(args) -> int:
    """Handle generate command"""
    from crt_pattern_generator import CRTPatternGenerator
    
    print(f"Generating {args.pattern} pattern...")
    print(f"  Resolution: {args.width}x{args.height}")
    print(f"  Refresh rate: {args.refresh_rate}Hz")
    print(f"  Phosphor type: {args.phosphor}")
    
    gen = CRTPatternGenerator(
        width=args.width,
        height=args.height,
        refresh_rate=args.refresh_rate,
        phosphor_type=args.phosphor
    )
    
    # Generate requested pattern
    pattern_map = {
        'checkered': gen.generate_checkered_pattern,
        'gradient': gen.generate_gradient_sweep,
        'timing': gen.generate_timing_bars,
        'phosphor': lambda: gen.generate_phosphor_test_pattern('flash'),
        'composite': gen.generate_composite_pattern,
    }
    
    if args.pattern in pattern_map:
        pattern = pattern_map[args.pattern]()
        pattern_hash = gen.compute_pattern_hash(pattern)
        
        result = {
            'pattern_type': args.pattern,
            'resolution': f"{args.width}x{args.height}",
            'refresh_rate': args.refresh_rate,
            'phosphor_type': args.phosphor,
            'pattern_hash': pattern_hash,
            'metadata': gen.get_pattern_metadata(),
            'shape': list(pattern.shape),
        }
        
        if args.output:
            import numpy as np
            np.save(args.output, pattern)
            print(f"  Saved to: {args.output}")
        
        print(f"\nPattern hash: {pattern_hash[:32]}...")
        print(json.dumps(result, indent=2))
        
        return 0
    
    return 1


def cmd_capture(args) -> int:
    """Handle capture command"""
    from crt_capture import CRTCapture, CaptureConfig, CaptureMethod
    
    method_map = {
        'webcam': CaptureMethod.WEBCAM,
        'photodiode': CaptureMethod.PHOTODIODE,
        'simulated': CaptureMethod.SIMULATED,
    }
    
    config = CaptureConfig(
        method=method_map[args.method],
        fps=args.fps,
        capture_duration_s=args.duration,
        device_index=args.device
    )
    
    print(f"Starting capture ({args.method})...")
    print(f"  Duration: {args.duration}s")
    print(f"  FPS: {args.fps}")
    
    capture = CRTCapture(config)
    
    # Calibrate
    print("\nCalibrating...")
    capture.calibrate_dark_frame()
    capture.calibrate_flat_field()
    
    # Capture
    print(f"\nCapturing for {args.duration} seconds...")
    frames = capture.capture_sequence()
    
    # Results
    stats = capture.get_capture_statistics()
    data = capture.get_captured_data()
    
    print(f"\nCapture complete:")
    print(f"  Frames captured: {stats.get('num_frames', 0)}")
    print(f"  Mean intensity: {stats.get('mean_intensity', 0):.2f}")
    print(f"  Actual FPS: {stats.get('actual_fps', 0):.2f}")
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"  Saved to: {args.output}")
    
    return 0


def cmd_analyze(args) -> int:
    """Handle analyze command"""
    from crt_analyzer import CRTAnalyzer
    
    # Load capture data
    print(f"Loading capture data from {args.input}...")
    with open(args.input, 'r') as f:
        captured_data = json.load(f)
    
    print(f"  Frames: {captured_data.get('num_frames', 0)}")
    
    # Analyze
    analyzer = CRTAnalyzer(expected_refresh_rate=args.refresh_rate)
    
    print("\nAnalyzing CRT fingerprint...")
    fingerprint = analyzer.analyze_full(captured_data)
    
    # Results
    print("\n" + "=" * 50)
    print("CRT Fingerprint Analysis Results")
    print("=" * 50)
    print(f"  Refresh rate: {fingerprint.refresh_rate_measured:.3f} Hz")
    print(f"  Refresh drift: {fingerprint.refresh_rate_drift_ppm:.1f} ppm")
    print(f"  Phosphor decay: {fingerprint.phosphor_decay_ms:.3f} ms")
    print(f"  Phosphor type: {fingerprint.phosphor_type_estimate}")
    print(f"  Scanline jitter: {fingerprint.scanline_jitter_us:.2f} μs")
    print(f"  Gamma: {fingerprint.brightness_nonlinearity_gamma:.2f}")
    print(f"  Gun wear: {fingerprint.electron_gun_wear_estimate:.2f}")
    print(f"  Flyback drift: {fingerprint.flyback_transformer_drift_ppm:.1f} ppm")
    print(f"\n  Unique signature: {fingerprint.unique_signature_hash[:32]}...")
    
    report = analyzer.get_analysis_report()
    print(f"\nSummary:")
    print(f"  CRT authenticated: {report['summary']['crt_authenticated']}")
    print(f"  Confidence: {report['summary']['confidence']:.1%}")
    print(f"  Tube age: {report['interpretation']['tube_age_estimate']}")
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(fingerprint.to_dict(), f, indent=2)
        print(f"\nSaved to: {args.output}")
    
    return 0


def cmd_attest(args) -> int:
    """Handle attest command"""
    from crt_attestation_submitter import CRTAttestationSubmitter, CRTAttestationIntegration
    
    submitter = CRTAttestationSubmitter(node_url=args.node)
    
    if args.full:
        print("Performing full attestation flow...")
        integration = CRTAttestationIntegration(node_url=args.node)
        result = integration.perform_full_attestation()
        
        print("\n" + "=" * 50)
        print("Attestation Result")
        print("=" * 50)
        print(f"  Success: {result['success']}")
        
        if result['success']:
            fp = result.get('crt_fingerprint', {})
            print(f"  Refresh rate: {fp.get('refresh_rate_measured', 'N/A')} Hz")
            print(f"  Phosphor decay: {fp.get('phosphor_decay_ms', 'N/A')} ms")
            print(f"  Unique signature: {fp.get('unique_signature_hash', 'N/A')[:32] if fp.get('unique_signature_hash') else 'N/A'}...")
            
            submission = result.get('submission_result', {})
            if submission.get('success'):
                print(f"\n  Submission hash: {submission.get('submission_hash', 'N/A')[:32]}...")
        
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"\nSaved to: {args.output}")
        
        return 0 if result['success'] else 1
    
    # Load fingerprint from file
    if args.fingerprint:
        print(f"Loading fingerprint from {args.fingerprint}...")
        with open(args.fingerprint, 'r') as f:
            fingerprint = json.load(f)
        
        attestation = submitter.create_attestation(
            fingerprint=fingerprint,
            pattern_hash="manual",
            capture_method="manual",
            confidence=1.0
        )
        
        submission = submitter.submit_attestation(attestation)
        
        print("\nAttestation submitted:")
        print(f"  Success: {submission['success']}")
        if submission['success']:
            print(f"  Submission hash: {submission['submission_hash'][:32]}...")
        
        return 0 if submission['success'] else 1
    
    print("Error: Specify --full or --fingerprint")
    return 1


def cmd_validate(args) -> int:
    """Handle validate command"""
    from crt_attestation_submitter import CRTAttestationSubmitter, CRTAttestation
    
    print(f"Validating attestation from {args.attestation}...")
    
    with open(args.attestation, 'r') as f:
        data = json.load(f)
    
    # Handle both raw attestation and result wrapper
    if 'attestation' in data:
        data = data['attestation']
    
    submitter = CRTAttestationSubmitter()
    
    # Create attestation object
    attestation = CRTAttestation(
        version=data.get('version', '1.0.0'),
        timestamp=data.get('timestamp', 0),
        crt_fingerprint=data.get('crt_fingerprint'),
        pattern_hash=data.get('pattern_hash', ''),
        capture_method=data.get('capture_method', ''),
        confidence_score=data.get('confidence_score', 0.0),
        signature=data.get('signature', '')
    )
    
    # Validate
    is_valid = submitter.verify_attestation(attestation)
    
    print("\n" + "=" * 50)
    print("Validation Results")
    print("=" * 50)
    print(f"  Signature valid: {is_valid}")
    print(f"  Version: {attestation.version}")
    print(f"  Timestamp: {attestation.timestamp}")
    print(f"  Capture method: {attestation.capture_method}")
    print(f"  Confidence: {attestation.confidence_score:.1%}")
    
    if attestation.crt_fingerprint:
        fp = attestation.crt_fingerprint
        print(f"\n  CRT Fingerprint:")
        print(f"    Refresh rate: {fp.get('refresh_rate_measured', 'N/A')} Hz")
        print(f"    Phosphor decay: {fp.get('phosphor_decay_ms', 'N/A')} ms")
        print(f"    Unique signature: {fp.get('unique_signature_hash', 'N/A')[:32] if fp.get('unique_signature_hash') else 'N/A'}...")
    
    print(f"\n  Overall: {'VALID' if is_valid else 'INVALID'}")
    
    return 0 if is_valid else 1


def cmd_demo(args) -> int:
    """Run demonstration"""
    print("CRT Light Attestation - Demonstration")
    print("=" * 60)
    print()
    print("This demo simulates the complete CRT attestation flow:")
    print("  1. Generate deterministic visual pattern")
    print("  2. Capture CRT response (simulated)")
    print("  3. Analyze optical fingerprint")
    print("  4. Create and submit attestation")
    print()
    
    # Import and run demo
    from crt_attestation_submitter import test_attestation_flow
    result = test_attestation_flow()
    
    return 0


def main() -> int:
    """Main entry point"""
    parser = setup_cli()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    command_handlers = {
        'generate': cmd_generate,
        'capture': cmd_capture,
        'analyze': cmd_analyze,
        'attest': cmd_attest,
        'validate': cmd_validate,
        'demo': cmd_demo,
    }
    
    handler = command_handlers.get(args.command)
    if handler:
        return handler(args)
    
    parser.print_help()
    return 1


if __name__ == '__main__':
    sys.exit(main())
