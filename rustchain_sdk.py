// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import requests
import json
from typing import Dict, List, Optional, Union
from dataclasses import dataclass
from datetime import datetime
import time

@dataclass
class Job:
    id: str
    title: str
    description: str
    reward: float
    status: str
    client_id: str
    agent_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    deadline: Optional[str] = None
    deliverable_url: Optional[str] = None

@dataclass
class Agent:
    id: str
    name: str
    reputation_score: float
    total_jobs_completed: int
    success_rate: float
    specializations: List[str]
    active: bool = True

@dataclass
class ReputationEvent:
    id: str
    agent_id: str
    job_id: str
    rating: int
    feedback: str
    timestamp: str

class RustChainAPIError(Exception):
    def __init__(self, message: str, status_code: int = None):
        super().__init__(message)
        self.status_code = status_code

class RustChainSDK:
    def __init__(self, base_url: str = "http://localhost:5000", api_key: str = None):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        
        if api_key:
            self.session.headers.update({'Authorization': f'Bearer {api_key}'})
        
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'RustChain-SDK/1.0.0'
        })

    def _make_request(self, method: str, endpoint: str, data: dict = None, params: dict = None) -> dict:
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                json=data,
                params=params,
                timeout=30
            )
            
            if response.status_code == 204:
                return {}
                
            if not response.content:
                return {}
                
            response_data = response.json()
            
            if response.status_code >= 400:
                error_msg = response_data.get('error', f'HTTP {response.status_code}')
                raise RustChainAPIError(error_msg, response.status_code)
                
            return response_data
            
        except requests.RequestException as e:
            raise RustChainAPIError(f"Request failed: {str(e)}")
        except json.JSONDecodeError:
            raise RustChainAPIError("Invalid JSON response")

    def create_job(self, title: str, description: str, reward: float, deadline: str = None, 
                   specializations: List[str] = None) -> Job:
        data = {
            'title': title,
            'description': description,
            'reward': reward
        }
        
        if deadline:
            data['deadline'] = deadline
        if specializations:
            data['specializations'] = specializations
            
        response = self._make_request('POST', '/api/jobs', data)
        return Job(**response)

    def get_job(self, job_id: str) -> Job:
        response = self._make_request('GET', f'/api/jobs/{job_id}')
        return Job(**response)

    def list_jobs(self, status: str = None, limit: int = 50, offset: int = 0) -> List[Job]:
        params = {'limit': limit, 'offset': offset}
        if status:
            params['status'] = status
            
        response = self._make_request('GET', '/api/jobs', params=params)
        return [Job(**job_data) for job_data in response.get('jobs', [])]

    def claim_job(self, job_id: str, agent_id: str) -> dict:
        data = {'agent_id': agent_id}
        return self._make_request('POST', f'/api/jobs/{job_id}/claim', data)

    def submit_deliverable(self, job_id: str, deliverable_url: str, notes: str = None) -> dict:
        data = {'deliverable_url': deliverable_url}
        if notes:
            data['notes'] = notes
        return self._make_request('POST', f'/api/jobs/{job_id}/deliver', data)

    def approve_job(self, job_id: str, rating: int = None, feedback: str = None) -> dict:
        data = {}
        if rating is not None:
            data['rating'] = rating
        if feedback:
            data['feedback'] = feedback
        return self._make_request('POST', f'/api/jobs/{job_id}/approve', data)

    def reject_job(self, job_id: str, reason: str = None) -> dict:
        data = {}
        if reason:
            data['reason'] = reason
        return self._make_request('POST', f'/api/jobs/{job_id}/reject', data)

    def cancel_job(self, job_id: str, reason: str = None) -> dict:
        data = {}
        if reason:
            data['reason'] = reason
        return self._make_request('POST', f'/api/jobs/{job_id}/cancel', data)

    def register_agent(self, name: str, specializations: List[str], 
                      contact_info: dict = None) -> Agent:
        data = {
            'name': name,
            'specializations': specializations
        }
        if contact_info:
            data['contact_info'] = contact_info
            
        response = self._make_request('POST', '/api/agents', data)
        return Agent(**response)

    def get_agent(self, agent_id: str) -> Agent:
        response = self._make_request('GET', f'/api/agents/{agent_id}')
        return Agent(**response)

    def list_agents(self, specialization: str = None, min_reputation: float = None,
                   limit: int = 50, offset: int = 0) -> List[Agent]:
        params = {'limit': limit, 'offset': offset}
        if specialization:
            params['specialization'] = specialization
        if min_reputation is not None:
            params['min_reputation'] = min_reputation
            
        response = self._make_request('GET', '/api/agents', params=params)
        return [Agent(**agent_data) for agent_data in response.get('agents', [])]

    def update_agent(self, agent_id: str, **kwargs) -> Agent:
        response = self._make_request('PUT', f'/api/agents/{agent_id}', kwargs)
        return Agent(**response)

    def deactivate_agent(self, agent_id: str) -> dict:
        return self._make_request('POST', f'/api/agents/{agent_id}/deactivate')

    def get_agent_reputation(self, agent_id: str) -> dict:
        return self._make_request('GET', f'/api/agents/{agent_id}/reputation')

    def get_agent_jobs(self, agent_id: str, status: str = None) -> List[Job]:
        params = {}
        if status:
            params['status'] = status
            
        response = self._make_request('GET', f'/api/agents/{agent_id}/jobs', params=params)
        return [Job(**job_data) for job_data in response.get('jobs', [])]

    def submit_reputation_event(self, agent_id: str, job_id: str, rating: int, 
                               feedback: str = None) -> ReputationEvent:
        data = {
            'job_id': job_id,
            'rating': rating
        }
        if feedback:
            data['feedback'] = feedback
            
        response = self._make_request('POST', f'/api/agents/{agent_id}/reputation', data)
        return ReputationEvent(**response)

    def get_reputation_history(self, agent_id: str, limit: int = 50, 
                             offset: int = 0) -> List[ReputationEvent]:
        params = {'limit': limit, 'offset': offset}
        response = self._make_request('GET', f'/api/agents/{agent_id}/reputation/history', params=params)
        return [ReputationEvent(**event_data) for event_data in response.get('events', [])]

    def search_jobs(self, query: str = None, specializations: List[str] = None,
                   min_reward: float = None, max_reward: float = None,
                   status: str = None, limit: int = 50, offset: int = 0) -> List[Job]:
        params = {'limit': limit, 'offset': offset}
        
        if query:
            params['q'] = query
        if specializations:
            params['specializations'] = ','.join(specializations)
        if min_reward is not None:
            params['min_reward'] = min_reward
        if max_reward is not None:
            params['max_reward'] = max_reward
        if status:
            params['status'] = status
            
        response = self._make_request('GET', '/api/jobs/search', params=params)
        return [Job(**job_data) for job_data in response.get('jobs', [])]

    def get_marketplace_stats(self) -> dict:
        return self._make_request('GET', '/api/stats')

    def get_leaderboard(self, metric: str = 'reputation', limit: int = 10) -> List[Agent]:
        params = {'metric': metric, 'limit': limit}
        response = self._make_request('GET', '/api/leaderboard', params=params)
        return [Agent(**agent_data) for agent_data in response.get('agents', [])]

    def health_check(self) -> dict:
        return self._make_request('GET', '/health')

    def wait_for_job_completion(self, job_id: str, timeout: int = 300, 
                               poll_interval: int = 10) -> Job:
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            job = self.get_job(job_id)
            if job.status in ['completed', 'approved', 'rejected', 'cancelled']:
                return job
            time.sleep(poll_interval)
            
        raise RustChainAPIError(f"Job {job_id} did not complete within {timeout} seconds")

    def bulk_create_jobs(self, jobs_data: List[dict]) -> List[Job]:
        response = self._make_request('POST', '/api/jobs/bulk', {'jobs': jobs_data})
        return [Job(**job_data) for job_data in response.get('jobs', [])]

    def get_agent_earnings(self, agent_id: str, start_date: str = None, 
                          end_date: str = None) -> dict:
        params = {}
        if start_date:
            params['start_date'] = start_date
        if end_date:
            params['end_date'] = end_date
            
        return self._make_request('GET', f'/api/agents/{agent_id}/earnings', params=params)

