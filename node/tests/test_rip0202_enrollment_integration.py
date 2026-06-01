#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""RIP-202 B1 — INTEGRATION tests against the REAL anti-VM policy.

The B1 unit tests (test_rip0202_enrollment.py) use injected mock derive_fn /
weight_table. This suite closes the gap the module docstring flags:

    "wire the REAL derive_verified_device + HARDWARE_WEIGHTS and add integration
     tests over real committed shapes"

`derive_verified_device` lives in the giant Flask node file and can't be
imported directly (module-level app/DB/thread side effects). We instead extract
ONLY `derive_verified_device` + `HARDWARE_WEIGHTS` and their transitive
top-level dependency closure via AST, exec them in an isolated namespace, and
drive the real B1 pipeline with them. No Flask app, no DB, no network.

Key property proved: derive_block_enrollment(atts, REAL_derive, REAL_weights)
== an independent direct application of the same real functions — for arbitrary
device fixtures — so the wiring is correct without hardcoding classifications.
Plus the anti-VM invariants (failed fingerprint excluded) and snapshot
determinism / order-independence.
"""
import ast
import io
import os
import sys
import contextlib

# Path-robust: works in repo node/tests/ (module + node file live in ../) and in
# a flat staging dir (everything alongside this file).
_HERE = os.path.dirname(os.path.abspath(__file__))
for _d in (os.path.dirname(_HERE), _HERE):  # ../ first (repo layout), then .
    if os.path.exists(os.path.join(_d, "rip0202_enrollment.py")):
        sys.path.insert(0, _d)
        break
import rip0202_enrollment as b1  # noqa: E402


def _find_node_file():
    if os.environ.get("RC_NODE_FILE"):
        return os.environ["RC_NODE_FILE"]
    name = "rustchain_v2_integrated_v2.2.1_rip200.py"
    for d in (os.path.dirname(_HERE), _HERE):
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    raise FileNotFoundError(f"{name} not found near {_HERE}; set RC_NODE_FILE")


NODE_FILE = _find_node_file()


def _extract_real_funcs(node_src):
    """AST-extract derive_verified_device + HARDWARE_WEIGHTS + their top-level
    dependency closure into an isolated namespace (no module-level side effects)."""
    tree = ast.parse(node_src)
    func_defs, assigns, imports = {}, {}, []
    import_names = {}  # bound-name -> import stmt
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append(node)
            for alias in node.names:
                import_names[(alias.asname or alias.name).split(".")[0]] = node
        elif isinstance(node, ast.FunctionDef):
            func_defs[node.name] = node
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    assigns[t.id] = node

    defs = {**assigns, **func_defs}  # name -> defining node
    seeds = ["derive_verified_device", "HARDWARE_WEIGHTS"]
    needed, stack = set(), list(seeds)
    while stack:
        name = stack.pop()
        if name in needed or name not in defs:
            continue
        needed.add(name)
        for n in ast.walk(defs[name]):
            if isinstance(n, ast.Name) and n.id in defs and n.id not in needed:
                stack.append(n.id)

    # imports actually referenced by the closure (avoid importing flask etc.)
    referenced = set()
    for name in needed:
        for n in ast.walk(defs[name]):
            if isinstance(n, ast.Name):
                referenced.add(n.id)
            elif isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name):
                referenced.add(n.value.id)
    used_imports = []
    seen = set()
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            keep = any((a.asname or a.name).split(".")[0] in referenced for a in node.names)
            if keep and id(node) not in seen:
                used_imports.append(node)
                seen.add(id(node))

    body = list(used_imports)
    # preserve original source order for the needed defs
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in needed:
            body.append(node)
        elif isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id in needed for t in node.targets
        ):
            body.append(node)

    mod = ast.Module(body=body, type_ignores=[])
    ast.fix_missing_locations(mod)
    code = compile(mod, NODE_FILE, "exec")
    ns = {}
    with contextlib.redirect_stdout(io.StringIO()):  # swallow [DERIVE_DEBUG] prints
        exec(code, ns)
    return ns["derive_verified_device"], ns["HARDWARE_WEIGHTS"]


# Load once.
REAL_DERIVE, REAL_WEIGHTS = _extract_real_funcs(open(NODE_FILE).read())


def _silenced(fn):
    def wrapped(*a, **k):
        with contextlib.redirect_stdout(io.StringIO()):
            return fn(*a, **k)
    return wrapped


DERIVE = _silenced(REAL_DERIVE)

# ---- representative committed-attestation fixtures (B0 shape) --------------
def _att(miner, device, fp_passed=True, ts=1000, fingerprint=None):
    return {
        "miner": miner,
        "device": device,
        "fingerprint": fingerprint if fingerprint is not None else {"simd_identity": {}},
        "fingerprint_passed": fp_passed,
        "timestamp": ts,
    }


MODERN_X86 = {"machine": "x86_64", "cpu_brand": "Intel(R) Core(TM) i7-8700K",
              "platform_system": "Linux"}
WINDOWS = {"machine": "AMD64", "cpu_brand": "Intel64 Family 6 Model 42 Stepping 7",
           "platform_system": "Windows", "platform_machine": "AMD64"}
VM_LIKE = {"machine": "x86_64", "cpu_brand": "QEMU Virtual CPU", "platform_system": "Linux"}


def test_extraction_loaded_real_objects():
    assert callable(REAL_DERIVE)
    assert isinstance(REAL_WEIGHTS, dict) and "PowerPC" in REAL_WEIGHTS
    # sanity: the real table carries the known ladder
    assert REAL_WEIGHTS["PowerPC"]["G4"] == 2.5
    assert REAL_WEIGHTS["ARM"]["aarch64"] == 0.0005


def test_failed_fingerprint_excluded_regardless_of_device():
    """Anti-VM core: fingerprint_passed != True -> 0 units, independent of arch."""
    for dev in (MODERN_X86, WINDOWS, VM_LIKE):
        enr = b1.derive_block_enrollment(
            [_att("m", dev, fp_passed=False)], DERIVE, REAL_WEIGHTS
        )
        assert enr["m"] == 0, f"failed-fp should be excluded for {dev}"
        assert b1.eligible_miners(enr) == []


def test_pipeline_equals_direct_real_computation():
    """B1 pipeline == independent direct application of the REAL functions,
    for arbitrary devices — proves the wiring with no hardcoded classifications."""
    atts = [
        _att("x86-1", MODERN_X86, ts=10),
        _att("win-1", WINDOWS, ts=20),
        _att("vm-1", VM_LIKE, fp_passed=False, ts=30),
        _att("x86-2", MODERN_X86, ts=40),
    ]
    got = b1.derive_block_enrollment(atts, DERIVE, REAL_WEIGHTS)

    # independent direct computation using the SAME real functions
    expect = {}
    for a in atts:
        if a["fingerprint_passed"] is not True:
            expect[a["miner"]] = 0
            continue
        v = DERIVE(a["device"], a["fingerprint"], True)
        fam, arch = v.get("device_family", ""), v.get("device_arch", "")
        fam_tbl = REAL_WEIGHTS.get(fam, {})
        w = fam_tbl.get(arch, fam_tbl.get("default", 0.0)) if fam else 0.0
        expect[a["miner"]] = b1.to_weight_units(w)
    assert got == expect


def test_real_hardware_is_eligible():
    """A clean modern-x86 attestation derives to a known family with positive
    weight -> eligible (eligibility, not reward magnitude)."""
    enr = b1.derive_block_enrollment([_att("x86", MODERN_X86)], DERIVE, REAL_WEIGHTS)
    assert enr["x86"] > 0
    assert "x86" in b1.eligible_miners(enr)


def test_snapshot_hash_deterministic_and_order_independent():
    a = _att("alpha", MODERN_X86, ts=1)
    b = _att("bravo", WINDOWS, ts=2)
    c = _att("char", VM_LIKE, fp_passed=False, ts=3)
    e1 = b1.derive_block_enrollment([a, b, c], DERIVE, REAL_WEIGHTS)
    e2 = b1.derive_block_enrollment([c, b, a], DERIVE, REAL_WEIGHTS)  # shuffled
    assert e1 == e2
    h1 = b1.enrollment_snapshot_hash(e1)
    h2 = b1.enrollment_snapshot_hash(e2)
    assert h1 == h2 and len(h1) == 64


def test_duplicate_miner_resolves_deterministically():
    """Same miner, two attestations -> last-in-total-order wins, identically
    regardless of input order (no fork from duplicate handling)."""
    older = _att("dup", VM_LIKE, fp_passed=False, ts=100)   # -> 0
    newer = _att("dup", MODERN_X86, fp_passed=True, ts=200)  # -> >0
    e_fwd = b1.derive_block_enrollment([older, newer], DERIVE, REAL_WEIGHTS)
    e_rev = b1.derive_block_enrollment([newer, older], DERIVE, REAL_WEIGHTS)
    assert e_fwd == e_rev
    assert e_fwd["dup"] > 0  # newer timestamp wins
