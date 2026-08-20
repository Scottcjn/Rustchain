"""Self-tests for the falsegreen linter.

A linter with no tests is exactly the "reports success while doing nothing" shape
it exists to catch — so its own behavior is pinned here. Each test asserts BOTH
that a real instance is caught (recall) and that a legitimate pattern is not
(precision). Pure stdlib + pytest.
"""
import subprocess, sys, textwrap
from pathlib import Path

LINT = Path(__file__).with_name("falsegreen.py")


def run(tmp_path, code, *args, name="m.py"):
    f = tmp_path / name
    f.write_text(textwrap.dedent(code))
    r = subprocess.run([sys.executable, str(LINT), str(f), *args],
                       capture_output=True, text=True)
    return r.returncode, r.stdout


# ---- recall: the real bug shapes MUST be caught -------------------------------

def test_except_returns_true(tmp_path):
    rc, out = run(tmp_path, """
        def verify_payment():
            try:
                return api_check()
            except Exception:
                return True
    """)
    assert rc == 1 and "FG001" in out

def test_except_returns_empty_in_evidence_fn(tmp_path):
    rc, out = run(tmp_path, """
        def get_stargazers():
            try:
                return paginate()
            except Exception:
                return []
    """)
    assert rc == 1 and "FG001" in out

def test_or_fallback_fails_open(tmp_path):
    rc, out = run(tmp_path, """
        def check_cap(author):
            elig = api("/search") or {}
            if elig.get("total_count", 0) >= 15:
                return "capped"
            return "ok"
    """)
    assert rc == 1 and "FG005" in out

def test_top_level_swallow(tmp_path):
    rc, out = run(tmp_path, """
        def main():
            do_work()
        try:
            main()
        except Exception as e:
            print(e)
    """)
    assert rc == 1 and "FG001" in out

def test_yaml_continue_on_error(tmp_path):
    rc, out = run(tmp_path, """
        jobs:
          x:
            steps:
              - run: python invariants.py
                continue-on-error: true
    """, name="w.yml")
    assert rc == 1 and "FG003" in out

def test_yaml_or_true(tmp_path):
    rc, out = run(tmp_path, """
        steps:
          - run: gh api thing > report.json 2>&1 || true
    """, name="w.yml")
    assert rc == 1 and "FG003" in out


# ---- precision: legitimate patterns MUST NOT be flagged -----------------------

def test_import_error_is_not_flagged(tmp_path):
    # optional-dependency feature detection is the intended degrade path
    rc, out = run(tmp_path, """
        def get_backend():
            try:
                import fastcodec
                return fastcodec
            except ImportError:
                return None
    """)
    assert rc == 0, out

def test_except_that_reraises_is_ok(tmp_path):
    rc, out = run(tmp_path, """
        def verify():
            try:
                return check()
            except Exception:
                log()
                raise
    """)
    assert rc == 0, out

def test_except_that_exits_nonzero_is_ok(tmp_path):
    rc, out = run(tmp_path, """
        import sys
        def main():
            return run()
        try:
            main()
        except Exception:
            sys.exit(1)
    """)
    assert rc == 0, out

def test_non_evidence_fn_returning_none_not_flagged(tmp_path):
    # a plain helper returning None on except is too weak a signal to flag
    rc, out = run(tmp_path, """
        def render_widget():
            try:
                return build()
            except Exception:
                return None
    """)
    assert rc == 0, out


# ---- the deployment contract: --diff gates only added lines -------------------

def test_diff_mode_ignores_legacy(tmp_path):
    import os
    repo = tmp_path
    def git(*a): subprocess.run(["git", *a], cwd=repo, check=True,
                                capture_output=True)
    git("init"); git("config", "user.email", "t@t"); git("config", "user.name", "t")
    (repo / "svc.py").write_text(textwrap.dedent("""
        def get_balance():
            try:
                return q()
            except Exception:
                return {}
    """))
    git("add", "-A"); git("commit", "-m", "base")
    (repo / "svc.py").write_text(textwrap.dedent("""
        def get_balance():
            try:
                return q()
            except Exception:
                return {}
        def verify_new():
            try:
                return c()
            except Exception:
                return True
    """))
    git("add", "-A"); git("commit", "-m", "feat")
    r = subprocess.run([sys.executable, str(LINT), str(repo / "svc.py"),
                        "--diff", "HEAD~1"], cwd=repo, capture_output=True, text=True)
    # only the NEW one (verify_new) is reported; the legacy get_balance is not
    assert r.returncode == 1
    assert "verify_new" in r.stdout
    assert "get_balance" not in r.stdout
