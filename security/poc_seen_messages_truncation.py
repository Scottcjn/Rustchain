#!/usr/bin/env python3
"""
PoC: seen_messages Truncation Race — Message Replay
Issue: #2867 — RustChain Security Audit

Vulnerability: seen_messages truncation uses set(list(...)[-5000:]) which
is unreliable because Python sets are unordered. After truncation, recent
message IDs may be lost while old ones remain, enabling message replay.

Code (rustchain_p2p_gossip.py line ~411):
    if len(self.seen_messages) > 10000:
        self.seen_messages = set(list(self.seen_messages)[-5000:])

Severity: MEDIUM (message replay, DoS)

Wallet: zhaog100
"""


def test_seen_messages_truncation():
    """Demonstrate that set(list(set)[-N:]) loses ordering."""
    
    # Simulate the vulnerable code
    seen = set()
    
    # Add 10001 messages
    for i in range(10001):
        seen.add(f"msg_{i:05d}")
    
    print(f"  Before truncation: {len(seen)} messages")
    
    # The vulnerable truncation
    truncated = set(list(seen)[-5000:])
    
    print(f"  After truncation: {len(truncated)} messages")
    
    # Check: are recent messages preserved?
    recent_preserved = 0
    recent_lost = 0
    for i in range(9900, 10001):  # Last 101 messages
        if f"msg_{i:05d}" in truncated:
            recent_preserved += 1
        else:
            recent_lost += 1
    
    print(f"  Recent messages preserved: {recent_preserved}")
    print(f"  Recent messages LOST: {recent_lost}")
    
    if recent_lost > 0:
        print("  ⚠️ VULNERABLE: Recent messages lost after truncation!")
        print("  This enables replay of recent messages after truncation.")
        return True
    else:
        print("  ✓ Safe: All recent messages preserved")
        return False


def test_fix():
    print("\n  Recommended fix:")
    print("""
    # Use OrderedDict or collections.deque for LRU tracking
    from collections import OrderedDict
    
    class SeenMessages:
        def __init__(self, max_size=10000):
            self._messages = OrderedDict()
            self._max_size = max_size
        
        def add(self, msg_id):
            if msg_id in self._messages:
                return False
            self._messages[msg_id] = True
            if len(self._messages) > self._max_size:
                # Remove oldest entries
                for _ in range(self._max_size // 2):
                    self._messages.popitem(last=False)
            return True
        
        def __contains__(self, msg_id):
            return msg_id in self._messages
    """)


if __name__ == "__main__":
    print("=" * 60)
    print("PoC: seen_messages Truncation Race — Message Replay")
    print("Issue: Scottcjn/rustchain-bounties #2867")
    print("=" * 60)
    
    print("\n--- Test: Set Ordering After Truncation ---")
    vuln = test_seen_messages_truncation()
    test_fix()
    
    print("\n" + "=" * 60)
    if vuln:
        print("RESULT: VULNERABLE — Truncation loses recent messages")
    else:
        print("RESULT: Needs runtime verification")
    print("=" * 60)
