# SPDX-License-Identifier: MIT
"""CI entry point for the RTC-address header-key binding regression tests.

CI runs ``pytest tests/`` only, so this re-exports the suite that lives next to
the node under ``node/tests/test_header_key_rtc_alias_binding.py`` (attest /
enroll alias binding in every enforcement phase, legacy-pair idempotence, named
alias compatibility, /headers/ingest_signed rejection, and wsgi route wiring).
"""
import importlib.util
import os

_SRC = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "node", "tests", "test_header_key_rtc_alias_binding.py",
)
_spec = importlib.util.spec_from_file_location("node_header_key_rtc_alias_binding", _SRC)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

RtcAliasHeaderKeyBindingTest = _mod.RtcAliasHeaderKeyBindingTest
WsgiRouteRegistrationTest = _mod.WsgiRouteRegistrationTest
