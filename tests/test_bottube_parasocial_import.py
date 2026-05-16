# SPDX-License-Identifier: MIT
"""Regression coverage for importing the BoTTube parasocial package."""

import sys
from pathlib import Path


def test_bottube_parasocial_package_import_and_factory():
    integrations_dir = Path(__file__).resolve().parents[1] / "integrations"
    sys.path.insert(0, str(integrations_dir))
    original_module = sys.modules.pop("bottube_parasocial", None)
    try:
        import bottube_parasocial

        agent = bottube_parasocial.create_parasocial_agent("agent-1")
    finally:
        sys.modules.pop("bottube_parasocial", None)
        if original_module is not None:
            sys.modules["bottube_parasocial"] = original_module
        sys.path.remove(str(integrations_dir))

    assert set(agent) == {"tracker", "responder", "description_generator"}
