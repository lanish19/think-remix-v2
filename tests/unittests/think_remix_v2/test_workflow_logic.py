"""Unit tests for THINK Remix workflow logic helpers."""

from __future__ import annotations

import pytest

from contributing.samples.think_remix_v2 import workflow_logic


def test_evaluate_audit_gate_allows_proceed():
  audit = {
      'audit_status': 'proceed',
  }
  decision = workflow_logic.evaluate_audit_gate(audit)
  assert decision.audit_status == 'proceed'
  assert not decision.blocked


def test_evaluate_audit_gate_blocks_with_error():
  audit = {
      'audit_status': 'block',
      'clarification_needed': 'Question is unanswerable.',
  }
  decision = workflow_logic.evaluate_audit_gate(audit)
  assert decision.blocked
  assert decision.payload['error'] == 'Question is unanswerable.'


def test_evaluate_audit_gate_requires_status():
  with pytest.raises(workflow_logic.WorkflowError):
    workflow_logic.evaluate_audit_gate({})

