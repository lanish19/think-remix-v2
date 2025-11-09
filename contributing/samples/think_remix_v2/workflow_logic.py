"""Workflow orchestration helpers for THINK Remix v2.0."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from typing import Optional
from typing import Type
from typing import TypeVar

from pydantic import ValidationError

from . import schemas


ModelT = TypeVar('ModelT', bound=schemas.ImmutableModel)


class WorkflowError(RuntimeError):
  """Raised when the workflow encounters a blocking condition."""


@dataclass(frozen=True)
class AuditGateDecision:
  """Represents the outcome of the question audit gate."""

  audit_status: str
  payload: dict[str, Any]
  blocked: bool = False


def parse_agent_json(raw_text: str) -> Any:
  """Parses agent output enforcing strict JSON."""
  try:
    return json.loads(raw_text)
  except json.JSONDecodeError as exc:
    raise WorkflowError(f'Agent output was not valid JSON: {exc}') from exc


def parse_model(raw_text: str, model_cls: Type[ModelT]) -> ModelT:
  """Parses agent output and validates against a pydantic schema."""
  payload = parse_agent_json(raw_text)
  try:
    return model_cls.model_validate(payload)
  except ValidationError as exc:
    raise WorkflowError(
        f'Agent output failed validation for {model_cls.__name__}: {exc}'
    ) from exc


def evaluate_audit_gate(audit_result: dict[str, Any]) -> AuditGateDecision:
  """Evaluates audit gate result and determines branching action."""
  audit = schemas.AuditResult.model_validate(audit_result)
  status = audit.audit_status
  if status is None:
    raise WorkflowError('Audit result missing audit_status.')

  normalized = status.lower()
  payload: dict[str, Any] = {'audit_status': normalized}

  if normalized == 'proceed':
    return AuditGateDecision(audit_status=normalized, payload=payload)

  if normalized == 'request_clarification':
    prompt = audit.clarification_needed or (
        'Please clarify the question so the workflow can proceed.'
    )
    payload['clarification_prompt'] = prompt
    payload['error'] = 'Clarification required before workflow can proceed.'
    return AuditGateDecision(
        audit_status=normalized,
        payload=payload,
        blocked=True,
    )

  # Treat any non-proceed status as block.
  payload['error'] = (
      audit.proceed_justification
      or audit.clarification_needed
      or 'Question blocked by audit gate.'
  )
  return AuditGateDecision(
      audit_status=normalized,
      payload=payload,
      blocked=True,
  )


def ensure_audit_allows_progress(audit_result: dict[str, Any]) -> Optional[dict[str, Any]]:
  """Returns blocking payload if audit fails, else None."""
  decision = evaluate_audit_gate(audit_result)
  return decision.payload if decision.blocked else None

