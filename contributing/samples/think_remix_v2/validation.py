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

"""JSON schema validation utilities for THINK Remix v2.0."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any
from typing import Optional
from typing import Type
from typing import TypeVar

from pydantic import ValidationError

from . import schemas

logger = logging.getLogger(__name__)

ModelT = TypeVar('ModelT', bound=schemas.ImmutableModel)


@dataclass
class ValidationResult:
  """Result of schema validation."""

  valid: bool
  """Whether validation passed."""
  
  model: Optional[Any] = None
  """Validated Pydantic model if validation succeeded."""
  
  error: Optional[str] = None
  """Error message if validation failed."""
  
  raw_output: Optional[str] = None
  """Raw agent output that was validated."""


def parse_json_output(raw_text: str) -> dict[str, Any]:
  """Parses agent output enforcing strict JSON."""
  # Try to extract JSON from markdown code blocks if present
  text = raw_text.strip()
  
  # Remove markdown code blocks
  if text.startswith('```'):
    lines = text.split('\n')
    # Remove first line (```json or ```)
    if len(lines) > 1:
      lines = lines[1:]
    # Remove last line (```)
    if lines and lines[-1].strip().startswith('```'):
      lines = lines[:-1]
    text = '\n'.join(lines)
  
  try:
    return json.loads(text)
  except json.JSONDecodeError as exc:
    raise ValueError(f'Agent output was not valid JSON: {exc}') from exc


def validate_agent_output(
    raw_output: str,
    schema_class: Type[ModelT],
    agent_name: str = 'unknown',
) -> ValidationResult:
  """Validates agent output against a Pydantic schema.
  
  Args:
    raw_output: Raw text output from agent.
    schema_class: Pydantic model class to validate against.
    agent_name: Name of the agent for logging.
  
  Returns:
    ValidationResult with validation status and parsed model.
  """
  try:
    # Parse JSON
    payload = parse_json_output(raw_output)
    
    # Validate against schema
    model = schema_class.model_validate(payload)
    
    logger.debug('Validation passed for agent %s', agent_name)
    return ValidationResult(
        valid=True,
        model=model,
        raw_output=raw_output,
    )
    
  except ValueError as e:
    logger.warning('JSON parsing failed for agent %s: %s', agent_name, e)
    return ValidationResult(
        valid=False,
        error=f'JSON parsing error: {e}',
        raw_output=raw_output,
    )
    
  except ValidationError as e:
    logger.warning('Schema validation failed for agent %s: %s', agent_name, e)
    # Format validation errors nicely
    errors = []
    for error in e.errors():
      field = '.'.join(str(loc) for loc in error['loc'])
      msg = error['msg']
      errors.append(f'{field}: {msg}')
    
    error_msg = 'Schema validation errors:\n' + '\n'.join(errors)
    return ValidationResult(
        valid=False,
        error=error_msg,
        raw_output=raw_output,
    )
    
  except (TypeError, AttributeError) as e:
    logger.error('Unexpected error during validation for agent %s: %s', agent_name, e)
    return ValidationResult(
        valid=False,
        error=f'Unexpected validation error: {e}',
        raw_output=raw_output,
    )


# Mapping of agent output keys to their schema classes
AGENT_SCHEMA_MAP: dict[str, Type[schemas.ImmutableModel]] = {
    'question_audit_result': schemas.AuditResult,
    'question_analysis': schemas.QuestionAnalysis,
    'null_hypotheses': schemas.NullHypothesisSet,
    'gather_insights_result': schemas.GatherInsightsResult,
    'persona_allocation': schemas.PersonaAllocation,
    'persona_validation': schemas.PersonaValidation,
    'synthesis_result': schemas.SynthesisResult,
    'adversarial_result': schemas.AdversarialResult,
    'disagreement_analysis': schemas.DisagreementAnalysis,
    'null_adjudications': schemas.NullAdjudicationResult,
    'targeted_research': schemas.ConductResearchResult,
    'evidence_consistency': schemas.EvidenceConsistencyResult,
    'evidence_adjudication': schemas.EvidenceAdjudicationResult,
    'case_file': schemas.CaseFileAgent,
    'coverage_validation': schemas.CoverageValidationResult,
    'robustness_metrics': schemas.RobustnessMetrics,
    'qa_notes': schemas.QAResult,
    'final_arbiter_output': schemas.FinalArbiterOutput,
    'blindspot_analysis': schemas.DisagreementAnalysis,  # Reusing schema
    'search_inquiry_plan': schemas.DisagreementAnalysis,  # Reusing schema
}


def get_schema_for_output_key(output_key: str) -> Optional[Type[schemas.ImmutableModel]]:
  """Gets the schema class for an agent output key."""
  return AGENT_SCHEMA_MAP.get(output_key)


def validate_agent_output_by_key(
    raw_output: str,
    output_key: str,
    agent_name: str = 'unknown',
) -> ValidationResult:
  """Validates agent output using the output_key to find the schema.
  
  Args:
    raw_output: Raw text output from agent.
    output_key: Output key from agent definition.
    agent_name: Name of the agent for logging.
  
  Returns:
    ValidationResult with validation status.
  """
  schema_class = get_schema_for_output_key(output_key)
  if schema_class is None:
    logger.warning('No schema found for output_key %s, skipping validation', output_key)
    return ValidationResult(
        valid=True,  # Don't fail if no schema defined
        raw_output=raw_output,
    )
  
  return validate_agent_output(raw_output, schema_class, agent_name)
