"""Tests for persona analysis utilities."""

from __future__ import annotations

from contributing.samples.think_remix_v2 import persona_analysis


def test_find_ignored_high_credibility_facts():
  persona_analyses = [
      {
          'persona_id': 'a',
          'evidence': {
              'ignored': [{'fact_id': 'CER-001'}, {'fact_id': 'CER-002'}],
          },
      },
      {
          'persona_id': 'b',
          'evidence': {
              'ignored': [{'fact_id': 'CER-001'}],
          },
      },
      {
          'persona_id': 'c',
          'evidence': {
              'ignored': [{'fact_id': 'CER-003'}],
          },
      },
  ]
  cer_registry = [
      {'fact_id': 'CER-001', 'credibility_score': 0.9},
      {'fact_id': 'CER-002', 'credibility_score': 0.88},
      {'fact_id': 'CER-003', 'credibility_score': 0.6},
  ]

  results = persona_analysis.find_ignored_high_credibility_facts(
      persona_analyses,
      cer_registry,
      ignore_threshold=0.6,
      min_credibility=0.85,
  )

  fact_ids = {fact['fact_id'] for fact in results}
  assert fact_ids == {'CER-001'}