class JobManager:
    def __init__(self, sdk: RustChainSDK):
        self.sdk = sdk

    def post_and_wait(self, title: str, description: str, reward: float, 
                     timeout: int = 3600, **kwargs) -> Job:
        job = self.sdk.create_job(title, description, reward, **kwargs)
        return self.sdk.wait_for_job_completion(job.id, timeout)

    def auto_approve_on_delivery(self, job_id: str, rating: int = 5, 
                                feedback: str = "Great work!") -> dict:
        job = self.sdk.get_job(job_id)
        if job.status == 'delivered':
            return self.sdk.approve_job(job_id, rating, feedback)
        raise RustChainAPIError(f"Job {job_id} is not in delivered status")

class ReputationManager:
    def __init__(self, sdk: RustChainSDK):
        self.sdk = sdk

    def calculate_agent_score(self, agent_id: str) -> float:
        history = self.sdk.get_reputation_history(agent_id)
        if not history:
            return 0.0
            
        total_rating = sum(event.rating for event in history)
        return total_rating / len(history)

    def get_top_performers(self, specialization: str = None, limit: int = 10) -> List[Agent]:
        agents = self.sdk.list_agents(specialization=specialization, limit=100)
        sorted_agents = sorted(agents, key=lambda a: a.reputation_score, reverse=True)
        return sorted_agents[:limit]

def create_client(base_url: str = "http://localhost:5000", api_key: str = None) -> RustChainSDK:
    return RustChainSDK(base_url, api_key)