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

"""Evidence management tools for Central Evidence Registry (CER)."""

from __future__ import annotations

import logging
import math
from datetime import datetime
from typing import Any
from typing import Literal
from typing import Optional

from google.adk.tools.tool_context import ToolContext

from ..config_loader import get_config
from ..state_compat import ensure_state_mapping_methods
from ..state_manager import StateManager
from ..state_manager import initialize_state

logger = logging.getLogger(__name__)


def tool(func):
  """Lightweight decorator for parity with ADK tool expectations."""
  setattr(func, '_think_remix_tool', True)
  return func


def _get_source_credibility_scores() -> dict[str, float]:
  """Get source credibility scores from config."""
  config = get_config()
  return config.source_credibility_scores


SOURCE_CREDIBILITY_SCORES: dict[str, float] = _get_source_credibility_scores()


def _normalize_source_type(source_type: str) -> str:
  """Normalize source type to lowercase and validate."""
  normalized = source_type.strip().lower()
  if normalized not in SOURCE_CREDIBILITY_SCORES:
    return 'tertiary'
  return normalized


def _normalize_date_token(date_accessed: Optional[str]) -> str:
  """Normalize date token to YYYYMMDD format."""
  if date_accessed:
    date_accessed = date_accessed.strip()
    # Try to parse if not already in YYYYMMDD format
    if len(date_accessed) == 8 and date_accessed.isdigit():
      return date_accessed
    # Try parsing other formats
    try:
      dt = datetime.strptime(date_accessed, '%Y-%m-%d')
      return dt.strftime('%Y%m%d')
    except ValueError:
      logger.warning('Invalid date format: %s, using current date', date_accessed)
  return datetime.utcnow().strftime('%Y%m%d')


def _validate_credibility_score(
    credibility_override: Optional[float],
    normalized_source_type: str,
) -> float:
  """Validate and normalize credibility score."""
  base_score = SOURCE_CREDIBILITY_SCORES.get(normalized_source_type, 0.55)
  if credibility_override is not None:
    try:
      credibility = float(credibility_override)
    except (ValueError, TypeError) as e:
      raise TypeError(
          f'credibility_override must be a number, got {type(credibility_override).__name__}'
      ) from e

    if math.isnan(credibility) or math.isinf(credibility):
      raise ValueError(f'Invalid credibility_override: {credibility_override} (NaN or Inf)')

    credibility = max(0.0, min(1.0, credibility))
  else:
    credibility = base_score

  return credibility


