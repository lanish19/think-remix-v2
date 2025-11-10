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

"""Persona analysis tools for THINK Remix workflow."""

from __future__ import annotations

import logging
from typing import Any

from google.adk.tools.tool_context import ToolContext

from ..state_manager import StateManager
from ..state_manager import initialize_state

logger = logging.getLogger(__name__)


def tool(func):
  """Lightweight decorator for parity with ADK tool expectations."""
  setattr(func, '_think_remix_tool', True)
  return func


@tool
def record_persona_analysis(
    persona_result: dict[str, Any],
    tool_context: ToolContext,
) -> dict[str, Any]:
  """Stores persona analysis output inside workflow state.

  Args:
    persona_result: Dictionary containing persona analysis results.
      Must include 'persona_id' key.
    tool_context: Tool context providing access to workflow state.

  Returns:
    The persona_result dictionary that was stored.

  Raises:
    ValueError: If persona_result is missing 'persona_id' key.
  """
  initialize_state(tool_context)
  manager = StateManager(tool_context)
  persona_id = persona_result.get('persona_id')
  if not persona_id:
    raise ValueError('persona_result must contain persona_id.')

  # Remove any existing analysis with the same persona_id (deduplication)
  updated_analyses = [
      analysis
      for analysis in manager.persona_analyses
      if analysis.get('persona_id') != persona_id
  ]
  updated_analyses.append(persona_result)
  manager.persona_analyses = updated_analyses

  manager.append_audit_event(
      {
          'event': 'record_persona_analysis',
          'persona_id': persona_id,
      }
  )

  logger.info('Recorded persona analysis for: %s', persona_id)

  return persona_result
