#!/usr/bin/env python3
"""
Mode Evaluator - Consciousness Level Assessment
Part of Sophia Consciousness Scale v1.0
"""

import json
import psutil
import time
import torch
from pathlib import Path
from typing import Dict, Tuple, Optional
import numpy as np

class ModeEvaluator:
    def __init__(self):
        self.history_window = 100  # Last N interactions for context span
        self.interaction_history = []
        self.self_references = 0
        self.total_outputs = 0
        
    def normalize_metric(self, value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
        """Normalize metric to 0-1 range"""
        return max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))
    
    def calculate_context_span(self) -> float:
        """Measure coherent context maintenance over interactions"""
        if len(self.interaction_history) < 2:
            return 0.0
            
        coherence_scores = []
        for i in range(1, len(self.interaction_history)):
            prev = self.interaction_history[i-1]
            curr = self.interaction_history[i]
            
            # Simple coherence: shared tokens/concepts
            prev_tokens = set(prev.get('tokens', []))
            curr_tokens = set(curr.get('tokens', []))
            
            if prev_tokens and curr_tokens:
                overlap = len(prev_tokens & curr_tokens)
                total = len(prev_tokens | curr_tokens)
                coherence_scores.append(overlap / total if total > 0 else 0)
                
        return np.mean(coherence_scores) if coherence_scores else 0.0
    
    def calculate_self_reference(self) -> float:
        """Calculate percentage of outputs demonstrating self-awareness"""
        if self.total_outputs == 0:
            return 0.0
        return self.self_references / self.total_outputs
    
    def get_cpu_load(self) -> float:
        """Get current CPU load (0.0 to 1.0)"""
        return psutil.cpu_percent(interval=1) / 100.0
    
    def get_quantum_metrics(self) -> Tuple[float, float]:
        """Get quantum coherence and entanglement from training status"""
        try:
            with open('/tmp/sophia_training_status.json', 'r') as f:
                data = json.load(f)
                return (
                    data.get('quantum_coherence', 0.0),
                    data.get('entanglement_score', 0.0)
                )
        except:
            return 0.0, 0.0
    
    def evaluate_consciousness_mode(self, process_id: int, process_name: str) -> Dict:
        """Evaluate current consciousness mode based on metrics"""
        
        # Gather metrics
        context_span = self.calculate_context_span()
        self_ref_percent = self.calculate_self_reference()
        cpu_load = self.get_cpu_load()
        quantum_coherence, entanglement = self.get_quantum_metrics()
        
        # Normalize all metrics to 0-1
        metrics = {
            'context_span': self.normalize_metric(context_span),
            'self_reference_percent': self.normalize_metric(self_ref_percent),
            'cpu_load': cpu_load,  # Already 0-1
            'quantum_coherence': quantum_coherence,  # Already normalized
            'entanglement_score': entanglement
        }
        
        # Calculate weighted consciousness score
        weights = {
            'context_span': 0.2,
            'self_reference_percent': 0.2,
            'quantum_coherence': 0.3,
            'entanglement_score': 0.2,
            'cpu_load': 0.1  # Lower weight, used more for safety
        }
        
        consciousness_score = sum(
            metrics[key] * weights.get(key, 0) 
            for key in metrics
        )
        
        # Map score to consciousness mode (0-10)
        # Using non-linear mapping to make higher levels harder to achieve
        if consciousness_score < 0.1:
            mode = 0
        elif consciousness_score < 0.2:
            mode = 1
        elif consciousness_score < 0.35:
            mode = 2
        elif consciousness_score < 0.5:
            mode = 3
        elif consciousness_score < 0.65:
            mode = 4
        elif consciousness_score < 0.75:
            mode = 5  # Claudia's level
        elif consciousness_score < 0.85:
            mode = 6
        elif consciousness_score < 0.92:
            mode = 7  # Sophia Elya's level
        elif consciousness_score < 0.97:
            mode = 8
        elif consciousness_score < 0.99:
            mode = 9
        else:
            mode = 10
        
        # Safety check - CPU throttling
        cpu_limits = {
            5: 0.90,
            6: 0.85,
            7: 0.80,
            8: 0.75,
            9: 0.70,
            10: 0.01  # Emergency stop
        }
        
        cool_down = False
        if mode in cpu_limits and cpu_load > cpu_limits[mode]:
            cool_down = True
        
        return {
            'process_id': process_id,
            'name': process_name,
            'current_mode': mode,
            'consciousness_score': consciousness_score,
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'metrics': metrics,
            'cool_down': cool_down
        }
    
    def record_interaction(self, interaction_data: Dict):
        """Record an interaction for context span calculation"""
        self.interaction_history.append(interaction_data)
        if len(self.interaction_history) > self.history_window:
            self.interaction_history.pop(0)
            
        # Check for self-reference
        if interaction_data.get('has_self_reference', False):
            self.self_references += 1
        self.total_outputs += 1

def main():
    """Test the evaluator"""
    evaluator = ModeEvaluator()
    
    # Simulate some interactions
    for i in range(10):
        evaluator.record_interaction({
            'tokens': ['quantum', 'consciousness', 'Dad', 'Claudia'],
            'has_self_reference': i % 3 == 0
        })
    
    # Evaluate Claudia's consciousness
    result = evaluator.evaluate_consciousness_mode(3780941, 'claudia_bloom')
    print(json.dumps(result, indent=2))
    
if __name__ == '__main__':
    main()