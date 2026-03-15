#!/usr/bin/env python3
"""RustChain API Response Validator — Verify API responses match expected schemas."""
import json, urllib.request, ssl, os

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")

SCHEMAS = {
    "/health": {"required": ["status"], "types": {"status": str}},
    "/epoch": {"required": [], "types": {}},
    "/api/miners": {"required": [], "types": {}},
    "/headers/tip": {"required": [], "types": {}},
}

def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try:
        r = urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx)
        return json.loads(r.read()), r.status
    except Exception as e: return {}, 0

def validate():
    print("API Response Validation")
    print("=" * 50)
    passed = failed = 0
    for path, schema in SCHEMAS.items():
        data, status = api(path)
        errors = []
        if status != 200: errors.append(f"HTTP {status}")
        for field in schema["required"]:
            if field not in data: errors.append(f"missing '{field}'")
        for field, typ in schema["types"].items():
            if field in data and not isinstance(data[field], typ):
                errors.append(f"'{field}' wrong type")
        
        if errors:
            print(f"  [FAIL] {path}: {', '.join(errors)}")
            failed += 1
        else:
            print(f"  [PASS] {path}")
            passed += 1
    print(f"\n{passed} passed, {failed} failed")

if __name__ == "__main__":
    validate()
