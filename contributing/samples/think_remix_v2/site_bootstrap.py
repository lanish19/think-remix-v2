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

"""Bootstrap module to ensure State compatibility shim is loaded at process startup.

This module should be imported early in the application lifecycle (e.g., in the
main entrypoint or server startup code) to guarantee that ADK State objects
have the necessary mapping helpers (keys, items, values, etc.) before any
workflow or agent code runs.

Usage:
    import contributing.samples.think_remix_v2.site_bootstrap  # noqa: F401
"""

from __future__ import annotations

from .state_compat import bootstrap_known_state_classes

# Apply compatibility shim immediately on import
bootstrap_known_state_classes()

