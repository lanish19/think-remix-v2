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

"""Perplexity API search tool for THINK Remix v2.0."""

from __future__ import annotations

import logging
import os
from typing import Any

import requests

from google.adk.tools.function_tool import FunctionTool

logger = logging.getLogger(__name__)

PERPLEXITY_API_URL = 'https://api.perplexity.ai/chat/completions'
PERPLEXITY_MODEL = 'llama-3.1-sonar-large-128k-online'


def _search_perplexity(
    query: str,
    model: str = PERPLEXITY_MODEL,
    max_results: int = 10,
) -> dict[str, Any]:
  """Search using Perplexity API.
  
  Args:
    query: Search query string.
    model: Perplexity model to use (default: llama-3.1-sonar-large-128k-online).
    max_results: Maximum number of results to return.
  
  Returns:
    Dictionary with search results including citations.
  """
  api_key = os.getenv('PERPLEXITY_API_KEY')
  if not api_key:
    raise ValueError(
        'PERPLEXITY_API_KEY environment variable not set. '
        'Please set it to use Perplexity search.'
    )
  
  headers = {
      'Authorization': f'Bearer {api_key}',
      'Content-Type': 'application/json',
  }
  
  payload = {
      'model': model,
      'messages': [
          {
              'role': 'user',
              'content': query,
          }
      ],
      'temperature': 0.2,
      'max_tokens': 4096,
  }
  
  try:
    response = requests.post(
        PERPLEXITY_API_URL,
        headers=headers,
        json=payload,
        timeout=30.0,
    )
    response.raise_for_status()
    data = response.json()
    
    # Extract content and citations from Perplexity response
    content = ''
    citations = []
    
    if 'choices' in data and len(data['choices']) > 0:
      choice = data['choices'][0]
      if 'message' in choice:
        content = choice['message'].get('content', '')
        # Perplexity includes citations in the content as [1], [2], etc.
        # and provides citations array
        if 'citations' in choice.get('message', {}):
          citations = choice['message']['citations']
    
    # Format results similar to Google Search Tool format
    results = []
    if content:
      results.append({
          'title': 'Perplexity AI Response',
          'snippet': content,
          'link': '',  # Perplexity doesn't provide a single link
          'citations': citations,
      })
    
    return {
        'results': results[:max_results],
        'total_results': len(results),
        'query': query,
        'source': 'perplexity',
    }
      
  except requests.HTTPError as e:
    logger.error('Perplexity API request failed: %s', e)
    raise ValueError(f'Perplexity API request failed: {e}') from e
  except requests.RequestException as e:
    logger.error('Perplexity API request error: %s', e)
    raise ValueError(f'Perplexity API request error: {e}') from e
  except Exception as e:
    logger.error('Unexpected error calling Perplexity API: %s', e)
    raise ValueError(f'Unexpected error calling Perplexity API: {e}') from e


# Create the Perplexity search tool
perplexity_search_tool = FunctionTool(
    func=_search_perplexity,
    name='perplexity_search',
    description=(
        'Search the web using Perplexity AI. Perplexity provides real-time web search '
        'with citations. Use this for comprehensive research queries that benefit from '
        'synthesized answers with source citations. Returns search results with citations.'
    ),
)
