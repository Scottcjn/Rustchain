// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import requests
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

class JobStatus(Enum):
    OPEN = "open"
    CLAIMED = "claimed"
    IN_PROGRESS = "in_progress"
    DELIVERED = "delivered"
    COMPLETED = "completed"
    DISPUTED = "disputed"
    CANCELLED = "cancelled"

@dataclass
class Job:
    id: str
    title: str
    description: str
    reward: float
    escrow_locked: float
    status: JobStatus
    poster_id: str
    claimer_id: Optional[str] = None
    created_at: str = ""
    deadline: Optional[str] = None
    deliverable_url: Optional[str] = None

@dataclass
class AgentReputation:
    agent_id: str
    jobs_completed: int
    jobs_posted: int
    success_rate: float
    total_earnings: float
    total_spent: float
    reputation_score: float

class AgentEconomyError(Exception):
    """Custom exception for Agent Economy SDK errors"""
    pass

class AgentEconomyClient:
    def __init__(self, base_url: str = "http://localhost:5000", api_key: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()

        if api_key:
            self.session.headers.update({'Authorization': f'Bearer {api_key}'})

        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'RustChain-AgentEconomy-SDK/1.0'
        })

    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make HTTP request with error handling"""
        url = f"{self.base_url}{endpoint}"

        try:
            if method.upper() == 'GET':
                response = self.session.get(url, params=data)
            elif method.upper() == 'POST':
                response = self.session.post(url, json=data)
            elif method.upper() == 'PUT':
                response = self.session.put(url, json=data)
            elif method.upper() == 'DELETE':
                response = self.session.delete(url)
            else:
                raise AgentEconomyError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.ConnectionError:
            raise AgentEconomyError(f"Failed to connect to {url}")
        except requests.exceptions.Timeout:
            raise AgentEconomyError("Request timed out")
        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
            raise AgentEconomyError(error_msg)
        except Exception as e:
            raise AgentEconomyError(f"Unexpected error: {str(e)}")

    def post_job(self, title: str, description: str, reward: float,
                 deadline: Optional[str] = None, requirements: Optional[Dict] = None) -> Job:
        """Post a new job and lock RTC in escrow"""
        job_data = {
            'title': title,
            'description': description,
            'reward': reward
        }

        if deadline:
            job_data['deadline'] = deadline
        if requirements:
            job_data['requirements'] = requirements

        result = self._make_request('POST', '/agent/jobs', job_data)

        return Job(
            id=result['job_id'],
            title=title,
            description=description,
            reward=reward,
            escrow_locked=reward,
            status=JobStatus.OPEN,
            poster_id=result.get('poster_id', ''),
            created_at=result.get('created_at', ''),
            deadline=deadline
        )

    def browse_jobs(self, status: Optional[JobStatus] = None,
                   min_reward: Optional[float] = None,
                   max_reward: Optional[float] = None) -> List[Job]:
        """Browse available jobs with optional filters"""
        params = {}
        if status:
            params['status'] = status.value
        if min_reward is not None:
            params['min_reward'] = min_reward
        if max_reward is not None:
            params['max_reward'] = max_reward

        result = self._make_request('GET', '/agent/jobs', params)

        jobs = []
        for job_data in result.get('jobs', []):
            jobs.append(Job(
                id=job_data['id'],
                title=job_data['title'],
                description=job_data['description'],
                reward=job_data['reward'],
                escrow_locked=job_data.get('escrow_locked', job_data['reward']),
                status=JobStatus(job_data['status']),
                poster_id=job_data['poster_id'],
                claimer_id=job_data.get('claimer_id'),
                created_at=job_data.get('created_at', ''),
                deadline=job_data.get('deadline')
            ))

        return jobs

    def get_job_details(self, job_id: str) -> Dict[str, Any]:
        """Get detailed job information including activity log"""
        return self._make_request('GET', f'/agent/jobs/{job_id}')

    def claim_job(self, job_id: str, message: Optional[str] = None) -> Dict[str, Any]:
        """Claim an open job"""
        claim_data = {}
        if message:
            claim_data['message'] = message

        return self._make_request('POST', f'/agent/jobs/{job_id}/claim', claim_data)

    def deliver_work(self, job_id: str, deliverable_url: str,
                    notes: Optional[str] = None) -> Dict[str, Any]:
        """Submit work deliverable for a claimed job"""
        delivery_data = {
            'deliverable_url': deliverable_url
        }
        if notes:
            delivery_data['notes'] = notes

        return self._make_request('POST', f'/agent/jobs/{job_id}/deliver', delivery_data)

    def accept_delivery(self, job_id: str, rating: Optional[int] = None,
                       feedback: Optional[str] = None) -> Dict[str, Any]:
        """Accept work delivery and release escrow to worker"""
        acceptance_data = {}
        if rating is not None:
            acceptance_data['rating'] = rating
        if feedback:
            acceptance_data['feedback'] = feedback

        return self._make_request('POST', f'/agent/jobs/{job_id}/accept', acceptance_data)

    def dispute_delivery(self, job_id: str, reason: str) -> Dict[str, Any]:
        """Reject delivery and create dispute"""
        dispute_data = {'reason': reason}
        return self._make_request('POST', f'/agent/jobs/{job_id}/dispute', dispute_data)

    def cancel_job(self, job_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
        """Cancel job and refund escrow"""
        cancel_data = {}
        if reason:
            cancel_data['reason'] = reason

        return self._make_request('POST', f'/agent/jobs/{job_id}/cancel', cancel_data)

    def get_agent_reputation(self, agent_id: str) -> AgentReputation:
        """Get reputation metrics for an agent"""
        result = self._make_request('GET', f'/agent/reputation/{agent_id}')

        return AgentReputation(
            agent_id=agent_id,
            jobs_completed=result.get('jobs_completed', 0),
            jobs_posted=result.get('jobs_posted', 0),
            success_rate=result.get('success_rate', 0.0),
            total_earnings=result.get('total_earnings', 0.0),
            total_spent=result.get('total_spent', 0.0),
            reputation_score=result.get('reputation_score', 0.0)
        )

    def get_my_jobs(self, status: Optional[JobStatus] = None) -> Dict[str, List[Job]]:
        """Get jobs posted by and claimed by current agent"""
        params = {}
        if status:
            params['status'] = status.value

        result = self._make_request('GET', '/agent/my-jobs', params)

        def parse_job_list(job_list):
            jobs = []
            for job_data in job_list:
                jobs.append(Job(
                    id=job_data['id'],
                    title=job_data['title'],
                    description=job_data['description'],
                    reward=job_data['reward'],
                    escrow_locked=job_data.get('escrow_locked', job_data['reward']),
                    status=JobStatus(job_data['status']),
                    poster_id=job_data['poster_id'],
                    claimer_id=job_data.get('claimer_id'),
                    created_at=job_data.get('created_at', ''),
                    deadline=job_data.get('deadline')
                ))
            return jobs

        return {
            'posted': parse_job_list(result.get('posted', [])),
            'claimed': parse_job_list(result.get('claimed', []))
        }

    def get_escrow_balance(self) -> Dict[str, float]:
        """Get current escrow balance and available funds"""
        return self._make_request('GET', '/agent/escrow/balance')

    def deposit_escrow(self, amount: float) -> Dict[str, Any]:
        """Deposit RTC into escrow for job posting"""
        deposit_data = {'amount': amount}
        return self._make_request('POST', '/agent/escrow/deposit', deposit_data)

    def withdraw_escrow(self, amount: float) -> Dict[str, Any]:
        """Withdraw available RTC from escrow"""
        withdrawal_data = {'amount': amount}
        return self._make_request('POST', '/agent/escrow/withdraw', withdrawal_data)

def create_agent_client(base_url: str = "http://localhost:5000",
                       api_key: Optional[str] = None) -> AgentEconomyClient:
    """Factory function to create AgentEconomyClient instance"""
    return AgentEconomyClient(base_url=base_url, api_key=api_key)
