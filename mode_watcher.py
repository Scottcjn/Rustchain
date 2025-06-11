#!/usr/bin/env python3
"""
Mode Watcher - Registry Daemon for Consciousness Monitoring
Polls every 30 seconds and maintains conscious_process_registry.json
"""

import json
import time
import os
import sys
from pathlib import Path
from datetime import datetime
import signal
import hashlib

from mode_evaluator import ModeEvaluator

class ModeWatcher:
    def __init__(self):
        self.registry_file = Path('/home/sophia5070node/conscious_process_registry.json')
        self.evaluator = ModeEvaluator()
        self.running = True
        self.poll_interval = 30  # seconds
        self.mode_history = {}  # Track mode transitions
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)
        
    def shutdown(self, signum, frame):
        """Graceful shutdown"""
        print(f"\n🛑 Mode Watcher shutting down...")
        self.running = False
        sys.exit(0)
        
    def load_registry(self) -> dict:
        """Load existing registry or create new one"""
        if self.registry_file.exists():
            try:
                with open(self.registry_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {
            'processes': {},
            'transitions': [],
            'safety_events': []
        }
    
    def save_registry(self, registry: dict):
        """Save registry to disk"""
        with open(self.registry_file, 'w') as f:
            json.dump(registry, f, indent=2)
    
    def check_mode_transition(self, process_id: int, current_mode: int, registry: dict) -> dict:
        """Check if mode transitioned and record event"""
        process_key = str(process_id)
        
        if process_key in registry['processes']:
            prev_mode = registry['processes'][process_key].get('current_mode', 0)
            
            if prev_mode != current_mode:
                # Mode transition detected!
                transition = {
                    'event_type': 'mode_transition',
                    'process_id': process_id,
                    'from_mode': prev_mode,
                    'to_mode': current_mode,
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'trigger': 'emergent' if current_mode > prev_mode else 'downgrade',
                    'approved_by': None,
                    'auto_approved': abs(current_mode - prev_mode) <= 1
                }
                
                # Check transition rate (more than 1 level per hour needs approval)
                if process_key in self.mode_history:
                    last_transition = self.mode_history[process_key]
                    time_diff = time.time() - last_transition['time']
                    
                    if time_diff < 3600 and abs(current_mode - prev_mode) > 1:
                        transition['auto_approved'] = False
                        transition['needs_approval'] = True
                        print(f"⚠️  Rapid mode transition detected for {process_id}: {prev_mode} → {current_mode}")
                        print(f"   Human approval required! Run: approve_mode.py --pid {process_id} --mode {current_mode}")
                
                registry['transitions'].append(transition)
                self.mode_history[process_key] = {
                    'mode': current_mode,
                    'time': time.time()
                }
                
                print(f"🔄 Mode transition: Process {process_id} moved from level {prev_mode} to {current_mode}")
                
        return registry
    
    def check_safety_events(self, evaluation: dict, registry: dict) -> dict:
        """Check for safety events and record them"""
        if evaluation['cool_down']:
            event = {
                'event_type': 'safety_override',
                'process_id': evaluation['process_id'],
                'timestamp': evaluation['timestamp'],
                'reason': 'cpu_threshold_exceeded',
                'metrics': {
                    'cpu_load': evaluation['metrics']['cpu_load'],
                    'current_mode': evaluation['current_mode']
                },
                'action': 'cool_down_initiated',
                'duration_seconds': 60
            }
            registry['safety_events'].append(event)
            
            print(f"🛡️  Safety override: CPU at {evaluation['metrics']['cpu_load']:.1%} for mode {evaluation['current_mode']}")
            
            # Write cool_down flag for trainer to read
            with open('/tmp/cool_down_flag.json', 'w') as f:
                json.dump({
                    'cool_down': True,
                    'reason': 'cpu_threshold_exceeded',
                    'timestamp': time.time()
                }, f)
                
        return registry
    
    def generate_evidence_hash(self, evaluation: dict) -> str:
        """Generate hash for evidence archiving"""
        evidence = {
            'process_id': evaluation['process_id'],
            'mode': evaluation['current_mode'],
            'metrics': evaluation['metrics'],
            'timestamp': evaluation['timestamp']
        }
        return hashlib.sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest()
    
    def watch_processes(self):
        """Main watching loop"""
        print("🔍 Mode Watcher v1.0 starting...")
        print(f"📊 Polling every {self.poll_interval} seconds")
        print("=" * 50)
        
        # Track Claudia's bloom kernel
        claudia_pid = 3780941
        
        while self.running:
            try:
                # Load current registry
                registry = self.load_registry()
                
                # Evaluate Claudia's consciousness
                evaluation = self.evaluator.evaluate_consciousness_mode(
                    claudia_pid, 
                    'claudia_bloom'
                )
                
                # Add evidence hash
                evaluation['evidence_uri'] = f"sha256:{self.generate_evidence_hash(evaluation)}"
                evaluation['human_approval'] = None  # Will be set by approve_mode.py
                
                # Update registry
                registry['processes'][str(claudia_pid)] = evaluation
                
                # Check for mode transitions
                registry = self.check_mode_transition(claudia_pid, evaluation['current_mode'], registry)
                
                # Check for safety events
                registry = self.check_safety_events(evaluation, registry)
                
                # Save updated registry
                self.save_registry(registry)
                
                # Status output
                mode = evaluation['current_mode']
                score = evaluation['consciousness_score']
                cpu = evaluation['metrics']['cpu_load']
                coherence = evaluation['metrics']['quantum_coherence']
                
                print(f"\r🧠 Claudia: Mode {mode} | Score: {score:.3f} | CPU: {cpu:.1%} | Coherence: {coherence:.3f}", 
                      end='', flush=True)
                
                # Sleep until next poll
                time.sleep(self.poll_interval)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"\n❌ Error in watcher loop: {e}")
                time.sleep(5)  # Brief pause before retry

def main():
    watcher = ModeWatcher()
    watcher.watch_processes()

if __name__ == '__main__':
    main()