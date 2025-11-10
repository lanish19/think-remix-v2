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
"""Utility functions for session service."""
from __future__ import annotations

from typing import Any
from typing import Optional
from typing import Type
from typing import TypeVar

from .state import State

M = TypeVar("M")


def decode_model(
    data: Optional[dict[str, Any]], model_cls: Type[M]
) -> Optional[M]:
  """Decodes a pydantic model object from a JSON dictionary."""
  if data is None:
    return None
  return model_cls.model_validate(data)


def extract_state_delta(
    state: dict[str, Any] | Any,
) -> dict[str, dict[str, Any]]:
  """Extracts app, user, and session state deltas from a state-like object.

  Accepts either a plain dict or an ADK State object. Never calls .keys()
  on the State object directly; converts to a dict first.
  """
  deltas: dict[str, dict[str, Any]] = {"app": {}, "user": {}, "session": {}}
  if not state:
    return deltas

  # Convert State -> dict safely
  data: dict[str, Any] | None = None
  try:
    if hasattr(state, "to_dict") and callable(getattr(state, "to_dict", None)):
      maybe_dict = state.to_dict()
      if isinstance(maybe_dict, dict):
        data = maybe_dict
    elif isinstance(state, dict):
      data = state
  except Exception:
    # Fall through to empty deltas on failure
    data = None

  if not data:
    return deltas

  for key, value in data.items():
    if key.startswith(State.APP_PREFIX):
      deltas["app"][key.removeprefix(State.APP_PREFIX)] = value
    elif key.startswith(State.USER_PREFIX):
      deltas["user"][key.removeprefix(State.USER_PREFIX)] = value
    elif not key.startswith(State.TEMP_PREFIX):
      deltas["session"][key] = value
  return deltas
