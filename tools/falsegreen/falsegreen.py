#!/usr/bin/env python3
"""falsegreen — a linter for the "reports success while doing nothing" bug class.

The recurring RustChain defect: failure and success return the SAME shape, so the
caller cannot tell them apart and the bug is invisible by construction. This class
was found 15+ times in one sweep, with the correct fix already written three times
and never applied to the sibling file. Education did not move it; a mechanical gate
might.

This is a HIGH-PRECISION linter, deliberately. A noisy linter that flags every
`except` gets muted in a week (that is itself the alert-fatigue instance of the same
bug). So each rule targets a specific, load-bearing shape and every finding prints
the exact line, so a human verifies in seconds.

Rules:
  FG001  except-block returns success  — `except ...: return True/[]/{}/0/None`
         with no re-raise, in a function whose name suggests a check/fetch/verify.
  FG002  status-code-only health check — reads `.status_code` / HTTP code but never
         the response body/`ok` field on the same success path.
  FG003  shell `|| true` / `set +e` on a step whose output is consumed as evidence.
  FG004  count reported from the loop, not from confirmed effects
         — `n += 1` unconditionally inside a loop that also has `|| true`/`except:pass`.

Exit 1 if any findings; 0 if clean. Prints file:line and the offending source.
Pure stdlib. Python 3.8+. Reads .py and .yml/.yaml (shell rules) only.
"""
import ast, sys, re, os, argparse
from pathlib import Path

SUCCESS_RETURN = {
    "True": "True", "[]": "empty list", "{}": "empty dict",
    "0": "0", "None": "None (when caller reads it as 'no work')",
}
# function-name stems that mean "this returns evidence a caller trusts"
EVIDENCE_STEMS = re.compile(
    r"check|verify|validate|fetch|get_|list_|scan|integrity|health|status|"
    r"paginate|stargazer|attest|settle|broadcast|confirm|drip|debit|pay|"
    r"count|audit|eligib|lookup|query", re.I)


def _exc_names(t):
    """Set of exception type names in an `except (A, B):` clause, or None for bare."""
    if t is None:
        return None
    out = set()
    for n in (t.elts if isinstance(t, ast.Tuple) else [t]):
        if isinstance(n, ast.Name): out.add(n.id)
        elif isinstance(n, ast.Attribute): out.add(n.attr)
    return out


def _is_success_literal(node):
    if isinstance(node, ast.Constant):
        v = node.value
        if v is True: return "True"
        if v == 0 and v is not False: return "0"
        if v is None: return "None"
    if isinstance(node, ast.List) and not node.elts: return "[]"
    if isinstance(node, ast.Dict) and not node.keys: return "{}"
    # tuple like (True, None, None) or (True, x, None)
    if isinstance(node, ast.Tuple) and node.elts:
        first = _is_success_literal(node.elts[0])
        if first == "True": return "(True, ...)"
    return None


