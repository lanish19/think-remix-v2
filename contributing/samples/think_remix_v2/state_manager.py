"""State management utilities for THINK Remix v2.0 workflow."""

from __future__ import annotations

from collections.abc import MutableMapping
import copy
from dataclasses import dataclass, field
from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Any
from typing import Iterable
from typing import Optional
from typing import TypedDict

from google.adk.tools.tool_context import ToolContext

logger = logging.getLogger(__name__)


class CERFact(TypedDict, total=False):
  """Type definition for a CER fact entry."""
  fact_id: str
  statement: str
  source: str
  source_type: str
  credibility_score: float
  date_accessed: str
  registered_at: str
  metadata: Optional[dict[str, Any]]


class AuditEvent(TypedDict, total=False):
  """Type definition for an audit event."""
  timestamp: str
  event: str
  fact_id: str
  source_type: str
  credibility_score: float
  persona_id: str


DEFAULT_STATE_SNAPSHOT = {
    'cer_registry': [],
    'cer_next_id': 1,
    'cer_daily_sequences': {},
    'persona_analyses': [],
    'null_hypotheses': [],
    'null_hypotheses_result': {},
    'research_objectives': [],
    'adjudications': {},
    'workflow_audit_trail': [],
}


def _get_state_keys_safely(state: MutableMapping[str, Any]) -> set[str]:
  """Safely get keys from State object or dict.
  
  NEVER calls .keys() directly on state - always uses to_dict() first
  or the 'in' operator which works for both dicts and State objects.
  """
  state_keys = set()

  # Strategy 1: Try to_dict() for State objects (safest method)
  try:
    if hasattr(state, 'to_dict') and callable(getattr(state, 'to_dict', None)):
      state_dict = state.to_dict()
      # state_dict should be a regular dict, so .keys() is safe
      if isinstance(state_dict, dict):
        state_keys = set(state_dict.keys())
        # If we got keys successfully, return early
        if state_keys:
          return state_keys
  except Exception as e:
    # If to_dict() fails, fall through to fallback
    logger.debug('Could not get keys via to_dict(): %s', e)

  # Strategy 2: Fallback - build state_keys using 'in' operator
  # This works for both dicts and State objects WITHOUT calling .keys()
  # Check each key in DEFAULT_STATE_SNAPSHOT to see if it exists in state
  for key in DEFAULT_STATE_SNAPSHOT:
    try:
      if key in state:
        state_keys.add(key)
    except (AttributeError, TypeError):
      # Skip this key if we can't check it
      continue

  return state_keys


def _validate_existing_state_types(state: MutableMapping[str, Any], keys: set[str]) -> None:
  """Validate types of existing state keys before modification."""
  if 'cer_registry' in keys and not isinstance(state['cer_registry'], list):
    raise TypeError('Existing cer_registry must be a list')
  if 'persona_analyses' in keys and not isinstance(state['persona_analyses'], list):
    raise TypeError('Existing persona_analyses must be a list')


def _validate_state_types(state: MutableMapping[str, Any]) -> None:
  """Validate all state types after initialization."""
  if not isinstance(state['cer_registry'], list):
    raise TypeError('Expected cer_registry to be a list.')
  if not isinstance(state['persona_analyses'], list):
    raise TypeError('Expected persona_analyses to be a list.')

  # null_hypotheses should be a list for internal state management
  if not isinstance(state['null_hypotheses'], list):
    # Handle dict case explicitly (agent output may be dict)
    if isinstance(state['null_hypotheses'], dict):
      if 'null_hypotheses' in state['null_hypotheses']:
        state['null_hypotheses'] = state['null_hypotheses']['null_hypotheses']
      else:
        state['null_hypotheses'] = []
    else:
      state['null_hypotheses'] = []
    logger.warning('Converted null_hypotheses from non-list type to list')

  # null_hypotheses_result is the agent output dict
  if not isinstance(state['null_hypotheses_result'], dict):
    raise TypeError(
        f'Expected null_hypotheses_result to be a dict, '
        f'got {type(state["null_hypotheses_result"])}'
    )


def _initialize_mapping(state: MutableMapping[str, Any]) -> None:
  """Initialize state with proper type validation and deep copies."""
  try:
    # Get existing keys safely
    state_keys = _get_state_keys_safely(state)

    # Validate existing state types BEFORE modifying
    _validate_existing_state_types(state, state_keys)

    # Initialize missing keys with deep copies
    for key, default_value in DEFAULT_STATE_SNAPSHOT.items():
      if key not in state_keys:
        try:
          state[key] = (
              copy.deepcopy(default_value)
              if isinstance(default_value, (dict, list))
              else default_value
          )
        except Exception as e:
          # If deepcopy fails (e.g., due to State objects), use shallow copy or direct assignment
          logger.warning('Deep copy failed for key %s, using direct assignment: %s', key, e)
          state[key] = default_value

    # Final type validation
    _validate_state_types(state)
  except AttributeError as e:
    # Catch any AttributeError (like 'keys' not found) and provide better error message
    if 'keys' in str(e):
      logger.error(
          'State object does not support .keys() method. '
          'This should have been handled by _get_state_keys_safely(). '
          'Error: %s', e
      )
      # Try to recover by using fallback method
      state_keys = set()
      for key in DEFAULT_STATE_SNAPSHOT:
        try:
          if key in state:
            state_keys.add(key)
        except Exception:
          continue
      # Retry initialization with recovered keys
      for key, default_value in DEFAULT_STATE_SNAPSHOT.items():
        if key not in state_keys:
          state[key] = (
              copy.deepcopy(default_value)
              if isinstance(default_value, (dict, list))
              else default_value
          )
      _validate_state_types(state)
    else:
      raise