@tool
def register_evidence(
    statement: str,
    source: str,
    source_type: Literal['primary', 'secondary', 'tertiary'],
    tool_context: ToolContext,
    *,
    date_accessed: Optional[str] = None,
    credibility_override: Optional[float] = None,
    research_track: Optional[Literal['confirmatory', 'disconfirmatory']] = None,
    analyst: Optional[str] = None,
) -> dict[str, Any]:
  """Registers evidence in the Central Evidence Registry with structured output.

  Args:
    statement: The evidence statement to register (max 10,000 chars).
    source: The source URL or citation (max 2,000 chars).
    source_type: Type of source ('primary', 'secondary', or 'tertiary').
    tool_context: Tool context providing access to workflow state.
    date_accessed: Optional date string (YYYYMMDD or YYYY-MM-DD format).
    credibility_override: Optional credibility score override (0.0-1.0).
    research_track: Optional research track ('confirmatory' or 'disconfirmatory').
    analyst: Optional analyst identifier.

  Returns:
    Dictionary containing the registered fact with fact_id, credibility_score, etc.
    On error, returns a dictionary with 'error' and 'status': 'failed'.
  """
  # INPUT VALIDATION
  # Check None values
  if statement is None:
    raise ValueError('Statement cannot be None')
  if not isinstance(statement, str):
    raise TypeError(f'Statement must be a string, got {type(statement).__name__}')
  if source is None:
    raise ValueError('Source cannot be None')
  if not isinstance(source, str):
    raise TypeError(f'Source must be a string, got {type(source).__name__}')

  # Check empty/whitespace
  statement = statement.strip()
  if len(statement) == 0:
    raise ValueError('Statement cannot be empty or whitespace-only')

  # Check length limits
  if len(statement) > 10000:
    raise ValueError('Statement exceeds maximum length (10000 chars)')
  if len(source) > 2000:
    raise ValueError('Source URL exceeds maximum length (2000 chars)')

  # Sanitize inputs (already trimmed, just truncate if needed)
  statement = statement[:10000]
  source = source.strip()[:2000]

  ensure_state_mapping_methods(getattr(tool_context, 'state', None))

  try:
    # Log state before initialization for debugging
    try:
      if hasattr(tool_context.state, 'to_dict') and callable(getattr(tool_context.state, 'to_dict', None)):
        state_dict = tool_context.state.to_dict()
        if isinstance(state_dict, dict):
          logger.debug('register_evidence called - checking state keys: %s', list(state_dict.keys()))
        else:
          logger.debug('register_evidence called - to_dict() returned non-dict: %s', type(state_dict))
      else:
        logger.debug('register_evidence called - state does not have to_dict() method')
    except (AttributeError, KeyError, TypeError) as e:
      logger.debug('register_evidence called - could not access state keys: %s', e)

    # Initialize state with retry logic (max 2 retries)
    max_init_retries = 2
    init_success = False
    for attempt in range(max_init_retries):
      try:
        initialize_state(tool_context)
        init_success = True
        break
      except TypeError as te:
        if attempt < max_init_retries - 1 and 'null_hypotheses' in str(te):
          logger.warning('Attempting to fix null_hypotheses state issue (attempt %d)', attempt + 1)
          # Ensure null_hypotheses is a list
          if 'null_hypotheses' in tool_context.state and not isinstance(tool_context.state['null_hypotheses'], list):
            logger.warning('Converting null_hypotheses from %s to list',
                          type(tool_context.state['null_hypotheses']))
            # If it's a dict with 'null_hypotheses' key, extract the list
            if isinstance(tool_context.state['null_hypotheses'], dict):
              if 'null_hypotheses' in tool_context.state['null_hypotheses']:
                tool_context.state['null_hypotheses'] = tool_context.state['null_hypotheses']['null_hypotheses']
              else:
                tool_context.state['null_hypotheses'] = []
            else:
              tool_context.state['null_hypotheses'] = []
        else:
          # Re-raise if can't fix or max retries reached
          raise

    if not init_success:
      raise RuntimeError('Failed to initialize state after retries')

    manager = StateManager(tool_context)

    logger.debug('StateManager created, CER registry size: %d', len(manager.cer_registry))

    normalized_source_type = _normalize_source_type(source_type)
    date_token = _normalize_date_token(date_accessed)
    fact_id = manager.next_fact_id(date_token)

    credibility = _validate_credibility_score(credibility_override, normalized_source_type)

    metadata: dict[str, Any] = {}
    if research_track:
      metadata['research_track'] = research_track
    if analyst:
      metadata['registered_by'] = analyst

    stored = manager.register_fact(
        fact_id=fact_id,
        statement=statement.strip(),
        source=source.strip(),
        source_type=normalized_source_type,
        credibility_score=credibility,
        date_accessed=date_token,
        metadata=metadata or None,
    )

    manager.append_audit_event(
        {
            'event': 'register_evidence',
            'fact_id': fact_id,
            'source_type': normalized_source_type,
            'credibility_score': stored['credibility_score'],
        }
    )

    logger.info('Successfully registered evidence: %s (credibility: %.2f)',
                fact_id, stored['credibility_score'])

    return stored
  except (ValueError, TypeError, AttributeError, KeyError, RuntimeError) as e:
    # Handle expected errors
    logger.error('Error in register_evidence: %s', e, exc_info=True)
    # If the error is caused by a State.keys() call somewhere in the stack,
    # attempt a minimal, no-initialize fallback to register the fact directly.
    try:
      if isinstance(e, AttributeError) and 'keys' in str(e):
        logger.warning('Attempting CER registration via fallback path due to keys() error')
        # Minimal normalization
        normalized_source_type = _normalize_source_type(source_type)
        date_token = _normalize_date_token(date_accessed)
        credibility = _validate_credibility_score(credibility_override, normalized_source_type)
        # Ensure CER structures exist without calling any initializer
        cer_registry = tool_context.state.get('cer_registry')
        if not isinstance(cer_registry, list):
          cer_registry = []
          tool_context.state['cer_registry'] = cer_registry
        sequences = tool_context.state.get('cer_daily_sequences')
        if not isinstance(sequences, dict):
          sequences = {}
          tool_context.state['cer_daily_sequences'] = sequences
        next_sequence = sequences.get(date_token, 1)
        sequences[date_token] = next_sequence + 1
        fact_id = f'CER-{date_token}-{next_sequence:03d}'
        entry = {
            'fact_id': fact_id,
            'statement': statement.strip()[:10000] if statement else '',
            'source': source.strip()[:2000] if source else '',
            'source_type': normalized_source_type,
            'credibility_score': round(float(credibility), 4),
            'date_accessed': date_token,
            'registered_at': datetime.utcnow().isoformat(timespec='seconds'),
        }
        meta: dict[str, Any] = {}
        if research_track:
          meta['research_track'] = research_track
        if analyst:
          meta['registered_by'] = analyst
        if meta:
          entry['metadata'] = meta
        cer_registry.append(entry)
        # Audit trail (best-effort)
        try:
          audit = tool_context.state.get('workflow_audit_trail')
          if isinstance(audit, list):
            audit.append(
                {
                    'timestamp': datetime.utcnow().isoformat(timespec='seconds'),
                    'event': 'register_evidence_fallback',
                    'fact_id': fact_id,
                    'source_type': normalized_source_type,
                    'credibility_score': entry['credibility_score'],
                }
            )
        except Exception:
          pass
        logger.info('Fallback CER registration succeeded: %s', fact_id)
        return entry
    except Exception as fallback_error:
      logger.error('Fallback CER registration failed: %s', fallback_error, exc_info=True)

    # Log detailed state information for debugging
    try:
      if hasattr(tool_context.state, 'to_dict') and callable(getattr(tool_context.state, 'to_dict', None)):
        state_dict = tool_context.state.to_dict()
        if isinstance(state_dict, dict):
          state_info = {k: type(v).__name__ for k, v in state_dict.items()}
          logger.error('State types at error: %s', state_info)
        else:
          logger.error('State to_dict() returned non-dict: %s', type(state_dict))
      else:
        logger.error('State does not have to_dict() method')
    except Exception as log_error:
      logger.error('Could not log state information: %s', log_error)

    # Return a valid response even on error so workflow can continue
    return {
        'fact_id': f'ERROR-{datetime.utcnow().strftime("%Y%m%d-%H%M%S")}',
        'statement': statement[:100] if statement else 'N/A',
        'error': str(e),
        'status': 'failed',
    }
  except Exception as e:
    # Unexpected errors - re-raise system exceptions
    if isinstance(e, (KeyboardInterrupt, SystemExit)):
      raise
    logger.critical('Unexpected error in register_evidence: %s', e, exc_info=True)
    raise  # Re-raise unexpected errors


@tool
def get_high_credibility_facts(
    min_credibility: float,
    tool_context: ToolContext,
) -> dict[str, Any]:
  """Retrieves facts from CER registry with credibility score >= min_credibility.

  Args:
    min_credibility: Minimum credibility score threshold (typically 0.80 for
      established facts).
    tool_context: Tool context providing access to workflow state.

  Returns:
    Dictionary with 'facts' list containing fact entries matching the threshold,
    and 'count' indicating total number of matching facts.
  """
  initialize_state(tool_context)
  manager = StateManager(tool_context)

  threshold = float(min_credibility)
  matching_facts = [
      fact
      for fact in manager.cer_registry
      if fact.get('credibility_score', 0.0) >= threshold
  ]

  logger.info(
      'Retrieved %d facts with credibility >= %.2f from CER registry',
      len(matching_facts),
      threshold,
  )

  return {
      'facts': matching_facts,
      'count': len(matching_facts),
      'min_credibility': threshold,
  }
