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

"""Tools module for THINK Remix v2.0.

This module provides tools for evidence management and persona analysis:
- Evidence tools: register_evidence, get_high_credibility_facts
- Persona tools: record_persona_analysis
"""

from .evidence import get_high_credibility_facts
from .evidence import register_evidence
from .persona import record_persona_analysis

__all__ = [
    'register_evidence',
    'get_high_credibility_facts',
    'record_persona_analysis',
]
