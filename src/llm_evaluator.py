#!/usr/bin/env python3
"""
LLM Evaluator - Uses LLM to assess bounty feasibility
"""

import os
import json
from typing import Dict, Optional


class LLMEvaluator:
    """Evaluates bounties using LLM to determine feasibility."""

    def __init__(self, provider: str = 'claude', model: str = 'claude-3-5-sonnet-20240620',
                 max_tokens: int = 4000, temperature: float = 0.7, logger=None):
        self.provider = provider
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.logger = logger
        
        # Initialize LLM client
        self.client = self._init_client()

    def _init_client(self):
        """Initialize LLM client based on provider."""
        if self.provider == 'claude':
            try:
                import anthropic
                api_key = os.getenv('ANTHROPIC_API_KEY')
                if not api_key:
                    raise ValueError("ANTHROPIC_API_KEY not set")
                return anthropic.Anthropic(api_key=api_key)
            except ImportError:
                if self.logger:
                    self.logger.error("anthropic package not installed")
                return None
        
        elif self.provider == 'openai':
            try:
                import openai
                api_key = os.getenv('OPENAI_API_KEY')
                if not api_key:
                    raise ValueError("OPENAI_API_KEY not set")
                return openai.OpenAI(api_key=api_key)
            except ImportError:
                if self.logger:
                    self.logger.error("openai package not installed")
                return None
        
        else:
            if self.logger:
                self.logger.error(f"Unsupported provider: {self.provider}")
            return None

    def evaluate_bounty(self, bounty: Dict) -> Dict:
        """Evaluate if the agent can complete this bounty."""
        if not self.client:
            return {
                'recommended': False,
                'reason': 'LLM client not available',
                'confidence': 0.0,
                'estimated_hours': 0,
                'required_skills': [],
                'risks': ['No LLM available']
            }
        
        # Build evaluation prompt
        prompt = self._build_evaluation_prompt(bounty)
        
        try:
            # Call LLM
            if self.provider == 'claude':
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    system="You are an expert software engineer evaluating bounty tasks for an autonomous agent.",
                    messages=[{"role": "user", "content": prompt}]
                )
                result_text = response.content[0].text
            
            elif self.provider == 'openai':
                response = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    messages=[
                        {"role": "system", "content": "You are an expert software engineer evaluating bounty tasks for an autonomous agent."},
                        {"role": "user", "content": prompt}
                    ]
                )
                result_text = response.choices[0].message.content
            
            else:
                result_text = ""
            
            # Parse LLM response
            evaluation = self._parse_evaluation_response(result_text)
            
            if self.logger:
                self.logger.info(f"🧠 Evaluation: {evaluation['recommended']} ({evaluation['confidence']:.1%})")
                self.logger.info(f"   Estimated: {evaluation['estimated_hours']} hours")
                self.logger.info(f"   Skills: {', '.join(evaluation['required_skills'])}")
            
            return evaluation
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"LLM evaluation error: {e}")
            
            return {
                'recommended': False,
                'reason': f'LLM error: {e}',
                'confidence': 0.0,
                'estimated_hours': 0,
                'required_skills': [],
                'risks': [f'LLM error: {e}']
            }

    def _build_evaluation_prompt(self, bounty: Dict) -> str:
        """Build prompt for LLM evaluation."""
        return f"""Evaluate this RustChain bounty for autonomous implementation:

BOUNTY #{bounty['number']}: {bounty['title']}
Reward: {bounty['reward_rtc']} RTC
Age: {bounty['age_days']} days

Description:
{bounty['body']}

Labels: {', '.join(bounty['labels'])}

Please analyze and respond with JSON:
{{
  "recommended": true/false,
  "reason": "explanation",
  "confidence": 0.0-1.0,
  "estimated_hours": number,
  "required_skills": ["skill1", "skill2"],
  "risks": ["risk1", "risk2"],
  "implementation_approach": "high-level approach",
  "key_challenges": ["challenge1", "challenge2"]
}}

Consider:
- Can an autonomous agent implement this?
- What skills are required?
- What are the main risks?
- Is the reward worth the effort?
- Are there dependencies or blockers?

Be realistic and conservative in your assessment.
"""

    def _parse_evaluation_response(self, response: str) -> Dict:
        """Parse LLM response into structured evaluation."""
        try:
            # Extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(0)
                result = json.loads(json_str)
                
                # Ensure all required fields
                defaults = {
                    'recommended': False,
                    'reason': 'No reason provided',
                    'confidence': 0.0,
                    'estimated_hours': 0,
                    'required_skills': [],
                    'risks': [],
                    'implementation_approach': '',
                    'key_challenges': []
                }
                
                for key, default in defaults.items():
                    if key not in result:
                        result[key] = default
                
                return result
            
            else:
                # Fallback parsing
                recommended = 'recommended' in response.lower() and 'true' in response.lower()
                confidence = 0.5 if recommended else 0.0
                
                return {
                    'recommended': recommended,
                    'reason': 'Parsed from text response',
                    'confidence': confidence,
                    'estimated_hours': 4 if recommended else 0,
                    'required_skills': ['unknown'],
                    'risks': ['Response parsing failed'],
                    'implementation_approach': '',
                    'key_challenges': []
                }
        
        except Exception as e:
            return {
                'recommended': False,
                'reason': f'Failed to parse LLM response: {e}',
                'confidence': 0.0,
                'estimated_hours': 0,
                'required_skills': [],
                'risks': ['Response parsing failed'],
                'implementation_approach': '',
                'key_challenges': []
            }