"""Unit tests for THINK Remix V2 perplexity tool rate limiting."""

from __future__ import annotations

import concurrent.futures
import os
import time
from unittest.mock import Mock
from unittest.mock import patch

import pytest

from contributing.samples.think_remix_v2.perplexity_tool import brave_search


def test_rate_limiting_enforced():
  """Test that rate limiting delays requests."""
  with patch('contributing.samples.think_remix_v2.perplexity_tool.requests.get') as mock_get:
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'web': {'results': []}}
    mock_get.return_value = mock_response

    # Set API key for testing
    with patch.dict(os.environ, {'BRAVE_API_KEY': 'test_key'}):
      start = time.time()
      brave_search('test query 1')
      brave_search('test query 2')
      elapsed = time.time() - start

      # Should take at least 1.1 seconds due to rate limiting
      assert elapsed >= 1.1
      assert mock_get.call_count == 2


def test_concurrent_requests_thread_safe():
  """Test that concurrent requests don't violate rate limits."""
  with patch('contributing.samples.think_remix_v2.perplexity_tool.requests.get') as mock_get:
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'web': {'results': []}}
    mock_get.return_value = mock_response

    # Set API key for testing
    with patch.dict(os.environ, {'BRAVE_API_KEY': 'test_key'}):
      start = time.time()

      with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(brave_search, f'query {i}') for i in range(3)]
        results = [f.result() for f in futures]

      elapsed = time.time() - start

      # Should take at least 2.2 seconds (3 requests with 1.1s delay)
      assert elapsed >= 2.2
      assert len(results) == 3
      assert mock_get.call_count == 3


def test_brave_search_missing_api_key():
  """Test that missing API key raises ValueError."""
  with patch.dict(os.environ, {}, clear=True):
    with pytest.raises(ValueError, match='BRAVE_API_KEY'):
      brave_search('test query')


def test_brave_search_rate_limit_error():
  """Test that rate limit errors are handled correctly."""
  with patch('contributing.samples.think_remix_v2.perplexity_tool.requests.get') as mock_get:
    mock_response = Mock()
    mock_response.status_code = 429
    mock_response.text = 'Rate limit exceeded'
    mock_response.json.return_value = {
        'error': {'detail': 'Rate limit exceeded'}
    }
    mock_get.return_value = mock_response

    with patch.dict(os.environ, {'BRAVE_API_KEY': 'test_key'}):
      with pytest.raises(ValueError, match='rate limit'):
        brave_search('test query')

