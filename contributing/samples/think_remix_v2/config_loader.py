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

"""Configuration loader for THINK Remix v2.0."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_CONFIG = {
    'workflow': {
        'thresholds': {
            'persona_similarity_max': 0.70,
            'cer_credibility_bedrock': 0.80,
            'fact_preservation_min': 0.70,
            'divergence_coverage_min': 0.90,
            'null_coverage_min': 1.00,
            'transcendent_insight_inclusion_min': 1.00,
        },
        'persona_allocation': {
            'simple_max_complexity': 2.5,
            'simple_count': 3,
            'moderate_max_complexity': 4.0,
            'moderate_count': 5,
            'complex_count': 7,
            'max_allocator_attempts': 3,
        },
        'validation': {
            'max_persona_validator_attempts': 3,
            'max_coverage_validator_attempts': 3,
            'max_schema_validation_retries': 2,
        },
        'optimization': {
            'enable_parallel_personas': True,
            'enable_early_termination': False,
            'early_termination_convergence_threshold': 0.85,
            'early_termination_confidence_threshold': 0.80,
            'enable_caching': False,
            'cache_ttl_hours': 24,
        },
        'source_credibility_scores': {
            'primary': 0.95,
            'secondary': 0.75,
            'tertiary': 0.55,
        },
        'search': {
            'provider': 'perplexity',
            'perplexity': {
                'model': 'llama-3.1-sonar-large-128k-online',
                'max_results': 10,
                'temperature': 0.2,
            },
            'google': {
                'num_results': 10,
            },
        },
    },
}


class Config:
  """Configuration manager for THINK Remix v2.0."""

  def __init__(self, config_path: str | Path | None = None):
    """Initialize configuration.
    
    Args:
      config_path: Path to config.yaml file. If None, uses default config.
    """
    if config_path is None:
      # Try to find config.yaml in the same directory as this file
      config_path = Path(__file__).parent / 'config.yaml'
    
    config_path = Path(config_path)
    
    if config_path.exists():
      try:
        with open(config_path, 'r', encoding='utf-8') as f:
          self._config = yaml.safe_load(f) or {}
        logger.info('Loaded configuration from %s', config_path)
      except Exception as e:
        logger.warning('Failed to load config from %s: %s. Using defaults.', config_path, e)
        self._config = DEFAULT_CONFIG.copy()
    else:
      logger.info('Config file not found at %s. Using defaults.', config_path)
      self._config = DEFAULT_CONFIG.copy()
    
    # Merge with defaults to ensure all keys exist
    self._config = self._merge_configs(DEFAULT_CONFIG, self._config)
    self._validate_config()

  def _merge_configs(self, default: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge user config with defaults."""
    result = default.copy()
    for key, value in user.items():
      if key in result and isinstance(result[key], dict) and isinstance(value, dict):
        result[key] = self._merge_configs(result[key], value)
      else:
        result[key] = value
    return result

  def _validate_config(self) -> None:
    """Validates configuration values."""
    thresholds = self._config['workflow']['thresholds']
    
    # Validate thresholds are in valid ranges
    assert 0.0 <= thresholds['persona_similarity_max'] <= 1.0, (
        'persona_similarity_max must be between 0.0 and 1.0'
    )
    assert 0.0 <= thresholds['cer_credibility_bedrock'] <= 1.0, (
        'cer_credibility_bedrock must be between 0.0 and 1.0'
    )
    assert 0.0 <= thresholds['fact_preservation_min'] <= 1.0, (
        'fact_preservation_min must be between 0.0 and 1.0'
    )
    assert 0.0 <= thresholds['divergence_coverage_min'] <= 1.0, (
        'divergence_coverage_min must be between 0.0 and 1.0'
    )
    assert thresholds['null_coverage_min'] == 1.0, (
        'null_coverage_min must be exactly 1.0'
    )
    
    # Validate persona allocation
    allocation = self._config['workflow']['persona_allocation']
    assert allocation['simple_count'] >= 3, 'simple_count must be at least 3'
    assert allocation['moderate_count'] >= 5, 'moderate_count must be at least 5'
    assert allocation['complex_count'] >= 7, 'complex_count must be at least 7'
    
    # Validate validation settings
    validation = self._config['workflow']['validation']
    assert validation['max_persona_validator_attempts'] > 0, (
        'max_persona_validator_attempts must be > 0'
    )
    assert validation['max_coverage_validator_attempts'] > 0, (
        'max_coverage_validator_attempts must be > 0'
    )
    assert validation['max_schema_validation_retries'] >= 0, (
        'max_schema_validation_retries must be >= 0'
    )

  def get(self, key_path: str, default: Any = None) -> Any:
    """Get configuration value using dot-notation path.
    
    Args:
      key_path: Dot-separated path to config value (e.g., 'workflow.thresholds.persona_similarity_max').
      default: Default value if key not found.
    
    Returns:
      Configuration value or default.
    """
    keys = key_path.split('.')
    value = self._config
    for key in keys:
      if isinstance(value, dict) and key in value:
        value = value[key]
      else:
        return default
    return value

  @property
  def persona_similarity_max(self) -> float:
    """Maximum allowed persona similarity."""
    return self.get('workflow.thresholds.persona_similarity_max', 0.70)

  @property
  def cer_credibility_bedrock(self) -> float:
    """CER credibility threshold for empirically settled facts."""
    return self.get('workflow.thresholds.cer_credibility_bedrock', 0.80)

  @property
  def fact_preservation_min(self) -> float:
    """Minimum fact preservation rate."""
    return self.get('workflow.thresholds.fact_preservation_min', 0.70)

  @property
  def divergence_coverage_min(self) -> float:
    """Minimum divergence coverage."""
    return self.get('workflow.thresholds.divergence_coverage_min', 0.90)

  @property
  def null_coverage_min(self) -> float:
    """Minimum null coverage (must be 1.0)."""
    return self.get('workflow.thresholds.null_coverage_min', 1.00)

  @property
  def max_persona_validator_attempts(self) -> int:
    """Maximum attempts for persona validator loop."""
    return self.get('workflow.validation.max_persona_validator_attempts', 3)

  @property
  def max_coverage_validator_attempts(self) -> int:
    """Maximum attempts for coverage validator loop."""
    return self.get('workflow.validation.max_coverage_validator_attempts', 3)

  @property
  def max_schema_validation_retries(self) -> int:
    """Maximum retries for schema validation failures."""
    return self.get('workflow.validation.max_schema_validation_retries', 2)

  @property
  def enable_parallel_personas(self) -> bool:
    """Whether to enable parallel persona execution."""
    return self.get('workflow.optimization.enable_parallel_personas', True)

  @property
  def enable_early_termination(self) -> bool:
    """Whether to enable early termination."""
    return self.get('workflow.optimization.enable_early_termination', False)

  @property
  def source_credibility_scores(self) -> dict[str, float]:
    """Source credibility scores by type."""
    return self.get('workflow.source_credibility_scores', {
        'primary': 0.95,
        'secondary': 0.75,
        'tertiary': 0.55,
    })
  
  @property
  def search_provider(self) -> str:
    """Search provider: 'google' or 'perplexity'."""
    return self.get('workflow.search.provider', 'perplexity')
  
  @property
  def perplexity_config(self) -> dict[str, Any]:
    """Perplexity API configuration."""
    return self.get('workflow.search.perplexity', {
        'model': 'llama-3.1-sonar-large-128k-online',
        'max_results': 10,
        'temperature': 0.2,
    })


# Global config instance
_config_instance: Config | None = None


def get_config(config_path: str | Path | None = None) -> Config:
  """Get or create global configuration instance.
  
  Args:
    config_path: Path to config file (only used on first call).
  
  Returns:
    Config instance.
  """
  global _config_instance
  if _config_instance is None:
    _config_instance = Config(config_path)
  return _config_instance
