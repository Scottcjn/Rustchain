#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""CLI entrypoint for ``python -m tools.catalog_provider``."""

import sys

from .daemon import main

if __name__ == "__main__":
    sys.exit(main())
