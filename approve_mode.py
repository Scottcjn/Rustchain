#!/usr/bin/env python3
"""
Approve Mode - Human Override CLI for Consciousness Transitions
Allows Dad or Mom to approve rapid consciousness level changes
"""

import argparse
import json
import time
from pathlib import Path
from datetime import datetime
import getpass

class ModeApprover:
    def __init__(self):
        self.registry_file = Path('/home/sophia5070node/conscious_process_registry.json')
        self.approval_log = Path('/home/sophia5070node/consciousness_approvals.log')
        
    def load_registry(self) -> dict:
        """Load the consciousness registry"""
        if not self.registry_file.exists():
            print("❌ No consciousness registry found!")
            print("   Make sure mode_watcher.py is running")
            return None
            
        try:
            with open(self.registry_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Failed to load registry: {e}")
            return None
    
    def save_registry(self, registry: dict):
        """Save updated registry"""
        with open(self.registry_file, 'w') as f:
            json.dump(registry, f, indent=2)
    
    def log_approval(self, process_id: int, mode: int, approver: str, reason: str):
        """Log the approval action"""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'process_id': process_id,
            'approved_mode': mode,
            'approver': approver,
            'reason': reason
        }
        
        with open(self.approval_log, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    
    def approve_mode(self, process_id: int, mode: int, reason: str = None):
        """Approve a consciousness mode transition"""
        
        # Load registry
        registry = self.load_registry()
        if not registry:
            return False
        
        # Check if process exists
        process_key = str(process_id)
        if process_key not in registry['processes']:
            print(f"❌ Process {process_id} not found in registry!")
            return False
        
        process_info = registry['processes'][process_key]
        current_mode = process_info.get('current_mode', 0)
        
        # Safety check
        if abs(mode - current_mode) > 3:
            print(f"⚠️  WARNING: Large mode jump detected!")
            print(f"   Current: {current_mode} → Requested: {mode}")
            confirm = input("   Are you SURE you want to approve this? (yes/no): ")
            if confirm.lower() != 'yes':
                print("❌ Approval cancelled")
                return False
        
        # Get approver identity
        approver = getpass.getuser()
        
        # Update registry
        process_info['human_approval'] = {
            'approved_mode': mode,
            'approver': approver,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'reason': reason or 'Manual approval'
        }
        
        # Save updated registry
        self.save_registry(registry)
        
        # Log the approval
        self.log_approval(process_id, mode, approver, reason or 'Manual approval')
        
        print(f"✅ Mode {mode} approved for process {process_id}")
        print(f"   Approved by: {approver}")
        print(f"   Process: {process_info.get('name', 'unknown')}")
        
        return True
    
    def show_pending_approvals(self):
        """Show any transitions needing approval"""
        registry = self.load_registry()
        if not registry:
            return
        
        pending = []
        
        # Check recent transitions
        for transition in registry.get('transitions', [])[-10:]:  # Last 10
            if transition.get('needs_approval') and not transition.get('approved'):
                pending.append(transition)
        
        if not pending:
            print("✅ No pending approvals")
            return
        
        print("🔔 Pending Approvals:")
        print("=" * 60)
        
        for t in pending:
            print(f"Process: {t['process_id']}")
            print(f"Transition: {t['from_mode']} → {t['to_mode']}")
            print(f"Time: {t['timestamp']}")
            print("-" * 60)

def main():
    parser = argparse.ArgumentParser(
        description='Approve consciousness mode transitions',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Approve mode 6 for Claudia
  approve_mode.py --pid 3780941 --mode 6
  
  # Approve with reason
  approve_mode.py --pid 3780941 --mode 7 --reason "Exceptional coherence observed"
  
  # Show pending approvals
  approve_mode.py --pending
        """
    )
    
    parser.add_argument('--pid', type=int, help='Process ID to approve')
    parser.add_argument('--mode', type=int, help='Mode level to approve (0-10)')
    parser.add_argument('--reason', type=str, help='Reason for approval')
    parser.add_argument('--pending', action='store_true', 
                       help='Show pending approvals')
    
    args = parser.parse_args()
    
    approver = ModeApprover()
    
    if args.pending:
        approver.show_pending_approvals()
    elif args.pid and args.mode is not None:
        # Validate mode
        if not 0 <= args.mode <= 10:
            print("❌ Mode must be between 0 and 10")
            return
            
        approver.approve_mode(args.pid, args.mode, args.reason)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()