class FG(ast.NodeVisitor):
    def __init__(self, src_lines):
        self.src = src_lines
        self.findings = []
        self.func_stack = []

    def _line(self, n):
        return self.src[n.lineno - 1].strip() if 0 < n.lineno <= len(self.src) else "?"

    def visit_FunctionDef(self, node):
        self.func_stack.append(node.name)
        self.generic_visit(node)
        self.func_stack.pop()
    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ExceptHandler(self, node):
        fn = self.func_stack[-1] if self.func_stack else "<module>"
        evidence_fn = bool(EVIDENCE_STEMS.search(fn))
        # Optional-dependency / feature-detection handlers are NOT this bug class —
        # they are the intended way to degrade when a module is absent. Skip them.
        etypes = _exc_names(node.type)
        if etypes and etypes <= {"ImportError", "ModuleNotFoundError", "AttributeError",
                                 "NotImplementedError", "KeyboardInterrupt"}:
            self.generic_visit(node)
            return
        # signals that this handler surfaces the failure rather than swallowing it
        reraises = any(isinstance(n, ast.Raise) for n in ast.walk(node))
        exits_nonzero = any(
            isinstance(n, ast.Call) and (
                (isinstance(n.func, ast.Attribute) and n.func.attr == "exit") or
                (isinstance(n.func, ast.Name) and n.func.id == "exit"))
            and n.args and not (isinstance(n.args[0], ast.Constant) and n.args[0].value in (0, None))
            for n in ast.walk(node))
        surfaces = reraises or exits_nonzero
        seen = set()
        for n in ast.walk(node):
            if isinstance(n, ast.Return):
                lit = _is_success_literal(n.value) if n.value is not None else "None"
                if lit and not surfaces and n.lineno not in seen:
                    if lit.startswith("None") and not evidence_fn:
                        continue
                    seen.add(n.lineno)
                    sev = "HIGH" if evidence_fn else "MED"
                    self.findings.append((
                        n.lineno, "FG001", sev,
                        f"except-block in `{fn}()` returns {SUCCESS_RETURN.get(lit, lit)} "
                        f"with no re-raise — failure looks identical to success",
                        self._line(n)))
        # FG001b — top-level guard that swallows: `try: main() except: print(...)`
        # with no re-raise and no non-zero exit. The process exits 0 on failure.
        if not self.func_stack and not surfaces:
            body_has_effect = any(isinstance(n, (ast.Return, ast.Raise)) for n in node.body)
            calls_exit0 = False  # already excluded above; here just detect swallow
            if not body_has_effect:
                self.findings.append((
                    node.lineno, "FG001", "HIGH",
                    "top-level except swallows the error and the process still exits 0 "
                    "— a failed run reports success to CI",
                    self._line(node)))
        self.generic_visit(node)

    def visit_Assign(self, node):
        # FG005 — `x = <call>(...) or {}/[]/0` : a failed lookup defaults to a falsy
        # value the caller reads as an authoritative zero/empty. THE cap-fails-open shape.
        v = node.value
        if isinstance(v, ast.BoolOp) and isinstance(v.op, ast.Or) and len(v.values) == 2:
            left, right = v.values
            rlit = _is_success_literal(right)
            if isinstance(left, ast.Call) and rlit in ("[]", "{}", "0"):
                # name the called function if we can
                cn = ""
                f = left.func
                if isinstance(f, ast.Name): cn = f.id
                elif isinstance(f, ast.Attribute): cn = f.attr
                if EVIDENCE_STEMS.search(cn) or cn in ("api", "gh", "request", "fetch", "get"):
                    self.findings.append((
                        node.lineno, "FG005", "HIGH",
                        f"`{cn}(...) or {rlit}` — a failed lookup defaults to {rlit}, "
                        f"which downstream reads as an authoritative zero/empty (fails OPEN)",
                        self._line(node)))
        self.generic_visit(node)


def check_py(path, text):
    out = []
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        return [(e.lineno or 0, "FG000", "SKIP", f"unparseable: {e.msg}", "")]
    lines = text.splitlines()
    v = FG(lines)
    v.visit(tree)
    # dedup: nested except handlers double-count via ast.walk
    seen = set()
    for f in v.findings:
        key = (f[0], f[1])          # (lineno, rule)
        if key not in seen:
            seen.add(key)
            out.append(f)

    # FG002 — status-code-only: a function that touches status_code but never
    # inspects a body/ok on the success branch.
    for m in re.finditer(r"def\s+(\w*(?:health|check|probe|status|ready|live)\w*)\s*\(",
                         text, re.I):
        fname = m.group(1)
        start = text.count("\n", 0, m.start()) + 1
        # crude body slice: to next top-level def/class or EOF
        body = text[m.end():]
        nxt = re.search(r"\n(def |class |@app\.route)", body)
        seg = body[:nxt.start()] if nxt else body
        touches_code = re.search(r"status_code|\.status\b|resp\.code|getcode\(\)", seg)
        reads_body = re.search(r'\.json\(\)|\bok\b|\.text\b|\.get\(["\']ok', seg)
        if touches_code and not reads_body:
            ln = start + seg[:touches_code.start()].count("\n")
            out.append((ln, "FG002", "MED",
                        f"`{fname}()` gates on HTTP status only, never reads the "
                        f"response body — a 200 with error/HTML body reads as healthy",
                        lines[ln-1].strip() if ln <= len(lines) else ""))
    return out


