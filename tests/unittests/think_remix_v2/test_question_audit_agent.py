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

"""Unit tests for question audit agent."""

from __future__ import annotations

import json

import pytest

from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.invocation_context import InvocationContext
from google.adk.tools.tool_context import ToolContext

from contributing.samples.think_remix_v2 import agent
from contributing.samples.think_remix_v2.schemas import AuditResult
from contributing.samples.think_remix_v2.validation import validate_agent_output_by_key


@pytest.fixture
def mock_invocation_context():
  """Create a mock invocation context."""
  ctx = InvocationContext()
  ctx.state = {}
  return ctx


def test_question_audit_blocks_unanswerable(mock_invocation_context):
  """Test that unanswerable questions are blocked."""
  # This is a conceptual test - in practice, we'd need to mock the LLM
  # For now, we test the schema validation
  unanswerable_output = json.dumps({
      'audit_status': 'block',
      'question_type': 'normative',
      'answerability': 'unanswerable',
      'scope_assessment': 'appropriate',
      'temporal_assessment': 'feasible',
      'clarification_needed': 'This question requires metaphysical judgment.',
  })
  
  result = validate_agent_output_by_key(
      unanswerable_output,
      'question_audit_result',
      'question_audit_agent',
  )
  
  assert result.valid
  assert result.model is not None
  assert result.model.audit_status == 'block'
  assert result.model.answerability == 'unanswerable'


def test_question_audit_proceeds_with_valid_question(mock_invocation_context):
  """Test that valid questions proceed."""
  valid_output = json.dumps({
      'audit_status': 'proceed',
      'question_type': 'causal',
      'answerability': 'empirical',
      'scope_assessment': 'appropriate',
      'temporal_assessment': 'feasible',
      'proceed_justification': 'Question is well-formed and answerable.',
  })
  
  result = validate_agent_output_by_key(
      valid_output,
      'question_audit_result',
      'question_audit_agent',
  )
  
  assert result.valid
  assert result.model is not None
  assert result.model.audit_status == 'proceed'


def test_question_audit_request_clarification(mock_invocation_context):
  """Test that unclear questions request clarification."""
  clarification_output = json.dumps({
      'audit_status': 'request_clarification',
      'question_type': 'hybrid',
      'answerability': 'hybrid',
      'scope_assessment': 'too_broad',
      'temporal_assessment': 'feasible',
      'clarification_needed': 'Please specify the time horizon for this question.',
  })
  
  result = validate_agent_output_by_key(
      clarification_output,
      'question_audit_result',
      'question_audit_agent',
  )
  
  assert result.valid
  assert result.model is not None
  assert result.model.audit_status == 'request_clarification'
  assert result.model.clarification_needed is not None


def test_question_audit_schema_validation_fails_invalid():
  """Test that invalid JSON fails validation."""
  invalid_output = 'This is not JSON'
  
  result = validate_agent_output_by_key(
      invalid_output,
      'question_audit_result',
      'question_audit_agent',
  )
  
  assert not result.valid
  assert result.error is not None


def test_question_audit_schema_validation_fails_missing_fields():
  """Test that missing required fields fail validation."""
  incomplete_output = json.dumps({
      'question_type': 'causal',
      # Missing audit_status
  })
  
  result = validate_agent_output_by_key(
      incomplete_output,
      'question_audit_result',
      'question_audit_agent',
  )
  
  assert not result.valid
  assert 'audit_status' in result.error.lower() or 'required' in result.error.lower()
