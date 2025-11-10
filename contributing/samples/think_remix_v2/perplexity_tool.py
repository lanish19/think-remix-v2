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

"""Brave Search API tool for THINK Remix v2.0."""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import requests

from google.adk.tools.function_tool import FunctionTool

from .config_loader import get_config

logger = logging.getLogger(__name__)

# Rate limiting state (simple in-memory tracking)
_last_request_time = 0.0
_rate_limit_delay = 1.1  # Seconds between requests (slightly more than 1s for safety)

BRAVE_API_URL = 'https://api.search.brave.com/res/v1/web/search'


def brave_search(
    query: str,
    max_results: int = 10,
) -> dict[str, Any]:
  """Search the web using Brave Search API. Brave provides real-time web search results with ranked results from their continuously refreshed index.
  
  Args:
    query: Search query string.
    max_results: Maximum number of results to return (1-20, default: 10).
  
  Returns:
    Dictionary with search results including title, url, snippet, and metadata.
  """
  # Load config to potentially override defaults
  try:
    config = get_config()
    brave_config = config.brave_config
    config_count = brave_config.get('count', max_results)
    if config_count != 10:
      max_results = config_count
  except Exception:
    # If config loading fails, use function defaults
    pass
  
  api_key = os.getenv('BRAVE_API_KEY')
  if not api_key:
    raise ValueError(
        'BRAVE_API_KEY environment variable not set. '
        'Please set it to use Brave search.'
    )
  
  # Validate max_results (Brave typically supports up to 20 results per request)
  count = max(1, min(20, max_results))
  
  headers = {
      'Accept': 'application/json',
      'Accept-Encoding': 'gzip',
      'X-Subscription-Token': api_key,
  }
  
  # Brave uses GET request with query parameters
  params = {
      'q': query,
      'count': count,
  }
  
  # Rate limiting: Ensure we don't exceed 1 request per second
  global _last_request_time  # pylint: disable=global-statement
  current_time = time.time()
  time_since_last = current_time - _last_request_time
  
  if time_since_last < _rate_limit_delay:
    sleep_time = _rate_limit_delay - time_since_last
    logger.info('Rate limiting: sleeping %.2f seconds before Brave API request', sleep_time)
    time.sleep(sleep_time)
  
  _last_request_time = time.time()
  
  try:
    response = requests.get(
        BRAVE_API_URL,
        headers=headers,
        params=params,
        timeout=60.0,  # Increased timeout for reliability
    )
    
    # Log response details for debugging
    if response.status_code != 200:
      error_detail = response.text
      logger.error(
          'Brave API error: status=%d, response=%s, params=%s',
          response.status_code,
          error_detail,
          params,
      )
      
      # Handle rate limiting specifically
      if response.status_code == 429:
        try:
          error_data = response.json()
          error_info = error_data.get('error', {})
          detail = error_info.get('detail', 'Rate limit exceeded')
          raise ValueError(
              f'Brave API rate limit exceeded: {detail}. '
              f'Please wait before retrying. Free plan allows 1 request per second.'
          )
        except (ValueError, KeyError):
          raise ValueError(
              f'Brave API rate limit exceeded (429). '
              f'Please wait before retrying. Free plan allows 1 request per second.'
          )
      
      raise ValueError(
          f'Brave API request failed with status {response.status_code}: {error_detail}'
      )
    
    response.raise_for_status()
    
    # Parse JSON response
    try:
      data = response.json()
    except ValueError as e:
      logger.error('Failed to parse Brave API JSON response: %s', e)
      raise ValueError(f'Invalid JSON response from Brave API: {e}') from e
    
    # Extract results from Brave Search API response
    results = []
    if 'web' in data and 'results' in data['web']:
      web_results = data['web']['results']
      if isinstance(web_results, list):
        for result in web_results:
          if not isinstance(result, dict):
            logger.warning('Skipping invalid result (not a dict): %s', type(result))
            continue
          
          # Extract page age if available
          page_age = result.get('page_age', '')
          if not page_age:
            # Fallback to other date fields if available
            page_age = result.get('fetched_content_timestamp', '')
          
          # Ensure we have at least a title or URL
          title = result.get('title', '')
          url = result.get('url', '')
          if not title and not url:
            logger.warning('Skipping result with no title or URL')
            continue
          
          results.append({
              'title': title,
              'snippet': result.get('description', ''),
              'link': url,
              'age': str(page_age) if page_age else '',
          })
      else:
        logger.warning('Brave API web.results is not a list: %s', type(web_results))
    else:
      logger.warning('Brave API response missing web.results: %s', list(data.keys()) if isinstance(data, dict) else 'not a dict')
    
    # Ensure we return at least an empty results list
    return {
        'results': results[:max_results],
        'total_results': len(results),
        'query': query,
        'source': 'brave',
    }
      
  except requests.HTTPError as e:
    logger.error('Brave API request failed: %s', e)
    raise ValueError(f'Brave API request failed: {e}') from e
  except requests.RequestException as e:
    logger.error('Brave API request error: %s', e)
    raise ValueError(f'Brave API request error: {e}') from e
  except Exception as e:
    logger.error('Unexpected error calling Brave API: %s', e)
    raise ValueError(f'Unexpected error calling Brave API: {e}') from e


# Create the Brave search tool (keeping name for backward compatibility)
perplexity_search_tool = FunctionTool(func=brave_search)
