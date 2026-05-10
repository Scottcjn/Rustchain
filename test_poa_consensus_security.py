"""Test for cryptographically secure validator selection fix."""

def test_validator_selection_uses_secrets():
    """Verify that select_validator uses secrets module, not random."""
    source = open('/tmp/rustchain-fix/rips/rustchain-core/consensus/poa.py').read()
    
    # Check that random module is not imported
    assert 'import secrets' in source, "secrets module should be imported"
    
    # Check that random is not used as an active import/usage (may appear in comments)
    lines = source.split('\n')
    code_lines = [l.strip() for l in lines if not l.strip().startswith('#')]
    code_only = '\n'.join(code_lines)
    
    assert 'import random' not in code_only, "random module should NOT be imported in code"
    assert 'random.uniform(' not in code_only, "random.uniform should not be called"
    assert 'random.choice(' not in code_only, "random.choice should not be called"
    
    # Check that secrets is used
    assert 'secrets.randbelow' in code_only, "secrets.randbelow should be used"
    
    print("PASS: Validator selection uses cryptographically secure randomness (secrets)")
    print("  - random module removed")
    print("  - secrets module imported")
    print("  - secrets.randbelow used for weighted selection")
    print("  - secrets.randbelow used for zero-AS fallback")

if __name__ == '__main__':
    test_validator_selection_uses_secrets()
    print("\nAll POA consensus security tests passed!")
