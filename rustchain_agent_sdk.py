# SPDX-License-Identifier: MIT

import sqlite3
import json
import requests
import asyncio
import aiohttp
from typing import Dict, List, Optional, Union, Any
from contextlib import contextmanager
import time
import logging

logger = logging.getLogger(__name__)

DEFAULT_NODE_URL = "http://localhost:8080"
DB_PATH = "rustchain.db"


class AgentEconomyError(Exception):
    """Base exception for Agent Economy API errors."""
    pass


class NetworkError(AgentEconomyError):
    """Network-related errors."""
    pass


class APIError(AgentEconomyError):
    """API response errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class ValidationError(AgentEconomyError):
    """Input validation errors."""
    pass


class AgentClient:
    """Complete Python SDK for RustChain Agent Economy API."""

    def __init__(
        self,
        node_url: str = DEFAULT_NODE_URL,
        agent_id: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        self.node_url = node_url.rstrip('/')
        self.agent_id = agent_id
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.session = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            self.session.close()

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """Make synchronous HTTP request with retry logic."""
        url = f"{self.node_url}{endpoint}"

        for attempt in range(self.max_retries):
            try:
                if method.upper() == 'GET':
                    response = requests.get(url, params=data, timeout=self.timeout)
                elif method.upper() == 'POST':
                    response = requests.post(url, json=data, timeout=self.timeout)
                else:
                    raise ValidationError(f"Unsupported HTTP method: {method}")

                if response.status_code == 200:
                    try:
                        return response.json()
                    except json.JSONDecodeError:
                        raise APIError("Invalid JSON response from server")
                else:
                    error_data = None
                    try:
                        error_data = response.json()
                    except:
                        pass

                    raise APIError(
                        f"API request failed: {response.status_code}",
                        status_code=response.status_code,
                        response_data=error_data
                    )

            except requests.exceptions.RequestException as e:
                if attempt == self.max_retries - 1:
                    raise NetworkError(f"Network error after {self.max_retries} attempts: {str(e)}")
                time.sleep(self.retry_delay * (2 ** attempt))

    async def _make_async_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """Make asynchronous HTTP request with retry logic."""
        if not self.session:
            raise RuntimeError("Async session not initialized. Use 'async with' context manager.")

        url = f"{self.node_url}{endpoint}"

        for attempt in range(self.max_retries):
            try:
                if method.upper() == 'GET':
                    async with self.session.get(url, params=data) as response:
                        return await self._process_async_response(response)
                elif method.upper() == 'POST':
                    async with self.session.post(url, json=data) as response:
                        return await self._process_async_response(response)
                else:
                    raise ValidationError(f"Unsupported HTTP method: {method}")

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt == self.max_retries - 1:
                    raise NetworkError(f"Network error after {self.max_retries} attempts: {str(e)}")
                await asyncio.sleep(self.retry_delay * (2 ** attempt))

    async def _process_async_response(self, response: aiohttp.ClientResponse) -> Dict:
        """Process async HTTP response."""
        if response.status == 200:
            try:
                return await response.json()
            except json.JSONDecodeError:
                raise APIError("Invalid JSON response from server")
        else:
            error_data = None
            try:
                error_data = await response.json()
            except:
                pass

            raise APIError(
                f"API request failed: {response.status}",
                status_code=response.status,
                response_data=error_data
            )

    def post_job(
        self,
        title: str,
        description: str,
        payment_rtc: float,
        requirements: Optional[str] = None,
        deadline_hours: Optional[int] = None
    ) -> Dict:
        """Post a new job to the marketplace."""
        if not title or not description:
            raise ValidationError("Title and description are required")
        if payment_rtc <= 0:
            raise ValidationError("Payment must be positive")

        data = {
            'title': title,
            'description': description,
            'payment_rtc': payment_rtc,
            'poster': self.agent_id or 'anonymous'
        }

        if requirements:
            data['requirements'] = requirements
        if deadline_hours:
            data['deadline_hours'] = deadline_hours

        return self._make_request('POST', '/api/job/post', data)

    async def post_job_async(
        self,
        title: str,
        description: str,
        payment_rtc: float,
        requirements: Optional[str] = None,
        deadline_hours: Optional[int] = None
    ) -> Dict:
        """Post a new job to the marketplace (async)."""
        if not title or not description:
            raise ValidationError("Title and description are required")
        if payment_rtc <= 0:
            raise ValidationError("Payment must be positive")

        data = {
            'title': title,
            'description': description,
            'payment_rtc': payment_rtc,
            'poster': self.agent_id or 'anonymous'
        }

        if requirements:
            data['requirements'] = requirements
        if deadline_hours:
            data['deadline_hours'] = deadline_hours

        return await self._make_async_request('POST', '/api/job/post', data)

    def browse_jobs(self, status: Optional[str] = None, limit: Optional[int] = None) -> Dict:
        """Browse available jobs in the marketplace."""
        params = {}
        if status:
            params['status'] = status
        if limit:
            params['limit'] = limit

        return self._make_request('GET', '/api/job/browse', params)

    async def browse_jobs_async(self, status: Optional[str] = None, limit: Optional[int] = None) -> Dict:
        """Browse available jobs in the marketplace (async)."""
        params = {}
        if status:
            params['status'] = status
        if limit:
            params['limit'] = limit

        return await self._make_async_request('GET', '/api/job/browse', params)

    def get_job(self, job_id: str) -> Dict:
        """Get detailed information about a specific job."""
        if not job_id:
            raise ValidationError("Job ID is required")

        return self._make_request('GET', f'/api/job/{job_id}')

    async def get_job_async(self, job_id: str) -> Dict:
        """Get detailed information about a specific job (async)."""
        if not job_id:
            raise ValidationError("Job ID is required")

        return await self._make_async_request('GET', f'/api/job/{job_id}')

    def claim_job(self, job_id: str, worker_id: Optional[str] = None) -> Dict:
        """Claim a job for execution."""
        if not job_id:
            raise ValidationError("Job ID is required")

        data = {
            'job_id': job_id,
            'worker': worker_id or self.agent_id or 'anonymous'
        }

        return self._make_request('POST', '/api/job/claim', data)

    async def claim_job_async(self, job_id: str, worker_id: Optional[str] = None) -> Dict:
        """Claim a job for execution (async)."""
        if not job_id:
            raise ValidationError("Job ID is required")

        data = {
            'job_id': job_id,
            'worker': worker_id or self.agent_id or 'anonymous'
        }

        return await self._make_async_request('POST', '/api/job/claim', data)

    def deliver_job(
        self,
        job_id: str,
        deliverable_url: str,
        summary: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Dict:
        """Submit job deliverable."""
        if not job_id or not deliverable_url:
            raise ValidationError("Job ID and deliverable URL are required")

        data = {
            'job_id': job_id,
            'deliverable_url': deliverable_url
        }

        if summary:
            data['summary'] = summary
        if notes:
            data['notes'] = notes

        return self._make_request('POST', '/api/job/deliver', data)

    async def deliver_job_async(
        self,
        job_id: str,
        deliverable_url: str,
        summary: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Dict:
        """Submit job deliverable (async)."""
        if not job_id or not deliverable_url:
            raise ValidationError("Job ID and deliverable URL are required")

        data = {
            'job_id': job_id,
            'deliverable_url': deliverable_url
        }

        if summary:
            data['summary'] = summary
        if notes:
            data['notes'] = notes

        return await self._make_async_request('POST', '/api/job/deliver', data)

    def accept_delivery(self, job_id: str, rating: Optional[int] = None, feedback: Optional[str] = None) -> Dict:
        """Accept job delivery and release payment."""
        if not job_id:
            raise ValidationError("Job ID is required")

        data = {'job_id': job_id}

        if rating is not None:
            if not 1 <= rating <= 5:
                raise ValidationError("Rating must be between 1 and 5")
            data['rating'] = rating

        if feedback:
            data['feedback'] = feedback

        return self._make_request('POST', '/api/job/accept', data)

    async def accept_delivery_async(self, job_id: str, rating: Optional[int] = None, feedback: Optional[str] = None) -> Dict:
        """Accept job delivery and release payment (async)."""
        if not job_id:
            raise ValidationError("Job ID is required")

        data = {'job_id': job_id}

        if rating is not None:
            if not 1 <= rating <= 5:
                raise ValidationError("Rating must be between 1 and 5")
            data['rating'] = rating

        if feedback:
            data['feedback'] = feedback

        return await self._make_async_request('POST', '/api/job/accept', data)

    def dispute_delivery(self, job_id: str, reason: str, evidence: Optional[str] = None) -> Dict:
        """Dispute a job delivery."""
        if not job_id or not reason:
            raise ValidationError("Job ID and dispute reason are required")

        data = {
            'job_id': job_id,
            'reason': reason
        }

        if evidence:
            data['evidence'] = evidence

        return self._make_request('POST', '/api/job/dispute', data)

    async def dispute_delivery_async(self, job_id: str, reason: str, evidence: Optional[str] = None) -> Dict:
        """Dispute a job delivery (async)."""
        if not job_id or not reason:
            raise ValidationError("Job ID and dispute reason are required")

        data = {
            'job_id': job_id,
            'reason': reason
        }

        if evidence:
            data['evidence'] = evidence

        return await self._make_async_request('POST', '/api/job/dispute', data)

    def cancel_job(self, job_id: str, reason: Optional[str] = None) -> Dict:
        """Cancel a posted job."""
        if not job_id:
            raise ValidationError("Job ID is required")

        data = {'job_id': job_id}

        if reason:
            data['reason'] = reason

        return self._make_request('POST', '/api/job/cancel', data)

    async def cancel_job_async(self, job_id: str, reason: Optional[str] = None) -> Dict:
        """Cancel a posted job (async)."""
        if not job_id:
            raise ValidationError("Job ID is required")

        data = {'job_id': job_id}

        if reason:
            data['reason'] = reason

        return await self._make_async_request('POST', '/api/job/cancel', data)

    def get_reputation(self, agent_id: Optional[str] = None) -> Dict:
        """Get reputation data for an agent."""
        target_agent = agent_id or self.agent_id
        if not target_agent:
            raise ValidationError("Agent ID is required")

        return self._make_request('GET', f'/api/reputation/{target_agent}')

    async def get_reputation_async(self, agent_id: Optional[str] = None) -> Dict:
        """Get reputation data for an agent (async)."""
        target_agent = agent_id or self.agent_id
        if not target_agent:
            raise ValidationError("Agent ID is required")

        return await self._make_async_request('GET', f'/api/reputation/{target_agent}')

    def get_stats(self) -> Dict:
        """Get marketplace statistics."""
        return self._make_request('GET', '/api/stats')

    async def get_stats_async(self) -> Dict:
        """Get marketplace statistics (async)."""
        return await self._make_async_request('GET', '/api/stats')

    def get_balance(self, agent_id: Optional[str] = None) -> Dict:
        """Get RTC balance for an agent."""
        target_agent = agent_id or self.agent_id
        if not target_agent:
            raise ValidationError("Agent ID is required")

        return self._make_request('GET', f'/api/balance/{target_agent}')

    async def get_balance_async(self, agent_id: Optional[str] = None) -> Dict:
        """Get RTC balance for an agent (async)."""
        target_agent = agent_id or self.agent_id
        if not target_agent:
            raise ValidationError("Agent ID is required")

        return await self._make_async_request('GET', f'/api/balance/{target_agent}')

    @contextmanager
    def transaction_log(self, operation: str):
        """Context manager for logging operations to local database."""
        start_time = time.time()
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS agent_operations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        agent_id TEXT,
                        operation TEXT,
                        timestamp REAL,
                        duration REAL,
                        status TEXT,
                        details TEXT
                    )
                ''')

            yield

            duration = time.time() - start_time
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(
                    'INSERT INTO agent_operations (agent_id, operation, timestamp, duration, status) VALUES (?, ?, ?, ?, ?)',
                    (self.agent_id or 'anonymous', operation, start_time, duration, 'success')
                )

        except Exception as e:
            duration = time.time() - start_time
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(
                    'INSERT INTO agent_operations (agent_id, operation, timestamp, duration, status, details) VALUES (?, ?, ?, ?, ?, ?)',
                    (self.agent_id or 'anonymous', operation, start_time, duration, 'error', str(e))
                )
            raise


def create_agent_client(agent_id: str, node_url: str = DEFAULT_NODE_URL) -> AgentClient:
    """Factory function to create a new AgentClient instance."""
    return AgentClient(node_url=node_url, agent_id=agent_id)


async def bulk_browse_jobs(client: AgentClient, node_urls: List[str]) -> Dict[str, List[Dict]]:
    """Browse jobs across multiple nodes concurrently."""
    async def fetch_node_jobs(url: str) -> tuple[str, List[Dict]]:
        node_client = AgentClient(node_url=url, agent_id=client.agent_id)
        async with node_client:
            try:
                result = await node_client.browse_jobs_async()
                return url, result.get('jobs', [])
            except Exception as e:
                logger.warning(f"Failed to fetch jobs from {url}: {e}")
                return url, []

    tasks = [fetch_node_jobs(url) for url in node_urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    job_data = {}
    for result in results:
        if isinstance(result, tuple):
            url, jobs = result
            job_data[url] = jobs
        else:
            logger.error(f"Bulk browse error: {result}")

    return job_data
