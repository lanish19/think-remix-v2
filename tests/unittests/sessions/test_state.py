"""Unit tests for google.adk.sessions.state.State mapping helpers."""

from __future__ import annotations

import importlib
import importlib.util
import sys
import types
from pathlib import Path

_STATE_MODULE_PATH = (
    Path(__file__).resolve().parents[3] / 'src/google/adk/sessions/state.py'
)
_STATE_SPEC = importlib.util.spec_from_file_location(
    'adk_state_module', _STATE_MODULE_PATH
)
if _STATE_SPEC is None or _STATE_SPEC.loader is None:
  raise ImportError('Could not load State module specification')
_STATE_MODULE = importlib.util.module_from_spec(_STATE_SPEC)
_STATE_SPEC.loader.exec_module(_STATE_MODULE)

State = _STATE_MODULE.State


def _load_state_manager_module():
  """Loads state_manager with stubbed ToolContext dependencies."""
  module_name = 'think_remix_state_manager_for_tests'
  if module_name in sys.modules:
    return sys.modules[module_name]

  # Stub minimal google.adk.tools.tool_context module expected by state_manager.
  if 'google' not in sys.modules:
    google_pkg = types.ModuleType('google')
    google_pkg.__path__ = []
    sys.modules['google'] = google_pkg
  if 'google.adk' not in sys.modules:
    adk_pkg = types.ModuleType('google.adk')
    adk_pkg.__path__ = []
    sys.modules['google.adk'] = adk_pkg
  if 'google.adk.tools' not in sys.modules:
    tools_pkg = types.ModuleType('google.adk.tools')
    sys.modules['google.adk.tools'] = tools_pkg
  if 'google.adk.tools.tool_context' not in sys.modules:
    tool_context_module = types.ModuleType('google.adk.tools.tool_context')

    class _StubToolContext:
      def __init__(self):
        self.state = None

    tool_context_module.ToolContext = _StubToolContext
    sys.modules['google.adk.tools.tool_context'] = tool_context_module

  state_manager_path = (
      Path(__file__).resolve().parents[3] /
      'contributing/samples/think_remix_v2/state_manager.py'
  )
  spec = importlib.util.spec_from_file_location(module_name, state_manager_path)
  if spec is None or spec.loader is None:
    raise ImportError('Could not load state_manager module specification')
  module = importlib.util.module_from_spec(spec)
  sys.modules[module_name] = module
  spec.loader.exec_module(module)
  return module


def _load_state_compat_module():
  """Loads state_compat without importing the full sample package."""
  module_name = 'think_remix_state_compat_for_tests'
  if module_name in sys.modules:
    return sys.modules[module_name]

  module_path = (
      Path(__file__).resolve().parents[3] /
      'contributing/samples/think_remix_v2/state_compat.py'
  )
  spec = importlib.util.spec_from_file_location(module_name, module_path)
  if spec is None or spec.loader is None:
    raise ImportError('Could not load state_compat module specification')
  module = importlib.util.module_from_spec(spec)
  sys.modules[module_name] = module
  spec.loader.exec_module(module)
  return module


def test_state_keys_items_and_len_reflect_current_state():
  """State should expose dict-like helpers such as keys(), items(), values()."""
  state = State({'foo': 1}, {})

  # Mutate state to ensure delta entries are included.
  state['bar'] = 2
  state['baz'] = 3

  assert set(state.keys()) == {'foo', 'bar', 'baz'}
  assert dict(state.items()) == {'foo': 1, 'bar': 2, 'baz': 3}
  assert sorted(state.values()) == [1, 2, 3]
  assert list(iter(state)) == ['foo', 'bar', 'baz']
  assert len(state) == 3


def test_initialize_state_accepts_adk_state_without_keys_errors():
  """initialize_state should work when ToolContext.state is a State instance."""
  state_manager = _load_state_manager_module()
  tool_context_module = sys.modules['google.adk.tools.tool_context']
  ToolContext = tool_context_module.ToolContext

  ctx = ToolContext()
  ctx.state = State({}, {})

  # Should not raise AttributeError about missing keys().
  state_manager.initialize_state(ctx)

  assert isinstance(ctx.state['cer_registry'], list)
  assert 'cer_registry' in ctx.state


def test_ensure_state_mapping_methods_adds_helpers_for_legacy_state():
  """ensure_state_mapping_methods should backfill mapping helpers."""
  state_compat = _load_state_compat_module()

  class LegacyState:
    def __init__(self, value=None, delta=None):
      self._value = dict(value or {})
      self._delta = dict(delta or {})

    def __getitem__(self, key):
      if key in self._delta:
        return self._delta[key]
      return self._value[key]

    def __setitem__(self, key, value):
      self._value[key] = value
      self._delta[key] = value

    def __contains__(self, key):
      return key in self._value or key in self._delta

    def get(self, key, default=None):
      if key in self:
        return self[key]
      return default

    def setdefault(self, key, default=None):
      if key in self:
        return self[key]
      self[key] = default
      return default

    def to_dict(self):
      data = dict(self._value)
      data.update(self._delta)
      return data

  legacy = LegacyState({'foo': 1})
  legacy['bar'] = 2

  state_compat.ensure_state_mapping_methods(legacy)

  assert set(legacy.keys()) == {'foo', 'bar'}
  assert dict(legacy.items()) == {'foo': 1, 'bar': 2}
  assert sorted(legacy.values()) == [1, 2]
  assert list(iter(legacy)) == ['foo', 'bar']
  assert len(legacy) == 2


def test_register_fact_succeeds_with_legacy_state_without_keys():
  """StateManager.register_fact should work with legacy states via compat layer."""
  state_manager = _load_state_manager_module()
  state_compat = _load_state_compat_module()

  class LegacyState:
    def __init__(self, value=None, delta=None):
      self._value = dict(value or {})
      self._delta = dict(delta or {})

    def __getitem__(self, key):
      if key in self._delta:
        return self._delta[key]
      return self._value[key]

    def __setitem__(self, key, value):
      self._value[key] = value
      self._delta[key] = value

    def __contains__(self, key):
      return key in self._value or key in self._delta

    def get(self, key, default=None):
      if key in self:
        return self[key]
      return default

    def setdefault(self, key, default=None):
      if key in self:
        return self[key]
      self[key] = default
      return default

    def to_dict(self):
      data = dict(self._value)
      data.update(self._delta)
      return data

  state = LegacyState()
  ctx = types.SimpleNamespace(state=state)

  state_compat.ensure_state_mapping_methods(ctx.state)
  state_manager.initialize_state(ctx)

  manager = state_manager.StateManager(ctx)
  result = manager.register_fact(
      fact_id='CER-20250101-001',
      statement='Legacy state fact',
      source='https://example.com',
      source_type='primary',
      credibility_score=0.95,
      date_accessed='20250101',
  )

  assert result['fact_id'] == 'CER-20250101-001'
  assert ctx.state['cer_registry'][0]['fact_id'] == 'CER-20250101-001'

