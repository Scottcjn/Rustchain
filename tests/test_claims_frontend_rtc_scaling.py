"""
Regression test for the claims-page RTC display scaling bug.

`reward_urtc` is denominated in micro-RTC (10^6 units per RTC). The backend
(node/claims_submission.py) converts to human-readable RTC by dividing by
1_000_000 in every place it reports an amount. The frontend `formatRtc()`
helper in web/claims/claims.js must use the *same* divisor, otherwise every
reward shown on the claim page (dropdown, summary, history, stats, success
message, CSV export) is off by 100x.

Concrete input -> output:
    reward_urtc = 1_500_000  (== 1.5 RTC)
    correct   : 1_500_000 / 1_000_000       -> "1.500000"
    buggy     : 1_500_000 / 100_000_000     -> "0.015000"   (100x too small)
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CLAIMS_JS = REPO_ROOT / "web" / "claims" / "claims.js"
CLAIMS_BACKEND = REPO_ROOT / "node" / "claims_submission.py"

MICRO_RTC_PER_RTC = 1_000_000


def _extract_format_rtc_divisor() -> int:
    """Return the integer divisor used inside formatRtc() in claims.js."""
    source = CLAIMS_JS.read_text(encoding="utf-8")
    m = re.search(
        r"function\s+formatRtc\s*\([^)]*\)\s*\{.*?/\s*([0-9_]+)\s*\)",
        source,
        re.DOTALL,
    )
    assert m, "Could not locate the divisor inside formatRtc() in claims.js"
    return int(m.group(1).replace("_", ""))


def test_format_rtc_uses_micro_rtc_divisor():
    assert _extract_format_rtc_divisor() == MICRO_RTC_PER_RTC, (
        "formatRtc() must divide micro-RTC by 1_000_000 to render RTC. "
        "Any other divisor (e.g. 100_000_000) misreports rewards on the claim page."
    )


def test_frontend_divisor_matches_backend_conversion():
    """The frontend divisor must match the backend reward_urtc -> RTC divisor."""
    backend = CLAIMS_BACKEND.read_text(encoding="utf-8")
    backend_divisors = {
        int(d.replace("_", ""))
        for d in re.findall(r"reward_urtc\"?\]?\s*/\s*([0-9_]+)", backend)
    }
    # Backend consistently uses 1_000_000 for reward_urtc conversion.
    assert MICRO_RTC_PER_RTC in backend_divisors, backend_divisors
    assert _extract_format_rtc_divisor() in backend_divisors, (
        "Frontend formatRtc() divisor does not match the backend micro-RTC divisor."
    )


def test_worked_example_1_5_rtc():
    divisor = _extract_format_rtc_divisor()
    assert f"{1_500_000 / divisor:.6f}" == "1.500000"
