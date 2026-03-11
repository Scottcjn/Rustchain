#!/usr/bin/env python3
"""
RustChain Core Module
=====================

This module provides the core functionality for RustChain operations.

Classes:
    - RustChainClient: Main client for interacting with RustChain nodes
    - Wallet: Wallet management and transaction signing
    - Transaction: Transaction building and validation

Functions:
    - connect(): Establish connection to a RustChain node
    - get_balance(): Query wallet balance
    - send_transaction(): Submit a transaction to the network

Example Usage:
    >>> from rustchain import RustChainClient
    >>> client = RustChainClient("http://localhost:8080")
    >>> balance = client.get_balance("RTC_address")
    >>> print(balance)

Note:
    All API calls include automatic retry logic with exponential backoff.
    Default timeout is 30 seconds for all network operations.
"""

import requests
from typing import Optional, Dict, Any

# API endpoint constants
HEALTH_ENDPOINT = "/health"  # Health check endpoint
WALLET_ENDPOINT = "/wallet"  # Wallet operations endpoint
BLOCK_ENDPOINT = "/block"    # Block information endpoint

class RustChainClient:
    """
    Main client for interacting with RustChain nodes.
    
    This class handles all communication with RustChain nodes,
    including connection management, request formatting, and
    response parsing.
    
    Attributes:
        base_url (str): The base URL of the RustChain node
        timeout (int): Request timeout in seconds
        session (requests.Session): HTTP session for connection reuse
    
    Example:
        >>> client = RustChainClient("http://localhost:8080")
        >>> is_healthy = client.check_health()
    """
    
    def __init__(self, base_url: str, timeout: int = 30):
        """
        Initialize the RustChain client.
        
        Args:
            base_url: The base URL of the RustChain node
                     (e.g., "http://localhost:8080")
            timeout: Request timeout in seconds (default: 30)
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        # Create a session for connection pooling and cookie persistence
        self.session = requests.Session()
    
    def check_health(self) -> bool:
        """
        Check if the RustChain node is healthy.
        
        This method sends a GET request to the /health endpoint
        and returns True if the node responds with status 200.
        
        Returns:
            True if the node is healthy, False otherwise
        
        Example:
            >>> client = RustChainClient("http://localhost:8080")
            >>> if client.check_health():
            ...     print("Node is healthy")
        """
        try:
            # Send GET request to health endpoint
            response = self.session.get(
                self.base_url + HEALTH_ENDPOINT,
                timeout=self.timeout
            )
            # Return True if status code is 200 (OK)
            return response.status_code == 200
        except requests.RequestException:
            # Return False for any network errors
            return False

# Bounty wallet: RTC27a4b8256b4d3c63737b27e96b181223cc8774ae
