"""State management utilities for THINK Remix v2.0 workflow."""

from __future__ import annotations

from collections.abc import MutableMapping
from dataclasses import dataclass, field
from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Any
from typing import Iterable
from typing import Optional

from google.adk.tools.tool_context import ToolContext

logger = logging.getLogger(__name__)


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


def _initialize_mapping(state: MutableMapping[str, Any]) -> None:
  # Handle State objects that don't support .items() or .keys() directly
  # State objects support dict-like access but may not have all dict methods
  state_keys = set()
  
  # Try to get keys via to_dict() - works for State objects
  try:
    if hasattr(state, 'to_dict'):
      state_dict = state.to_dict()
      # state_dict should be a regular dict, so .keys() is safe
      state_keys = set(state_dict.keys())
    elif hasattr(state, 'keys'):
      # For regular dicts, use .keys()
      state_keys = set(state.keys())
  except (AttributeError, TypeError):
    # If to_dict() or keys() fails, fall through to fallback
    pass
  
  # Fallback: build state_keys using 'in' operator (safest method)
  # This works for both dicts and State objects
  if not state_keys:
    for key in DEFAULT_STATE_SNAPSHOT:
      try:
        if key in state:
          state_keys.add(key)
      except (AttributeError, TypeError):
        # Skip this key if we can't check it
        continue
  
  for key, default_value in DEFAULT_STATE_SNAPSHOT.items():
    if key not in state_keys:
      state[key] = (
          default_value.copy()
          if isinstance(default_value, (dict, list))
          else default_value
      )

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
    raise TypeError(f'Expected null_hypotheses_result to be a dict, got {type(state["null_hypotheses_result"])}')


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
    data = json.loads(path.read_text(encoding='utf-8'))
    for key, default_value in DEFAULT_STATE_SNAPSHOT.items():
      if key in data:
        self.tool_context.state[key] = data[key]
      elif key not in self.tool_context.state:
        self.tool_context.state[key] = (
            default_value.copy()
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

