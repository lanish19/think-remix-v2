"""Compatibility helpers for ADK State objects lacking mapping helpers."""

from __future__ import annotations

import importlib
from typing import Any
from typing import Mapping

_PATCHED_CLASSES: set[type[Any]] = set()


def _state_to_dict(state: Any) -> dict[str, Any]:
  """Best-effort conversion of a state-like object to a dictionary."""
  if state is None:
    return {}
  if isinstance(state, dict):
    return state
  if isinstance(state, Mapping):
    return dict(state.items())
  if hasattr(state, 'to_dict'):
    to_dict = getattr(state, 'to_dict')
    if callable(to_dict):
      try:
        maybe_dict = to_dict()
      except Exception:
        maybe_dict = None
      if isinstance(maybe_dict, dict):
        return maybe_dict
  return {}


def _ensure_class_has_mapping_methods(cls: type[Any]) -> None:
  """Ensure the given class exposes dict-like helpers."""
  if cls in _PATCHED_CLASSES:
    return

  def _keys(self: Any):
    return _state_to_dict(self).keys()

  def _items(self: Any):
    return _state_to_dict(self).items()

  def _values(self: Any):
    return _state_to_dict(self).values()

  def _iter(self: Any):
    return iter(_state_to_dict(self))

  def _len(self: Any) -> int:
    return len(_state_to_dict(self))

  if not hasattr(cls, 'keys'):
    setattr(cls, 'keys', _keys)
  if not hasattr(cls, 'items'):
    setattr(cls, 'items', _items)
  if not hasattr(cls, 'values'):
    setattr(cls, 'values', _values)
  if not hasattr(cls, '__iter__'):
    setattr(cls, '__iter__', _iter)
  if not hasattr(cls, '__len__'):
    setattr(cls, '__len__', _len)

  _PATCHED_CLASSES.add(cls)


def ensure_state_mapping_methods(state: Any) -> None:
  """Ensure the provided state-like object exposes dict-style helpers."""
  if state is None:
    return
  state_cls = state.__class__
  _ensure_class_has_mapping_methods(state_cls)


def bootstrap_known_state_classes() -> None:
  """Patch known ADK State classes when available."""
  candidates: list[type[Any]] = []
  for module_name, attr_name in (
      ('google.adk.sessions.state', 'State'),
      ('google.adk.sessions', 'State'),
  ):
    try:
      module = importlib.import_module(module_name)
    except ImportError:
      continue
    candidate = getattr(module, attr_name, None)
    if isinstance(candidate, type):
      candidates.append(candidate)

  for cls in candidates:
    _ensure_class_has_mapping_methods(cls)


bootstrap_known_state_classes()