def initialize_state_mapping(state: MutableMapping[str, Any]) -> None:
  """Initializes state using a generic mutable mapping."""
  _initialize_mapping(state)


def initialize_state(tool_context: ToolContext) -> None:
  """Initializes structured state expected by THINK Remix workflow."""
  _initialize_mapping(tool_context.state)


def _ensure_state_initialized(tool_context: ToolContext) -> None:
  if 'cer_registry' not in tool_context.state:
    initialize_state(tool_context)


@dataclass
class StateManager:
  """High-level helper wrapping ToolContext state."""

  tool_context: ToolContext = field(repr=False)

  def __post_init__(self) -> None:
    _ensure_state_initialized(self.tool_context)

  @property
  def cer_registry(self) -> list[dict[str, Any]]:
    return self.tool_context.state['cer_registry']

  @property
  def persona_analyses(self) -> list[dict[str, Any]]:
    return self.tool_context.state['persona_analyses']

  @persona_analyses.setter
  def persona_analyses(self, value: Iterable[dict[str, Any]]) -> None:
    self.tool_context.state['persona_analyses'] = list(value)

  @property
  def null_hypotheses(self) -> list[dict[str, Any]]:
    return self.tool_context.state['null_hypotheses']

  @null_hypotheses.setter
  def null_hypotheses(self, value: Iterable[dict[str, Any]]) -> None:
    self.tool_context.state['null_hypotheses'] = list(value)

  def next_fact_id(self, date_accessed: Optional[str] = None) -> str:
    """Generates a CER fact identifier scoped to calendar date."""
    date_token = date_accessed or datetime.utcnow().strftime('%Y%m%d')
    sequences = self.tool_context.state.setdefault('cer_daily_sequences', {})
    next_sequence = sequences.get(date_token, 1)
    sequences[date_token] = next_sequence + 1
    return f'CER-{date_token}-{next_sequence:03d}'

  def register_fact(
      self,
      *,
      fact_id: str,
      statement: str,
      source: str,
      source_type: str,
      credibility_score: float,
      date_accessed: str,
      metadata: Optional[dict[str, Any]] = None,
  ) -> dict[str, Any]:
    """Stores a fact entry inside the CER registry."""
    entry = {
        'fact_id': fact_id,
        'statement': statement,
        'source': source,
        'source_type': source_type,
        'credibility_score': round(float(credibility_score), 4),
        'date_accessed': date_accessed,
        'registered_at': datetime.utcnow().isoformat(timespec='seconds'),
    }
    if metadata:
      entry['metadata'] = metadata

    self.cer_registry.append(entry)
    self.tool_context.state['cer_next_id'] = (
        self.tool_context.state.get('cer_next_id', 1) + 1
    )
    return entry

  def get_fact(self, fact_id: str) -> Optional[dict[str, Any]]:
    """Looks up a fact by identifier."""
    return next(
        (fact for fact in self.cer_registry if fact['fact_id'] == fact_id), None
    )

  def save_state(self, filepath: str | Path) -> None:
    """Persists workflow state to disk for offline inspection."""
    path = Path(filepath)
    snapshot = {
        key: self.tool_context.state.get(key)
        for key in DEFAULT_STATE_SNAPSHOT
    }
    path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding='utf-8')

  def load_state(self, filepath: str | Path) -> None:
    """Loads workflow state from disk."""
    path = Path(filepath)
    try:
      data = json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
      logger.error('Invalid JSON in state file %s: %s', path, e)
      raise ValueError(f'Invalid JSON in state file: {e}') from e
    except FileNotFoundError:
      logger.error('State file not found: %s', path)
      raise
    except Exception as e:
      logger.error('Error loading state file %s: %s', path, e)
      raise

    for key, default_value in DEFAULT_STATE_SNAPSHOT.items():
      if key in data:
        self.tool_context.state[key] = data[key]
      elif key not in self.tool_context.state:
        self.tool_context.state[key] = (
            copy.deepcopy(default_value)
            if isinstance(default_value, (dict, list))
            else default_value
        )

  def append_audit_event(self, event: dict[str, Any]) -> None:
    """Adds an entry to workflow audit trail."""
    self.tool_context.state['workflow_audit_trail'].append(
        {
            'timestamp': datetime.utcnow().isoformat(timespec='seconds'),
            **event,
        }
    )

