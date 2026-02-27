#!/usr/bin/env python3
"""Dry-run helper for RTC/ERG Spectrum pair checks."""
from integrations.spectrum.client import SpectrumClient

if __name__ == "__main__":
    c = SpectrumClient()
    print(c.get_pair("RTC", "ERG"))
    print(c.get_quote("RTC", "ERG", 1000000))
