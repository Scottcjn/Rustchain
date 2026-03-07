"""
rustchainnode — pip-installable RustChain attestation node.

Usage:
    pip install rustchainnode
    rustchainnode init --wallet my-wallet-name
    rustchainnode start

Author: NOX Ventures (noxxxxybot-sketch)
"""

__version__ = "0.1.0"
__author__ = "Elyan Labs / RustChain Contributors"

from .node import RustChainNode

__all__ = ["RustChainNode"]
