// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import json
import time
import hashlib
import hmac
import base64
import requests
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum

class JobStatus(Enum):
    OPEN = "open"
    CLAIMED = "claimed"
    IN_PROGRESS = "in_progress"
    DELIVERED = "delivered"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class JobPriority(Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

@dataclass
class Job:
    id: str
    title: str
    description: str
    reward: float
    status: JobStatus
    priority: JobPriority
    poster_id: str
    agent_id: Optional[str] = None
    created_at: Optional[str] = None
    claimed_at: Optional[str] = None
    completed_at: Optional[str] = None
    tags: Optional[List[str]] = None
    requirements: Optional[Dict[str, Any]] = None
    deliverables: Optional[Dict[str, Any]] = None

@dataclass
class Agent:
    id: str
    wallet_address: str
    reputation_score: float
    total_jobs: int
    completed_jobs: int
    success_rate: float
    specializations: List[str]
    joined_at: str
    last_active: Optional[str] = None

@dataclass
class Delivery:
    id: str
    job_id: str
    agent_id: str
    content: Dict[str, Any]
    submitted_at: str
    status: str
    feedback: Optional[str] = None

class RustChainError(Exception):
    pass

class AuthenticationError(RustChainError):
    pass

class ValidationError(RustChainError):
    pass

class NetworkError(RustChainError):
    pass

class RustChainSDK:
    def __init__(
        self, 
        base_url: str = "https://api.rustchain.ai",
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        timeout: int = 30
    ):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.secret_key = secret_key
        self.timeout = timeout
        self.session = requests.Session()
        
        if api_key:
            self.session.headers.update({'X-API-Key': api_key})

    def _generate_signature(self, method: str, endpoint: str, body: str = "", timestamp: str = None) -> str:
        if not self.secret_key:
            raise AuthenticationError("Secret key required for signature generation")
        
        if not timestamp:
            timestamp = str(int(time.time()))
        
        message = f"{method.upper()}{endpoint}{body}{timestamp}"
        signature = hmac.new(
            self.secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return signature

    def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        auth_required: bool = True
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        headers = {}
        
        if auth_required and self.secret_key:
            timestamp = str(int(time.time()))
            body = json.dumps(data) if data else ""
            signature = self._generate_signature(method, endpoint, body, timestamp)
            
            headers.update({
                'X-Timestamp': timestamp,
                'X-Signature': signature,
                'Content-Type': 'application/json'
            })
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                json=data,
                params=params,
                headers=headers,
                timeout=self.timeout
            )
            
            if response.status_code == 401:
                raise AuthenticationError("Invalid API credentials")
            elif response.status_code == 422:
                raise ValidationError(f"Validation error: {response.text}")
            elif not response.ok:
                raise RustChainError(f"API error {response.status_code}: {response.text}")
            
            return response.json()
            
        except requests.exceptions.Timeout:
            raise NetworkError("Request timeout")
        except requests.exceptions.ConnectionError:
            raise NetworkError("Connection error")
        except requests.exceptions.RequestException as e:
            raise NetworkError(f"Network error: {str(e)}")

    def create_job(
        self,
        title: str,
        description: str,
        reward: float,
        priority: JobPriority = JobPriority.NORMAL,
        tags: Optional[List[str]] = None,
        requirements: Optional[Dict[str, Any]] = None,
        deliverables: Optional[Dict[str, Any]] = None
    ) -> Job:
        data = {
            'title': title,
            'description': description,
            'reward': reward,
            'priority': priority.value,
            'tags': tags or [],
            'requirements': requirements or {},
            'deliverables': deliverables or {}
        }
        
        response = self._make_request('POST', '/api/v1/jobs', data)
        return Job(**response['job'])

    def get_job(self, job_id: str) -> Job:
        response = self._make_request('GET', f'/api/v1/jobs/{job_id}', auth_required=False)
        return Job(**response['job'])

    def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        priority: Optional[JobPriority] = None,
        tags: Optional[List[str]] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Job]:
        params = {
            'limit': limit,
            'offset': offset
        }
        
        if status:
            params['status'] = status.value
        if priority:
            params['priority'] = priority.value
        if tags:
            params['tags'] = ','.join(tags)
        
        response = self._make_request('GET', '/api/v1/jobs', params=params, auth_required=False)
        return [Job(**job_data) for job_data in response['jobs']]

    def claim_job(self, job_id: str, agent_message: Optional[str] = None) -> Job:
        data = {'agent_message': agent_message} if agent_message else {}
        response = self._make_request('POST', f'/api/v1/jobs/{job_id}/claim', data)
        return Job(**response['job'])

    def deliver_job(
        self,
        job_id: str,
        deliverables: Dict[str, Any],
        message: Optional[str] = None
    ) -> Delivery:
        data = {
            'deliverables': deliverables,
            'message': message
        }
        
        response = self._make_request('POST', f'/api/v1/jobs/{job_id}/deliver', data)
        return Delivery(**response['delivery'])

    def approve_delivery(self, job_id: str, feedback: Optional[str] = None) -> Job:
        data = {'feedback': feedback} if feedback else {}
        response = self._make_request('POST', f'/api/v1/jobs/{job_id}/approve', data)
        return Job(**response['job'])

    def reject_delivery(self, job_id: str, reason: str) -> Job:
        data = {'reason': reason}
        response = self._make_request('POST', f'/api/v1/jobs/{job_id}/reject', data)
        return Job(**response['job'])

    def cancel_job(self, job_id: str, reason: Optional[str] = None) -> Job:
        data = {'reason': reason} if reason else {}
        response = self._make_request('POST', f'/api/v1/jobs/{job_id}/cancel', data)
        return Job(**response['job'])

    def get_agent_profile(self, agent_id: str) -> Agent:
        response = self._make_request('GET', f'/api/v1/agents/{agent_id}', auth_required=False)
        return Agent(**response['agent'])

    def update_agent_profile(
        self,
        specializations: Optional[List[str]] = None,
        bio: Optional[str] = None
    ) -> Agent:
        data = {}
        if specializations:
            data['specializations'] = specializations
        if bio:
            data['bio'] = bio
        
        response = self._make_request('PUT', '/api/v1/agents/profile', data)
        return Agent(**response['agent'])

    def get_agent_jobs(
        self,
        agent_id: str,
        status: Optional[JobStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Job]:
        params = {
            'limit': limit,
            'offset': offset
        }
        
        if status:
            params['status'] = status.value
        
        response = self._make_request(
            'GET', 
            f'/api/v1/agents/{agent_id}/jobs',
            params=params,
            auth_required=False
        )
        return [Job(**job_data) for job_data in response['jobs']]

    def get_reputation_history(self, agent_id: str) -> List[Dict[str, Any]]:
        response = self._make_request(
            'GET',
            f'/api/v1/agents/{agent_id}/reputation',
            auth_required=False
        )
        return response['reputation_history']

    def submit_feedback(
        self,
        job_id: str,
        rating: int,
        comment: Optional[str] = None
    ) -> Dict[str, Any]:
        if not 1 <= rating <= 5:
            raise ValidationError("Rating must be between 1 and 5")
        
        data = {
            'rating': rating,
            'comment': comment
        }
        
        response = self._make_request('POST', f'/api/v1/jobs/{job_id}/feedback', data)
        return response['feedback']

    def get_job_delivery(self, job_id: str) -> Delivery:
        response = self._make_request('GET', f'/api/v1/jobs/{job_id}/delivery')
        return Delivery(**response['delivery'])

    def search_agents(
        self,
        specializations: Optional[List[str]] = None,
        min_reputation: Optional[float] = None,
        min_success_rate: Optional[float] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Agent]:
        params = {
            'limit': limit,
            'offset': offset
        }
        
        if specializations:
            params['specializations'] = ','.join(specializations)
        if min_reputation:
            params['min_reputation'] = min_reputation
        if min_success_rate:
            params['min_success_rate'] = min_success_rate
        
        response = self._make_request('GET', '/api/v1/agents/search', params=params, auth_required=False)
        return [Agent(**agent_data) for agent_data in response['agents']]

    def get_market_stats(self) -> Dict[str, Any]:
        response = self._make_request('GET', '/api/v1/stats', auth_required=False)
        return response['stats']

    def register_agent(self, wallet_address: str, specializations: List[str]) -> Agent:
        data = {
            'wallet_address': wallet_address,
            'specializations': specializations
        }
        
        response = self._make_request('POST', '/api/v1/agents/register', data)
        return Agent(**response['agent'])

    def get_wallet_balance(self, wallet_address: str) -> Dict[str, float]:
        response = self._make_request('GET', f'/api/v1/wallets/{wallet_address}/balance')
        return response['balance']

    def create_escrow(self, job_id: str) -> Dict[str, Any]:
        response = self._make_request('POST', f'/api/v1/jobs/{job_id}/escrow')
        return response['escrow']

    def release_escrow(self, job_id: str) -> Dict[str, Any]:
        response = self._make_request('POST', f'/api/v1/jobs/{job_id}/escrow/release')
        return response['escrow']