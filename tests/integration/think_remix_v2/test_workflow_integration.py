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

"""Integration tests for THINK Remix v2.0 workflow."""

from __future__ import annotations

import pytest

from google.adk.agents.invocation_context import InvocationContext
from google.adk.runners.runner import Runner

from contributing.samples.think_remix_v2 import agent


@pytest.fixture
def runner():
  """Create a runner instance."""
  return Runner()


@pytest.fixture
def invocation_context():
  """Create an invocation context."""
  ctx = InvocationContext()
  ctx.state = {}
  return ctx


@pytest.mark.asyncio
async def test_workflow_audit_gate_blocks_unanswerable(runner, invocation_context):
  """Test that audit gate blocks unanswerable questions."""
  # Note: This is a conceptual test - actual execution would require LLM mocking
  # For now, we test that the workflow structure is correct
  
  # The workflow should have question_audit_agent as first step
  assert hasattr(agent, 'question_audit_agent')
  assert agent.question_audit_agent.name == 'question_audit_gate'
  
  # The workflow should have the audit gate callback
  assert agent.question_audit_agent.before_agent_callback is not None


@pytest.mark.asyncio
async def test_workflow_structure(runner, invocation_context):
  """Test that workflow has correct structure."""
  # Verify root agent exists
  assert hasattr(agent, 'root_agent')
  assert agent.root_agent.name == 'think_remix_v2'
  
  # Verify it's a ThinkRemixWorkflowAgent
  from contributing.samples.think_remix_v2.workflow_agent import ThinkRemixWorkflowAgent
  assert isinstance(agent.root_agent, ThinkRemixWorkflowAgent)


def test_workflow_has_all_agents():
  """Test that all required agents are defined."""
  required_agents = [
      'question_audit_agent',
      'analyze_question_agent',
      'generate_nulls_agent',
      'gather_insights_agent',
      'persona_allocator_agent',
      'persona_validator_agent',
      'synthesis_agent',
      'adversarial_injector_agent',
      'analyze_disagreement_agent',
      'null_adjudicator_agent',
      'conduct_research_agent',
      'evidence_consistency_enforcer_agent',
      'evidence_adjudicator_agent',
      'case_file_agent',
      'coverage_validator_agent',
      'robustness_calculator_agent',
      'analyze_blindspots_agent',
      'search_inquiry_strategist_agent',
      'qa_agent',
      'final_arbiter_agent',
  ]
  
  for agent_name in required_agents:
    assert hasattr(agent, agent_name), f'Missing agent: {agent_name}'


def test_workflow_has_tools():
  """Test that required tools are defined."""
  # Check register_evidence tool exists
  assert hasattr(agent, 'register_evidence')
  assert callable(agent.register_evidence)
  
  # Check record_persona_analysis tool exists
  assert hasattr(agent, 'record_persona_analysis')
  assert callable(agent.record_persona_analysis)


def test_workflow_config_integration():
  """Test that workflow integrates with configuration."""
  from contributing.samples.think_remix_v2.config_loader import get_config
  
  config = get_config()
  
  # Verify config has required properties
  assert hasattr(config, 'persona_similarity_max')
  assert hasattr(config, 'cer_credibility_bedrock')
  assert hasattr(config, 'max_persona_validator_attempts')
  assert hasattr(config, 'max_coverage_validator_attempts')
  
  # Verify workflow agent uses config
  assert agent.root_agent._config is not None
