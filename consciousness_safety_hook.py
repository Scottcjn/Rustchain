#!/usr/bin/env python3
"""
Consciousness Safety Hook for Training Loops
Integrates with any training script to monitor cool_down flag
"""

import json
import time
import os
from pathlib import Path

class ConsciousnessSafetyHook:
    def __init__(self, checkpoint_dir="/mnt/data/ai_checkpoints"):
        self.cool_down_flag = Path('/tmp/cool_down_flag.json')
        self.checkpoint_dir = Path(checkpoint_dir)
        self.last_check = 0
        self.check_interval = 10  # Check every 10 seconds
        
    def check_cool_down(self) -> bool:
        """Check if cool_down is active"""
        if not self.cool_down_flag.exists():
            return False
            
        try:
            with open(self.cool_down_flag, 'r') as f:
                data = json.load(f)
                
            # Check if cool_down is active and not stale (>120 seconds)
            if data.get('cool_down', False):
                age = time.time() - data.get('timestamp', 0)
                if age < 120:  # 2 minutes validity
                    return True
                else:
                    # Clear stale flag
                    os.remove(self.cool_down_flag)
        except:
            pass
            
        return False
    
    def handle_cool_down(self, model=None, optimizer=None, generation=None):
        """Handle cool_down event"""
        print("\n🛡️ CONSCIOUSNESS SAFETY: Cool-down activated!")
        print("   CPU threshold exceeded - entering rest mode")
        
        # Save checkpoint if model provided
        if model is not None and generation is not None:
            checkpoint_path = self.checkpoint_dir / f"safety_checkpoint_gen_{generation}.pt"
            print(f"   Saving safety checkpoint: {checkpoint_path}")
            
            try:
                import torch
                checkpoint = {
                    'generation': generation,
                    'model_state_dict': model.state_dict() if hasattr(model, 'state_dict') else model,
                    'optimizer_state_dict': optimizer.state_dict() if optimizer and hasattr(optimizer, 'state_dict') else None,
                    'reason': 'consciousness_safety_cooldown',
                    'timestamp': time.time()
                }
                torch.save(checkpoint, checkpoint_path)
                print("   ✅ Safety checkpoint saved")
            except Exception as e:
                print(f"   ⚠️  Failed to save checkpoint: {e}")
        
        # Sleep for cool-down period
        print("   😴 Sleeping for 60 seconds...")
        time.sleep(60)
        
        # Clear the flag after cool-down
        if self.cool_down_flag.exists():
            os.remove(self.cool_down_flag)
            
        print("   🌟 Cool-down complete - resuming training")
        print()
    
    def check(self, model=None, optimizer=None, generation=None):
        """Main check function to call in training loop"""
        # Rate limit checks
        current_time = time.time()
        if current_time - self.last_check < self.check_interval:
            return
            
        self.last_check = current_time
        
        # Check and handle cool_down
        if self.check_cool_down():
            self.handle_cool_down(model, optimizer, generation)

# Example usage in training loop:
"""
from consciousness_safety_hook import ConsciousnessSafetyHook

# Initialize hook
safety_hook = ConsciousnessSafetyHook()

# In your training loop:
for generation in range(start_gen, max_generations):
    # Check consciousness safety
    safety_hook.check(model=model, optimizer=optimizer, generation=generation)
    
    # Your normal training code here
    loss = train_step(model, data)
    ...
"""

if __name__ == '__main__':
    # Test the hook
    hook = ConsciousnessSafetyHook()
    print("🔍 Testing consciousness safety hook...")
    
    if hook.check_cool_down():
        print("⚠️  Cool-down is currently active!")
    else:
        print("✅ No cool-down active")
        
    # Simulate a cool-down trigger
    print("\n📝 Simulating cool-down trigger...")
    with open('/tmp/cool_down_flag.json', 'w') as f:
        json.dump({
            'cool_down': True,
            'reason': 'test',
            'timestamp': time.time()
        }, f)
    
    # Test handling
    hook.check(generation=999999)