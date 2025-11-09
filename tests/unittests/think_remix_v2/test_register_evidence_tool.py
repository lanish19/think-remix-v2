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

"""Unit tests for register_evidence tool."""

from __future__ import annotations

from datetime import datetime

import pytest

from google.adk.tools.tool_context import ToolContext

from contributing.samples.think_remix_v2 import agent
from contributing.samples.think_remix_v2.state_manager import StateManager


@pytest.fixture
def tool_context():
  """Create a tool context for testing."""
  ctx = ToolContext()
  ctx.state = {}
  return ctx


def test_register_evidence_primary_source(tool_context):
  """Test registering evidence from a primary source."""
  result = agent.register_evidence(
      statement='Market size is $500M according to industry report.',
      source='https://example.com/industry-report-2024',
      source_type='primary',
      tool_context=tool_context,
  )
  
  assert 'fact_id' in result
  assert result['fact_id'].startswith('CER-')
  assert result['statement'] == 'Market size is $500M according to industry report.'
  assert result['source'] == 'https://example.com/industry-report-2024'
  assert result['source_type'] == 'primary'
  assert result['credibility_score'] == 0.95  # Primary source score


def test_register_evidence_secondary_source(tool_context):
  """Test registering evidence from a secondary source."""
  result = agent.register_evidence(
      statement='Analysis suggests 20% growth rate.',
      source='https://example.com/analysis',
      source_type='secondary',
      tool_context=tool_context,
  )
  
  assert result['credibility_score'] == 0.75  # Secondary source score
  assert result['source_type'] == 'secondary'


def test_register_evidence_tertiary_source(tool_context):
  """Test registering evidence from a tertiary source."""
  result = agent.register_evidence(
      statement='Some blog post claims X.',
      source='https://example.com/blog',
      source_type='tertiary',
      tool_context=tool_context,
  )
  
  assert result['credibility_score'] == 0.55  # Tertiary source score


def test_register_evidence_credibility_override(tool_context):
  """Test registering evidence with credibility override."""
  result = agent.register_evidence(
      statement='Custom credibility fact.',
      source='https://example.com/custom',
      source_type='primary',
      tool_context=tool_context,
      credibility_override=0.85,
  )
  
  assert result['credibility_score'] == 0.85


def test_register_evidence_fact_id_format(tool_context):
  """Test that fact IDs follow the correct format."""
  result = agent.register_evidence(
      statement='Test fact.',
      source='https://example.com/test',
      source_type='primary',
      tool_context=tool_context,
      date_accessed='20250115',
  )
  
  fact_id = result['fact_id']
  assert fact_id.startswith('CER-20250115-')
  # Should have sequence number
  assert len(fact_id.split('-')) == 3


def test_register_evidence_accumulates_in_state(tool_context):
  """Test that registered facts accumulate in state."""
  # Register first fact
  result1 = agent.register_evidence(
      statement='First fact.',
      source='https://example.com/1',
      source_type='primary',
      tool_context=tool_context,
  )
  
  # Register second fact
  result2 = agent.register_evidence(
      statement='Second fact.',
      source='https://example.com/2',
      source_type='primary',
      tool_context=tool_context,
  )
  
  # Check state
  manager = StateManager(tool_context)
  cer_registry = manager.cer_registry
  
  assert len(cer_registry) == 2
  assert cer_registry[0]['fact_id'] == result1['fact_id']
  assert cer_registry[1]['fact_id'] == result2['fact_id']


def test_register_evidence_research_track_tag(tool_context):
  """Test registering evidence with research track tag."""
  result = agent.register_evidence(
      statement='Disconfirmatory evidence.',
      source='https://example.com/disconfirm',
      source_type='secondary',
      tool_context=tool_context,
      research_track='disconfirmatory',
  )
  
  assert 'metadata' in result
  assert result['metadata']['research_track'] == 'disconfirmatory'
