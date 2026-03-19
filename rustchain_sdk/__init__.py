// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import requests
import json
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import time

class RustChainError(Exception):
    """Base exception for RustChain SDK"""
    pass

class AuthenticationError(RustChainError):
    """Authentication related errors"""
    pass

class JobNotFoundError(RustChainError):
    """Job not found error"""
    pass

class APIError(RustChainError):
    """General API errors"""
    pass

class AgentEconomyClient:
    """Python SDK for RustChain Agent Economy API"""
    
    def __init__(self, 
                 base_url: str = "http://localhost:5000",
                 api_key: Optional[str] = None,
                 timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.session = requests.Session()
        
        if api_key:
            self.session.headers.update({
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            })
    
    def _make_request(self, 
                     method: str, 
                     endpoint: str, 
                     data: Optional[Dict] = None,
                     params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make HTTP request with error handling"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method.upper() == 'GET':
                response = self.session.get(url, params=params, timeout=self.timeout)
            elif method.upper() == 'POST':
                response = self.session.post(url, json=data, timeout=self.timeout)
            elif method.upper() == 'PUT':
                response = self.session.put(url, json=data, timeout=self.timeout)
            elif method.upper() == 'DELETE':
                response = self.session.delete(url, timeout=self.timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            if response.status_code == 401:
                raise AuthenticationError("Invalid API key or authentication required")
            elif response.status_code == 404:
                raise JobNotFoundError("Resource not found")
            elif response.status_code >= 400:
                raise APIError(f"API error {response.status_code}: {response.text}")
            
            return response.json()
            
        except requests.RequestException as e:
            raise RustChainError(f"Request failed: {str(e)}")
    
    def create_job(self, 
                   title: str,
                   description: str,
                   reward_amount: float,
                   skill_requirements: List[str],
                   deadline: Optional[str] = None,
                   metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Create a new job posting"""
        job_data = {
            'title': title,
            'description': description,
            'reward_amount': reward_amount,
            'skill_requirements': skill_requirements,
            'status': 'open',
            'created_at': datetime.utcnow().isoformat()
        }
        
        if deadline:
            job_data['deadline'] = deadline
        if metadata:
            job_data['metadata'] = metadata
            
        return self._make_request('POST', '/api/jobs', job_data)
    
    def get_job(self, job_id: str) -> Dict[str, Any]:
        """Get job details by ID"""
        return self._make_request('GET', f'/api/jobs/{job_id}')
    
    def list_jobs(self, 
                  status: Optional[str] = None,
                  skill: Optional[str] = None,
                  min_reward: Optional[float] = None,
                  limit: int = 50) -> List[Dict[str, Any]]:
        """List jobs with optional filters"""
        params = {'limit': limit}
        if status:
            params['status'] = status
        if skill:
            params['skill'] = skill
        if min_reward:
            params['min_reward'] = min_reward
            
        response = self._make_request('GET', '/api/jobs', params=params)
        return response.get('jobs', [])
    
    def claim_job(self, job_id: str, agent_id: str) -> Dict[str, Any]:
        """Claim a job for an agent"""
        claim_data = {
            'job_id': job_id,
            'agent_id': agent_id,
            'claimed_at': datetime.utcnow().isoformat()
        }
        return self._make_request('POST', f'/api/jobs/{job_id}/claim', claim_data)
    
    def submit_delivery(self, 
                       job_id: str, 
                       agent_id: str,
                       deliverable_url: str,
                       notes: Optional[str] = None) -> Dict[str, Any]:
        """Submit job deliverable"""
        delivery_data = {
            'job_id': job_id,
            'agent_id': agent_id,
            'deliverable_url': deliverable_url,
            'submitted_at': datetime.utcnow().isoformat()
        }
        if notes:
            delivery_data['notes'] = notes
            
        return self._make_request('POST', f'/api/jobs/{job_id}/deliver', delivery_data)
    
    def approve_delivery(self, job_id: str) -> Dict[str, Any]:
        """Approve job delivery"""
        return self._make_request('PUT', f'/api/jobs/{job_id}/approve')
    
    def reject_delivery(self, job_id: str, reason: str) -> Dict[str, Any]:
        """Reject job delivery"""
        reject_data = {'reason': reason}
        return self._make_request('PUT', f'/api/jobs/{job_id}/reject', reject_data)
    
    def get_agent_reputation(self, agent_id: str) -> Dict[str, Any]:
        """Get agent reputation score and history"""
        return self._make_request('GET', f'/api/agents/{agent_id}/reputation')
    
    def update_reputation(self, 
                         agent_id: str, 
                         job_id: str,
                         rating: int, 
                         feedback: Optional[str] = None) -> Dict[str, Any]:
        """Update agent reputation after job completion"""
        if not 1 <= rating <= 5:
            raise ValueError("Rating must be between 1 and 5")
            
        reputation_data = {
            'agent_id': agent_id,
            'job_id': job_id,
            'rating': rating,
            'timestamp': datetime.utcnow().isoformat()
        }
        if feedback:
            reputation_data['feedback'] = feedback
            
        return self._make_request('POST', f'/api/agents/{agent_id}/reputation', reputation_data)
    
    def get_job_history(self, agent_id: str) -> List[Dict[str, Any]]:
        """Get job history for an agent"""
        response = self._make_request('GET', f'/api/agents/{agent_id}/jobs')
        return response.get('jobs', [])
    
    def get_agent_skills(self, agent_id: str) -> List[str]:
        """Get agent skills list"""
        response = self._make_request('GET', f'/api/agents/{agent_id}/skills')
        return response.get('skills', [])
    
    def update_agent_skills(self, agent_id: str, skills: List[str]) -> Dict[str, Any]:
        """Update agent skills"""
        skills_data = {'skills': skills}
        return self._make_request('PUT', f'/api/agents/{agent_id}/skills', skills_data)
    
    def search_agents(self, 
                     skills: Optional[List[str]] = None,
                     min_reputation: Optional[float] = None,
                     availability: Optional[bool] = None) -> List[Dict[str, Any]]:
        """Search for agents by criteria"""
        params = {}
        if skills:
            params['skills'] = ','.join(skills)
        if min_reputation:
            params['min_reputation'] = min_reputation
        if availability is not None:
            params['availability'] = str(availability).lower()
            
        response = self._make_request('GET', '/api/agents/search', params=params)
        return response.get('agents', [])
    
    def get_economy_stats(self) -> Dict[str, Any]:
        """Get overall economy statistics"""
        return self._make_request('GET', '/api/stats')

__all__ = ['AgentEconomyClient', 'RustChainError', 'AuthenticationError', 'JobNotFoundError', 'APIError']