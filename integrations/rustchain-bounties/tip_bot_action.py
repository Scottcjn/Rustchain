#!/usr/bin/env python3
"""
tip_bot_action.py — Entry point for the GitHub Action workflow.

Imports and runs the main tip bot from tip_bot.py.
"""

import sys
import os

# Ensure the integration directory is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tip_bot import main

if __name__ == "__main__":
    main()
