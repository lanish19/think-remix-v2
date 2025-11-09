# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unit tests for persona allocator and validator."""

from __future__ import annotations

import json

import pytest

from contributing.samples.think_remix_v2 import agent
from contributing.samples.think_remix_v2.schemas import PersonaAllocation
from contributing.samples.think_remix_v2.schemas import PersonaValidation
from contributing.samples.think_remix_v2.validation import validate_agent_output_by_key


def test_persona_allocator_schema_validation():
  """Test persona allocator output schema validation."""
  valid_output = json.dumps({
      'complexity_analysis': {
          'stakeholder_count': 3.0,
          'temporal_dimensions': 2.0,
          'domain_crossings': 1.0,
          'known_unknowns': 2.0,
          'complexity_score': 2.3,
          'recommended_persona_count': 3,
      },
      'persona_count': 3,
      'personas': [
          {
              'id': 'a',
              'persona_name': 'Bayesian Analyst',
              'epistemological_framework': 'Bayesian_Reasoning',
              'analytical_focus': 'Statistical inference',
              'worldview': 'Markets are probabilistic',
              'guiding_question': 'What is the probability?',
              'evidence_lens': 'Prioritize quantitative data',
              'time_horizon': 'short_term',
              'risk_orientation': 'risk_neutral',
              'diversity_tags': ['status_quo_challenger'],
          },
          {
              'id': 'b',
              'persona_name': 'Systems Thinker',
              'epistemological_framework': 'Complex_Systems',
              'analytical_focus': 'Feedback loops',
              'worldview': 'Systems are interconnected',
              'guiding_question': 'What are the feedback mechanisms?',
              'evidence_lens': 'Look for patterns',
              'time_horizon': 'long_term',
              'risk_orientation': 'risk_averse',
              'diversity_tags': ['long_term_guardian'],
          },
          {
              'id': 'c',
              'persona_name': 'Institutional Economist',
              'epistemological_framework': 'Institutional_Economics',
              'analytical_focus': 'Incentive structures',
              'worldview': 'Institutions shape behavior',
              'guiding_question': 'What are the incentives?',
              'evidence_lens': 'Focus on institutional data',
              'time_horizon': 'medium_term',
              'risk_orientation': 'risk_neutral',
              'diversity_tags': [],
          },
      ],
  })
  
  result = validate_agent_output_by_key(
      valid_output,
      'persona_allocation',
      'persona_allocator_agent',
  )
  
  assert result.valid
  assert result.model is not None
  assert isinstance(result.model, PersonaAllocation)
  assert result.model.persona_count == 3
  assert len(result.model.personas) == 3


def test_persona_validator_approved():
  """Test persona validator approves diverse personas."""
  valid_output = json.dumps({
      'validation_status': 'approved',
      'cognitive_distance_matrix': [
          {
              'pair': ['a', 'b'],
              'similarity': 0.42,
              'overlap_dimensions': [],
          },
          {
              'pair': ['a', 'c'],
              'similarity': 0.38,
              'overlap_dimensions': [],
          },
          {
              'pair': ['b', 'c'],
              'similarity': 0.45,
              'overlap_dimensions': [],
          },
      ],
      'redundancy_flags': [],
      'diversity_checks': {
          'unique_frameworks': True,
          'long_term_present': True,
          'status_quo_challenger_present': True,
      },
  })
  
  result = validate_agent_output_by_key(
      valid_output,
      'persona_validation',
      'persona_validator_agent',
  )
  
  assert result.valid
  assert result.model is not None
  assert isinstance(result.model, PersonaValidation)
  assert result.model.validation_status == 'approved'


def test_persona_validator_requires_regeneration():
  """Test persona validator rejects similar personas."""
  valid_output = json.dumps({
      'validation_status': 'requires_regeneration',
      'cognitive_distance_matrix': [
          {
              'pair': ['a', 'b'],
              'similarity': 0.85,  # Too high
              'overlap_dimensions': ['worldview', 'guiding_question'],
          },
      ],
      'redundancy_flags': [
          {
              'persona_ids': ['a', 'b'],
              'issue': 'shared worldview framing',
              'remediation': 'swap framework to Complex_Systems',
          },
      ],
      'diversity_checks': {
          'unique_frameworks': False,
          'long_term_present': True,
          'status_quo_challenger_present': True,
      },
  })
  
  result = validate_agent_output_by_key(
      valid_output,
      'persona_validation',
      'persona_validator_agent',
  )
  
  assert result.valid
  assert result.model is not None
  assert result.model.validation_status == 'requires_regeneration'
  assert len(result.model.redundancy_flags) > 0


def test_create_persona_agent():
  """Test dynamic persona agent creation."""
  persona_config = {
      'id': 'test_persona',
      'persona_name': 'Test Persona',
      'epistemological_framework': 'Bayesian_Reasoning',
      'analytical_focus': 'Testing',
      'worldview': 'Test worldview',
      'guiding_question': 'Test question?',
      'evidence_lens': 'Test lens',
      'time_horizon': 'short_term',
      'risk_orientation': 'risk_neutral',
      'diversity_tags': [],
  }
  
  cer_facts = [
      {'fact_id': 'CER-20250115-001', 'statement': 'Test fact 1'},
      {'fact_id': 'CER-20250115-002', 'statement': 'Test fact 2'},
  ]
  
  persona_agent = agent.create_persona_agent(persona_config, cer_facts)
  
  assert persona_agent.name == 'persona_test_persona'
  assert persona_agent.model == 'gemini-2.5-pro'
  assert 'Test Persona' in persona_agent.instruction
  assert 'Bayesian_Reasoning' in persona_agent.instruction
  assert 'CER-20250115-001' in persona_agent.instruction
  assert 'CER-20250115-002' in persona_agent.instruction