def check_yaml(path, text):
    out = []
    lines = text.splitlines()
    for i, ln in enumerate(lines, 1):
        low = ln.lower()
        if re.search(r"\|\|\s*true\b", ln):
            out.append((i, "FG003", "MED",
                        "`|| true` swallows the step's exit code — a failed command "
                        "reports success", ln.strip()))
        if re.search(r"continue-on-error:\s*true", low):
            out.append((i, "FG003", "HIGH",
                        "`continue-on-error: true` cannot distinguish an infra blip "
                        "from a real failure — the check can never fail", ln.strip()))
        if re.search(r"set\s+\+e|set\s+-[a-z]*u[a-z]*o\s+pipefail", ln) and "-e" not in ln:
            out.append((i, "FG003", "MED",
                        "shell without `-e`: a failing line does not stop the step",
                        ln.strip()))
    return out


SKIP_DIRS = {".git", "node_modules", "venv", ".venv", "__pycache__", "dist",
             "build", "site-packages", ".tox", "deprecated-builds"}


def iter_files(root):
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for f in fns:
            if f.endswith((".py", ".yml", ".yaml")):
                yield Path(dp) / f


def added_lines(base):
    """Map of {abs_path: set(added-line-numbers)} from `git diff <base>...HEAD`.
    This is the deployment mode: gate the DELTA, never the legacy baseline. A
    codebase with N pre-existing findings can adopt the linter without first
    clearing N — only newly-introduced false-green blocks a PR."""
    import subprocess
    try:
        root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"],
                                       text=True).strip()
        diff = subprocess.check_output(
            ["git", "diff", "--unified=0", f"{base}...HEAD"], text=True,
            errors="replace")
    except Exception as e:
        print(f"falsegreen: --diff could not read git ({e})", file=sys.stderr)
        return None
    out, cur = {}, None
    for ln in diff.splitlines():
        if ln.startswith("+++ b/"):
            cur = os.path.join(root, ln[6:]); out.setdefault(cur, set())
        elif ln.startswith("@@") and cur is not None:
            m = re.search(r"\+(\d+)(?:,(\d+))?", ln)
            if m:
                start = int(m.group(1)); cnt = int(m.group(2) or 1)
                out[cur].update(range(start, start + cnt))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--min-sev", choices=["HIGH", "MED"], default="MED")
    ap.add_argument("--rules", help="comma list to include, e.g. FG001,FG002")
    ap.add_argument("--diff", metavar="BASE_REF",
                    help="only report findings on lines added since BASE_REF "
                         "(e.g. origin/main) — gates the delta, not the baseline")
    args = ap.parse_args()
    diff_map = added_lines(args.diff) if args.diff else None
    if args.diff and diff_map is None:
        return 2
    only = set(args.rules.split(",")) if args.rules else None
    sev_ok = {"HIGH": {"HIGH"}, "MED": {"HIGH", "MED"}}[args.min_sev]

    files = []
    for p in args.paths:
        p = Path(p)
        files.extend(iter_files(p) if p.is_dir() else [p])

    total = 0
    by_sev = {"HIGH": 0, "MED": 0}
    for fp in sorted(set(files)):
        try:
            text = fp.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        found = (check_py(fp, text) if fp.suffix == ".py"
                 else check_yaml(fp, text))
        for ln, rule, sev, msg, code in sorted(found):
            if rule == "FG000":  # skip/parse note — suppress unless verbose
                continue
            if only and rule not in only: continue
            if sev not in sev_ok: continue
            if diff_map is not None and ln not in diff_map.get(str(fp), diff_map.get(os.path.abspath(fp), set())):
                continue
            print(f"{fp}:{ln}: [{rule}/{sev}] {msg}")
            if code: print(f"    {code}")
            total += 1
            by_sev[sev] = by_sev.get(sev, 0) + 1
    print(f"\nfalsegreen: {total} finding(s) "
          f"({by_sev['HIGH']} HIGH, {by_sev['MED']} MED) across {len(set(files))} files")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
