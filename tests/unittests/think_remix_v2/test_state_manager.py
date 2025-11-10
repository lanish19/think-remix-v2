"""Unit tests for THINK Remix V2 state management and tools."""

from __future__ import annotations

import re
from types import SimpleNamespace

import pytest

from contributing.samples.think_remix_v2 import agent
from contributing.samples.think_remix_v2 import state_manager


class FakeToolContext(SimpleNamespace):
  """Minimal tool context stub for unit testing."""

  def __init__(self):
    super().__init__(state={})


def test_initialize_state_sets_required_keys():
  ctx = FakeToolContext()
  state_manager.initialize_state(ctx)  # type: ignore[arg-type]

  assert 'cer_registry' in ctx.state
  assert ctx.state['cer_registry'] == []
  assert ctx.state['cer_next_id'] == 1
  assert ctx.state['persona_analyses'] == []
  assert ctx.state['null_hypotheses'] == []


def test_register_evidence_returns_structured_fact():
  ctx = FakeToolContext()

  result = agent.register_evidence(
      statement='Market size is $500M',
      source='https://example.com/report',
      source_type='primary',
      date_accessed='20250115',
      tool_context=ctx,  # type: ignore[arg-type]
  )

  assert result['fact_id'].startswith('CER-20250115-')
  assert re.fullmatch(r'CER-20250115-\d{3}', result['fact_id'])
  assert 0.0 <= result['credibility_score'] <= 1.0
  assert result['statement'] == 'Market size is $500M'
  assert result['source_type'] == 'primary'
  assert result in ctx.state['cer_registry']


def test_record_persona_analysis_updates_state():
  ctx = FakeToolContext()
  state_manager.initialize_state(ctx)  # type: ignore[arg-type]

  payload = {
      'persona_id': 'a',
      'persona_name': 'Bayesian Strategist',
      'evidence': {
          'prioritized': [{'fact_id': 'CER-20250115-001', 'weight': 0.4}],
          'ignored': [{'fact_id': 'CER-20250115-010'}],
      },
  }

  stored = agent.record_persona_analysis(  # type: ignore[attr-defined]
      persona_result=payload,
      tool_context=ctx,  # type: ignore[arg-type]
  )

  assert stored == payload
  assert ctx.state['persona_analyses'][0]['persona_id'] == 'a'


def test_null_hypotheses_dict_to_list_conversion():
  """Test that dict-wrapped null_hypotheses converts to list."""
  ctx = FakeToolContext()
  ctx.state = {
      'cer_registry': [],
      'cer_next_id': 1,
      'cer_daily_sequences': {},
      'persona_analyses': [],
      'null_hypotheses': {'null_hypotheses': [{'id': 'NH-01'}]},  # Dict wrapper
      'null_hypotheses_result': {},
      'research_objectives': [],
      'adjudications': {},
      'workflow_audit_trail': [],
  }

  state_manager.initialize_state_mapping(ctx.state)  # type: ignore[arg-type]

  assert isinstance(ctx.state['null_hypotheses'], list)
  assert len(ctx.state['null_hypotheses']) == 1
  assert ctx.state['null_hypotheses'][0]['id'] == 'NH-01'


def test_null_hypotheses_empty_dict_conversion():
  """Test that empty dict converts to empty list."""
  ctx = FakeToolContext()
  ctx.state = {
      'cer_registry': [],
      'cer_next_id': 1,
      'cer_daily_sequences': {},
      'persona_analyses': [],
      'null_hypotheses': {},  # Empty dict
      'null_hypotheses_result': {},
      'research_objectives': [],
      'adjudications': {},
      'workflow_audit_trail': [],
  }

  state_manager.initialize_state_mapping(ctx.state)  # type: ignore[arg-type]

  assert isinstance(ctx.state['null_hypotheses'], list)
  assert len(ctx.state['null_hypotheses']) == 0


def test_register_evidence_empty_statement_raises_error():
  """Test that empty statement raises ValueError."""
  ctx = FakeToolContext()
  state_manager.initialize_state(ctx)  # type: ignore[arg-type]

  with pytest.raises(ValueError, match='cannot be empty'):
    agent.register_evidence(
        statement='',
        source='https://example.com',
        source_type='primary',
        tool_context=ctx,  # type: ignore[arg-type]
    )


def test_register_evidence_long_statement_truncated():
  """Test that statement exceeding max length is truncated."""
  ctx = FakeToolContext()
  state_manager.initialize_state(ctx)  # type: ignore[arg-type]

  long_statement = 'x' * 15000  # Exceeds 10000 char limit
  result = agent.register_evidence(
      statement=long_statement,
      source='https://example.com',
      source_type='primary',
      tool_context=ctx,  # type: ignore[arg-type]
  )

  assert len(result['statement']) == 10000
  assert result['statement'] == 'x' * 10000


def test_register_evidence_long_source_truncated():
  """Test that source URL exceeding max length is truncated."""
  ctx = FakeToolContext()
  state_manager.initialize_state(ctx)  # type: ignore[arg-type]

  long_source = 'https://example.com/' + 'x' * 3000  # Exceeds 2000 char limit
  result = agent.register_evidence(
      statement='Test statement',
      source=long_source,
      source_type='primary',
      tool_context=ctx,  # type: ignore[arg-type]
  )

  assert len(result['source']) == 2000
