from core.scanner import BountyScanner
from core.executor import BountyExecutor
import os

def run_hunter():
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    TARGET_REPO = "Scottcjn/rustchain-bounties"
    
    print("🦅 Operative Reon: Hunter Framework Engaged.")
    
    scanner = BountyScanner(GITHUB_TOKEN)
    executor = BountyExecutor(TARGET_REPO, GITHUB_TOKEN)
    
    # 1. Scan
    bounties = scanner.find_bounties(TARGET_REPO)
    print(f"🔍 Found {len(bounties)} open bounties.")
    
    for b in bounties:
        diff = scanner.evaluate_difficulty(b)
        print(f"  - [{b['number']}] {b['title']} (Difficulty: {diff}/10)")
        
    print("\n✅ Framework initialized. Ready for autonomous task assignment.")

if __name__ == "__main__":
    run_hunter()
