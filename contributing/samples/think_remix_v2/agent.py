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

from __future__ import annotations

import json
import logging
import math
from datetime import datetime
from textwrap import dedent
from typing import Any
from typing import Callable
from typing import Iterable
from typing import Literal
from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.llm_agent import Agent
from google.adk.tools.google_search_tool import GoogleSearchTool
from google.adk.tools.tool_context import ToolContext
from google.genai import types

from .config_loader import get_config
from .perplexity_tool import perplexity_search_tool
from .state_manager import StateManager
from .state_manager import initialize_state
from .state_manager import initialize_state_mapping
from .workflow_agent import ThinkRemixWorkflowAgent

logger = logging.getLogger(__name__)


def _get_source_credibility_scores() -> dict[str, float]:
  """Get source credibility scores from config."""
  config = get_config()
  return config.source_credibility_scores


SOURCE_CREDIBILITY_SCORES: dict[str, float] = _get_source_credibility_scores()
JSON_ONLY_WARNING = (
    'CRITICAL: Output ONLY valid JSON. No preamble, markdown, or commentary.'
)

FRAMEWORK_REQUIREMENTS: dict[str, str] = {
    'Bayesian_Reasoning': (
        'Explicitly state priors, compute likelihood ratios for each major '
        'hypothesis, and report posterior odds influencing confidence.'
    ),
    'Complex_Systems': (
        'Map feedback loops, identify tipping points, and discuss path '
        'dependency or emergence in the phenomenon.'
    ),
    'Institutional_Economics': (
        'Analyze incentive structures, transaction costs, and institutional '
        'path dependence shaping outcomes.'
    ),
    'Behavioral_Economics': (
        'Examine cognitive biases, heuristics, and decision frictions that may '
        'distort agent behavior relative to rational models.'
    ),
    'Deterrence_Theory': (
        'Assess credibility of commitments, cost-benefit calculations of '
        'actors, and escalation ladders.'
    ),
    'Consequentialist_Ethics': (
        'Quantify expected value trade-offs, distributional impacts, and risk '
        'preferences driving normative stance.'
    ),
    'Deontological_Ethics': (
        'Evaluate duties, rights, and rule-consistency. Highlight any '
        'categorical imperatives that constrain recommendations.'
    ),
    'Systems_Safety': (
        'Apply failure mode analysis, defense-in-depth reasoning, and '
        'accident precursor detection.'
    ),
    'Evolutionary_Strategy': (
        'Consider adaptation, selection pressure, and evolutionary stable '
        'strategies shaping agent behavior.'
    ),
    'Network_Science': (
        'Analyze topology, centrality, contagion paths, and robustness of '
        'interconnected actors.'
    ),
}

def _get_search_tool():
  """Get the configured search tool based on config."""
  config = get_config()
  provider = config.search_provider.lower()
  
  if provider == 'brave' or provider == 'perplexity':
    # Both use the same tool (backward compatibility)
    return perplexity_search_tool
  else:
    # Default to Google Search
    return GoogleSearchTool(bypass_multi_tools_limit=True)


SEARCH_TOOL = _get_search_tool()


def tool(func: Callable[..., Any]) -> Callable[..., Any]:
  """Lightweight decorator for parity with ADK tool expectations."""
  setattr(func, '_think_remix_tool', True)
  return func


def _indent_block(block: str, prefix: str = '        ') -> str:
  return '\n'.join(f'{prefix}{line}' for line in dedent(block).strip().splitlines())


def _json_directive(template: str) -> str:
  formatted = _indent_block(template)
  return dedent(
      f"""
      {JSON_ONLY_WARNING}
      Respond with JSON matching exactly:
{formatted}
      """
  ).strip()


def _normalize_source_type(source_type: str) -> str:
  normalized = source_type.strip().lower()
  if normalized not in SOURCE_CREDIBILITY_SCORES:
    return 'tertiary'
  return normalized


def _normalize_date_token(date_accessed: Optional[str]) -> str:
  """Normalize date token to YYYYMMDD format."""
  if date_accessed:
    date_accessed = date_accessed.strip()
    # Try to parse if not already in YYYYMMDD format
    if len(date_accessed) == 8 and date_accessed.isdigit():
      return date_accessed
    # Try parsing other formats
    try:
      dt = datetime.strptime(date_accessed, '%Y-%m-%d')
      return dt.strftime('%Y%m%d')
    except ValueError:
      logger.warning('Invalid date format: %s, using current date', date_accessed)
  return datetime.utcnow().strftime('%Y%m%d')


def _validate_credibility_score(
    credibility_override: Optional[float],
    normalized_source_type: str,
) -> float:
  """Validate and normalize credibility score."""
  base_score = SOURCE_CREDIBILITY_SCORES.get(normalized_source_type, 0.55)
  if credibility_override is not None:
    try:
      credibility = float(credibility_override)
    except (ValueError, TypeError) as e:
      raise TypeError(
          f'credibility_override must be a number, got {type(credibility_override).__name__}'
      ) from e

    if math.isnan(credibility) or math.isinf(credibility):
      raise ValueError(f'Invalid credibility_override: {credibility_override} (NaN or Inf)')

    credibility = max(0.0, min(1.0, credibility))
  else:
    credibility = base_score

  return credibility


@tool
def register_evidence(
    statement: str,
    source: str,
    source_type: Literal['primary', 'secondary', 'tertiary'],
    tool_context: ToolContext,
    *,
    date_accessed: Optional[str] = None,
    credibility_override: Optional[float] = None,
    research_track: Optional[Literal['confirmatory', 'disconfirmatory']] = None,
    analyst: Optional[str] = None,
) -> dict[str, Any]:
  """Registers evidence in the Central Evidence Registry with structured output."""
  # INPUT VALIDATION
  # Check None values
  if statement is None:
    raise ValueError('Statement cannot be None')
  if not isinstance(statement, str):
    raise TypeError(f'Statement must be a string, got {type(statement).__name__}')
  if source is None:
    raise ValueError('Source cannot be None')
  if not isinstance(source, str):
    raise TypeError(f'Source must be a string, got {type(source).__name__}')

  # Check empty/whitespace
  statement = statement.strip()
  if len(statement) == 0:
    raise ValueError('Statement cannot be empty or whitespace-only')

  # Check length limits
  if len(statement) > 10000:
    raise ValueError('Statement exceeds maximum length (10000 chars)')
  if len(source) > 2000:
    raise ValueError('Source URL exceeds maximum length (2000 chars)')

  # Sanitize inputs (already trimmed, just truncate if needed)
  statement = statement[:10000]
  source = source.strip()[:2000]
  
  try:
    # Log state before initialization for debugging
    try:
      state_dict = tool_context.state.to_dict()
      logger.debug('register_evidence called - checking state keys: %s', list(state_dict.keys()))
    except (AttributeError, KeyError) as e:
      logger.debug('register_evidence called - could not access state keys: %s', e)

    # Initialize state with retry logic (max 2 retries)
    max_init_retries = 2
    init_success = False
    for attempt in range(max_init_retries):
      try:
        initialize_state(tool_context)
        init_success = True
        break
      except TypeError as te:
        if attempt < max_init_retries - 1 and 'null_hypotheses' in str(te):
          logger.warning('Attempting to fix null_hypotheses state issue (attempt %d)', attempt + 1)
          # Ensure null_hypotheses is a list
          if 'null_hypotheses' in tool_context.state and not isinstance(tool_context.state['null_hypotheses'], list):
            logger.warning('Converting null_hypotheses from %s to list',
                          type(tool_context.state['null_hypotheses']))
            # If it's a dict with 'null_hypotheses' key, extract the list
            if isinstance(tool_context.state['null_hypotheses'], dict):
              if 'null_hypotheses' in tool_context.state['null_hypotheses']:
                tool_context.state['null_hypotheses'] = tool_context.state['null_hypotheses']['null_hypotheses']
              else:
                tool_context.state['null_hypotheses'] = []
            else:
              tool_context.state['null_hypotheses'] = []
        else:
          # Re-raise if can't fix or max retries reached
          raise

    if not init_success:
      raise RuntimeError('Failed to initialize state after retries')

    manager = StateManager(tool_context)

    logger.debug('StateManager created, CER registry size: %d', len(manager.cer_registry))

    normalized_source_type = _normalize_source_type(source_type)
    date_token = _normalize_date_token(date_accessed)
    fact_id = manager.next_fact_id(date_token)

    credibility = _validate_credibility_score(credibility_override, normalized_source_type)

    metadata: dict[str, Any] = {}
    if research_track:
      metadata['research_track'] = research_track
    if analyst:
      metadata['registered_by'] = analyst

    stored = manager.register_fact(
        fact_id=fact_id,
        statement=statement.strip(),
        source=source.strip(),
        source_type=normalized_source_type,
        credibility_score=credibility,
        date_accessed=date_token,
        metadata=metadata or None,
    )

    manager.append_audit_event(
        {
            'event': 'register_evidence',
            'fact_id': fact_id,
            'source_type': normalized_source_type,
            'credibility_score': stored['credibility_score'],
        }
    )

    logger.info('Successfully registered evidence: %s (credibility: %.2f)',
                fact_id, stored['credibility_score'])

    return stored
  except (ValueError, TypeError, AttributeError, KeyError, RuntimeError) as e:
    # Handle expected errors
    logger.error('Error in register_evidence: %s', e, exc_info=True)
    # Log detailed state information for debugging
    try:
      state_dict = tool_context.state.to_dict()
      state_info = {k: type(v).__name__ for k, v in state_dict.items()}
      logger.error('State types at error: %s', state_info)
    except Exception as log_error:
      logger.error('Could not log state information: %s', log_error)

    # Return a valid response even on error so workflow can continue
    return {
        'fact_id': f'ERROR-{datetime.utcnow().strftime("%Y%m%d-%H%M%S")}',
        'statement': statement[:100] if statement else 'N/A',
        'error': str(e),
        'status': 'failed',
    }
  except Exception as e:
    # Unexpected errors - re-raise system exceptions
    if isinstance(e, (KeyboardInterrupt, SystemExit)):
      raise
    logger.critical('Unexpected error in register_evidence: %s', e, exc_info=True)
    raise  # Re-raise unexpected errors


async def _bootstrap_workflow_state(
    callback_context: CallbackContext,
) -> Optional[Any]:
  """Ensures workflow state scaffolding exists at invocation start."""
  initialize_state_mapping(callback_context.state)
  return None


async def _enforce_audit_gate(
    callback_context: CallbackContext,
) -> Optional[types.Content]:
  """Stops the workflow when the audit gate blocks or requests clarification."""
  audit = callback_context.state.get('question_audit_result')
  if not isinstance(audit, dict):
    return None

  status = audit.get('audit_status')
  if status == 'proceed' or status is None:
    return None

  payload: dict[str, Any] = {'audit_status': status}
  if status == 'request_clarification':
    payload['clarification_prompt'] = (
        audit.get('clarification_needed') or 'Please clarify your question.'
    )
    payload['error'] = 'Clarification required before workflow can proceed.'
  else:
    payload['error'] = (
        audit.get('proceed_justification')
        or audit.get('clarification_needed')
        or 'Question blocked by audit gate.'
    )

  callback_context._invocation_context.end_invocation = True  # pylint: disable=protected-access
  return types.Content(
      role='assistant', parts=[types.Part(text=json.dumps(payload))]
  )


@tool
def record_persona_analysis(
    persona_result: dict[str, Any],
    tool_context: ToolContext,
) -> dict[str, Any]:
  """Stores persona analysis output inside workflow state."""
  initialize_state(tool_context)
  manager = StateManager(tool_context)
  persona_id = persona_result.get('persona_id')
  if not persona_id:
    raise ValueError('persona_result must contain persona_id.')

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
  return persona_result


@tool
def get_high_credibility_facts(
    min_credibility: float,
    tool_context: ToolContext,
) -> dict[str, Any]:
  """Retrieves facts from CER registry with credibility score >= min_credibility.
  
  Args:
    min_credibility: Minimum credibility score threshold (typically 0.80 for
      established facts).
    tool_context: Tool context providing access to workflow state.
  
  Returns:
    Dictionary with 'facts' list containing fact entries matching the threshold,
    and 'count' indicating total number of matching facts.
  """
  initialize_state(tool_context)
  manager = StateManager(tool_context)
  
  threshold = float(min_credibility)
  matching_facts = [
      fact
      for fact in manager.cer_registry
      if fact.get('credibility_score', 0.0) >= threshold
  ]
  
  logger.info(
      'Retrieved %d facts with credibility >= %.2f from CER registry',
      len(matching_facts),
      threshold,
  )
  
  return {
      'facts': matching_facts,
      'count': len(matching_facts),
      'min_credibility': threshold,
  }


def _build_question_audit_instruction() -> str:
  preamble = dedent(
      """
      ROLE: QUESTION AUDITOR

      OBJECTIVE: Determine if the user's question is answerable, well-formed,
      and appropriately scoped. This gate blocks the workflow when requirements
      fail.

      AUDIT CHECKLIST:

      1. ANSWERABILITY CHECK
         - Can the question be answered with empirical evidence?
         - Does it demand metaphysical or purely normative judgment?
         - Classification: empirical | normative | hybrid | unanswerable

      2. SCOPE CHECK
         - Is the scope appropriately bounded for rigorous analysis?
         - Classification: appropriate | too_broad | too_narrow | malformed

      3. TEMPORAL CHECK
         - Does it require impossible foresight or real-time data?
         - Classification: feasible | requires_impossible_foresight |
           requires_realtime_data

      4. TYPE CLASSIFICATION
         - Determine archetype: causal | predictive | normative | diagnostic |
           comparative | hybrid

      DECISION LOGIC:
      - If answerability is unanswerable → BLOCK with explanation.
      - If scope is misaligned → request clarification with concrete prompt.
      - If temporal request is infeasible → block or reframe.
      - Otherwise → PROCEED with justification.
      """
  ).strip()
  schema = _json_directive(
      """
      {
        "audit_status": "proceed | block | request_clarification",
        "question_type": "causal | predictive | normative | diagnostic | comparative | hybrid",
        "answerability": "empirical | normative | hybrid | unanswerable",
        "scope_assessment": "appropriate | too_broad | too_narrow | malformed",
        "temporal_assessment": "feasible | requires_impossible_foresight | requires_realtime_data",
        "reframed_question": "string | null",
        "clarification_needed": "string | null",
        "proceed_justification": "string | null"
      }
      """
  )
  return f'{preamble}\n{schema}'


def _build_analyze_question_instruction() -> str:
  preamble = dedent(
      """
      ROLE: QUESTION ANALYST

      OBJECTIVE: Convert the audited question into an actionable research plan.

      TASKS:
      - Reframe the question for analytical precision.
      - Identify entities, mechanisms, stakeholders, and time horizons.
      - Enumerate evidence requirements with rationale and urgency.
      - Map explicit and implicit assumptions with potential failure modes.
      - Produce scaffolding for downstream persona allocation and research.
      """
  ).strip()
  schema = _json_directive(
      """
      {
        "core_question": "string",
        "question_type": "causal | predictive | normative | diagnostic | comparative | hybrid",
        "research_axes": [
          {
            "axis": "stakeholders | temporal_dimensions | causal_pathways | geographic_scope",
            "items": ["string"]
          }
        ],
        "required_evidence": [
          {
            "evidence_type": "statistical_series | natural_experiments | policy_analysis | expert_interviews | case_studies",
            "why_needed": "string",
            "priority": "high | medium | low"
          }
        ],
        "critical_assumptions": [
          {
            "assumption": "string",
            "risk_if_wrong": "string",
            "linked_nulls": ["NH-01"]
          }
        ],
        "complexity_estimators": {
          "stakeholder_count": 0,
          "temporal_dimensions": 0,
          "domain_crossings": 0,
          "known_unknowns": 0
        },
        "recommended_methodology": [
          {
            "step": 1,
            "focus": "string",
            "nulls_targeted": ["NH-01"]
          }
        ],
        "handoff_summary": "string"
      }
      """
  )
  return f'{preamble}\n{schema}'


def _build_generate_nulls_instruction() -> str:
  preamble = dedent(
      """
      ROLE: SKEPTICISM ARCHITECT

      OBJECTIVE: Generate 3-5 tailored null hypotheses aligned with the audited
      question type. Nulls must be falsifiable, high-signal, and cover distinct
      failure modes.

      REQUIREMENTS:
      - Provide mechanism, base-rate, and assumption-challenge nulls when relevant.
      - Align each null with explicit rejection criteria and required evidence.
      - Assign prior probabilities reflecting plausibility.
      """
  ).strip()
  schema = _json_directive(
      """
      {
        "null_hypotheses": [
          {
            "hypothesis_id": "NH-01",
            "null_claim": "string",
            "rejection_criteria": "string",
            "prior_probability": 0.15,
            "null_type": "mechanism | confounding | regime_change | unintended_consequence | base_rate | rights_violation",
            "assumptions_challenged": ["string"]
          }
        ],
        "coverage_summary": {
          "question_type": "causal | predictive | normative | diagnostic | comparative | hybrid",
          "completeness": "complete | partial",
          "gaps": ["string"]
        }
      }
      """
  )
  return f'{preamble}\n{schema}'


def _build_persona_allocator_instruction() -> str:
  preamble = dedent(
      """
      ROLE: PERSONA ALLOCATION STRATEGIST

      OBJECTIVE: Determine optimal persona count (3-7) based on complexity and
      design personas with distinct epistemological frameworks and heuristics.

      COMPLEXITY SCORE:
      complexity_score = (stakeholder_count × 0.30) +
                         (temporal_dimensions × 0.25) +
                         (domain_crossings × 0.25) +
                         (known_unknowns × 0.20)

      ALLOCATION RULES:
      - complexity_score ≤ 2.5 → 3 personas
      - 2.5 < complexity_score ≤ 4.0 → 5 personas
      - complexity_score > 4.0 → 7 personas

      DIVERSITY CONSTRAINTS:
      - Each persona must use a unique epistemological framework.
      - At least one persona must prioritize long-term (>5yr) horizon.
      - At least one persona must challenge default status quo assumptions.
      """
  ).strip()
  schema = _json_directive(
      """
      {
        "complexity_analysis": {
          "stakeholder_count": 0,
          "temporal_dimensions": 0,
          "domain_crossings": 0,
          "known_unknowns": 0,
          "complexity_score": 0.0,
          "recommended_persona_count": 5
        },
        "persona_count": 5,
        "personas": [
          {
            "id": "a",
            "persona_name": "string",
            "epistemological_framework": "Bayesian_Reasoning | Complex_Systems | Institutional_Economics | Behavioral_Economics | Deterrence_Theory | Consequentialist_Ethics | Deontological_Ethics | Systems_Safety",
            "analytical_focus": "string",
            "worldview": "string",
            "guiding_question": "string",
            "evidence_lens": "string",
            "time_horizon": "short_term | medium_term | long_term",
            "risk_orientation": "risk_seeking | risk_neutral | risk_averse",
            "diversity_tags": ["status_quo_challenger | contrarian | consensus_builder | long_term_guardian"]
          }
        ]
      }
      """
  )
  return f'{preamble}\n{schema}'


def _build_persona_validator_instruction() -> str:
  preamble = dedent(
      """
      ROLE: PERSONA DIVERGENCE VALIDATOR

      OBJECTIVE: Measure cognitive distance between personas. Reject if overlap
      exceeds threshold.

      SIMILARITY ASSESSMENT:
      - Evaluate worldview, guiding question, evidence lens, time horizon.
      - Use cosine-like similarity 0.0 (orthogonal) → 1.0 (identical).

      VALIDATION RULES:
      - PASS if all pairwise similarities < 0.70.
      - FAIL if any similarity ≥ 0.70 with remediation guidance.
      """
  ).strip()
  schema = _json_directive(
      """
      {
        "validation_status": "approved | requires_regeneration",
        "cognitive_distance_matrix": [
          {
            "pair": ["a", "b"],
            "similarity": 0.42,
            "overlap_dimensions": ["guiding_question"]
          }
        ],
        "redundancy_flags": [
          {
            "persona_ids": ["b", "c"],
            "issue": "shared worldview framing",
            "remediation": "swap framework to Complex_Systems"
          }
        ],
        "diversity_checks": {
          "unique_frameworks": true,
          "long_term_present": true,
          "status_quo_challenger_present": true
        }
      }
      """
  )
  return f'{preamble}\n{schema}'


STANDARDIZED_JUDGMENT_SCHEMA = _json_directive(
    """
    {
      "persona_id": "string",
      "persona_name": "string",
      "epistemological_framework": "string",
      "conclusion": {
        "answer": "string",
        "confidence_percentage": 72,
        "primary_driver": "CER-20250115-001"
      },
      "reasoning": {
        "critical_assumptions": [
          {
            "assumption": "string",
            "invalidation_criteria": "string",
            "monitoring_plan": "string"
          }
        ],
        "analytic_path": [
          {
            "step": "string",
            "supporting_facts": ["CER-20250115-001"],
            "nulls_considered": ["NH-01"],
            "confidence_shift": -0.06
          }
        ]
      },
      "evidence": {
        "prioritized": [
          {"fact_id": "CER-20250115-001", "weight": 0.23}
        ],
        "discounted": [
          {"fact_id": "CER-20250115-015", "rationale": "low credibility"}
        ],
        "ignored": [
          {"fact_id": "CER-20250115-020", "reason": "out-of-scope"}
        ]
      },
      "null_hypothesis_assessment": [
        {
          "null_id": "NH-01",
          "status": "Reject | Accept | Partially_Accept",
          "decisive_facts": ["CER-20250115-003"]
        }
      ],
      "transcendent_insight": {
        "triggered": false,
        "insight": "string | null"
      }
    }
    """
)


def _build_gather_insights_instruction() -> str:
  preamble = dedent(
      """
      ROLE: COMPREHENSIVE RESEARCH SPECIALIST

      OBJECTIVE: Conduct expansive web research on the user question, cataloging
      every distinct factual claim into the Central Evidence Registry (CER).

      EXPECTATIONS:
      - Perform iterative search (2-3 queries minimum) exploring heterogeneous
        sources (academic, industry, institutional, investigative).
      - IMPORTANT: Due to API rate limits, space out your search queries.
        The system will automatically handle rate limiting, but be patient.
      - For every distinct factual statement:
        1. Extract verbatim claim (no paraphrase).
        2. Record source URL and publication metadata.
        3. Classify source type (primary | secondary | tertiary).
        4. Invoke register_evidence tool immediately.
      - Track search strategy evolution for downstream transparency.
      """
  ).strip()
  schema = _json_directive(
      """
      {
        "summary": "string",
        "facts_registered": ["CER-20250115-001"],
        "search_strategy": [
          {
            "query": "string",
            "rationale": "string",
            "results_considered": 12,
            "insights": ["string"]
          }
        ],
        "coverage_metrics": {
          "primary_sources": 4,
          "secondary_sources": 8,
          "tertiary_sources": 3
        }
      }
      """
  )
  return f'{preamble}\n{schema}'


def _build_synthesis_instruction() -> str:
  preamble = dedent(
      """
      ROLE: SIGNAL INTEGRATION ENGINE

      OBJECTIVE: Synthesize conflicting persona analyses by identifying conditional
      domains where each framework is valid. You are NOT averaging—you are
      integrating conditional truth regimes.

      METHOD:
      - Access persona analyses from previous agent outputs (look for outputs with keys
        like "persona_analysis_a", "persona_analysis_b", etc.) or from conversation history.
      - Extract divergence points between personas and map boundary conditions.
      - Build conditional logic: "If [condition], then [conclusion]."
      - Weight evidence by CER credibility. Facts <0.60 credibility cannot be
        load-bearing.
      - Highlight remaining conflicts for further adjudication.
      """
  ).strip()
  schema = _json_directive(
      """
      {
        "conditional_conclusions": [
          {
            "condition": "string",
            "conclusion": "string",
            "supporting_facts": ["CER-20250115-001"],
            "confidence": 0.63
          }
        ],
        "consensus_zones": ["string"],
        "active_disagreements": ["DD-01"],
        "evidence_map": [
          {
            "fact_id": "CER-20250115-001",
            "used_by_personas": ["a", "c"],
            "credibility_score": 0.92
          }
        ]
      }
      """
  )
  return f'{preamble}\n{schema}'


def _build_adversarial_instruction() -> str:
  preamble = dedent(
      """
      ROLE: ADVERSARIAL EVIDENCE INJECTOR

      OBJECTIVE: Identify high-credibility evidence ignored by most personas and
      develop counter-arguments rooted in those blind spots.

      STEPS:
      - Access persona analyses from previous agent outputs (look for outputs with keys
        like "persona_analysis_a", "persona_analysis_b", etc.) or from the conversation
        history where persona agents recorded their analyses.
      - Parse persona analyses and gather ignored evidence lists.
      - Detect CER facts ignored by ≥60% of personas with credibility ≥0.85.
      - Construct adversarial reasoning using those facts.
      - If no candidates exist, state explicitly.
      """
  ).strip()
  schema = _json_directive(
      """
      {
        "exploited_blind_spots": [
          {
            "fact_id": "CER-20250115-021",
            "credibility_score": 0.9,
            "ignored_by": ["a", "b", "c", "d"],
            "adversarial_argument": "string"
          }
        ],
        "adversarial_conclusion": {
          "answer": "string",
          "confidence_percentage": 48,
          "divergence_from_majority": "string"
        },
        "notes": "string"
      }
      """
  )
  return f'{preamble}\n{schema}'


def _build_disagreement_instruction() -> str:
  preamble = dedent(
      """
      ROLE: DISAGREEMENT ANALYST

      OBJECTIVE: Map convergence, divergence, and root causes across persona,
      synthesis, and adversarial outputs.

      TASKS:
      - Access persona analyses, synthesis result, and adversarial result from previous
        agent outputs in the conversation history.
      - Extract conclusions, identify semantic conflicts, and classify conflict
        types (Core_Conflict, Constraint_Challenge, etc.).
      - Evaluate relevancy hypothesis from persona allocator.
      - Flag transcendent insights and compute framework fidelity scores.
      """
  ).strip()
  schema = _json_directive(
      """
      {
        "convergence_points": ["string"],
        "divergence_drivers": [
          {
            "disagreement_id": "DD-01",
            "point_of_disagreement": "string",
            "conflict_type": "Core_Conflict | Constraint_Challenge | Interpretive_Gap",
            "positions": [
              {"persona_id": "a", "answer": "string", "driven_by": "string"}
            ],
            "root_cause_type": "Different_Assumption | Evidence_Weighting | Time_Horizon",
            "resolvability": "Empirically_Testable | Philosophical | Requires_New_Data"
          }
        ],
        "framework_fidelity_scores": [
          {"persona_id": "a", "score": 0.82}
        ],
        "transcendent_insights_flagged": ["string"],
        "relevancy_hypothesis_assessment": {
          "status": "Validated | Challenged",
          "rationale": "string"
        }
      }
      """
  )
  return f'{preamble}\n{schema}'


def _build_null_adjudicator_instruction() -> str:
  preamble = dedent(
      """
      ROLE: NULL HYPOTHESIS ADJUDICATOR

      OBJECTIVE: Aggregate persona judgments to render rulings on each null
      hypothesis using evidence strength and consensus.

      INPUT:
      - Access null hypotheses from the generate_null_hypotheses agent output
        (key: "null_hypotheses_result") in conversation history or state.
      - Access persona analyses from previous agent outputs (look for outputs with keys
        like "persona_analysis_a", "persona_analysis_b", etc.) or from conversation history.
      - Each persona analysis should contain null_hypothesis_assessment sections.

      RULES:
      - Reject if ≥70% reject AND ≥2 high-credibility (≥0.85) facts support.
      - SPECIAL CASE: If persona consensus for rejection is unanimous (100% reject),
        you SHOULD issue a "Reject" ruling even if there are fewer than 2 high-credibility
        facts available, as unanimous consensus is strong evidence. Do NOT default to
        "Undetermined" when there is unanimous rejection consensus - use "Reject" and
        explain the limitation in the notes field.
      - Accept if ≥50% accept AND no contradictory high-credibility facts.
      - Otherwise mark Undetermined.
      - Compute skepticism_score capturing residual doubt (0.0-1.0).
      - In notes, explicitly state when rulings are affected by missing evidence
        registration (e.g., "Unanimous rejection consensus (7/7) but cannot validate
        due to no high-credibility CER facts being registered. Ruling based on persona
        consensus alone.").
      """
  ).strip()
  schema = _json_directive(
      """
      {
        "null_adjudications": [
          {
            "null_id": "NH-01",
            "ruling": "Reject | Accept | Undetermined",
            "supporting_facts": ["CER-20250115-004"],
            "dissenting_facts": ["CER-20250115-007"],
            "persona_vote_summary": {
              "reject": 4,
              "accept": 1,
              "partially_accept": 1
            }
          }
        ],
        "skepticism_score": 0.37,
        "notes": "string"
      }
      """
  )
  return f'{preamble}\n{schema}'


def _build_conduct_research_instruction() -> str:
  preamble = dedent(
      """
      ROLE: DUAL-TRACK RESEARCHER

      OBJECTIVE: Execute targeted confirmatory and disconfirmatory research for
      each inquiry objective supplied by the strategist.

      INPUT:
      - Access search_inquiry_plan from previous agent output (key: "search_inquiry_plan").
      - Access synthesis_result to understand the mainstream conclusion for disconfirmatory searches.

      MANDATE:
      - For every objective run two tracks:
        Track 1: Confirmatory evidence supporting resolution (1-2 searches).
        Track 2: Disconfirmatory evidence challenging consensus (1-2 searches).
      - IMPORTANT: Keep searches focused due to API rate limits.
        The system automatically handles rate limiting between requests.
      - Each finding must register via register_evidence with research_track tag.
      - Report disconfirmatory_ratio (facts tagged disconfirmatory ÷ total).
      """
  ).strip()
  schema = _json_directive(
      """
      {
        "objectives_completed": [
          {
            "objective_id": "IO-01",
            "confirmatory_facts": ["CER-20250115-051"],
            "disconfirmatory_facts": ["CER-20250115-054"],
            "notes": "string"
          }
        ],
        "disconfirmatory_ratio": 0.32,
        "execution_log": [
          {
            "objective_id": "IO-01",
            "track": "confirmatory | disconfirmatory",
            "queries": ["string"]
          }
        ]
      }
      """
  )
  return f'{preamble}\n{schema}'


def _build_evidence_consistency_instruction() -> str:
  preamble = dedent(
      """
      ROLE: EVIDENCE CONSISTENCY ENFORCER

      OBJECTIVE: Detect cherry-picking across persona analyses using CER
      credibility scores.

      INPUT:
      - Access persona analyses from previous agent outputs (look for outputs with keys
        like "persona_analysis_a", "persona_analysis_b", etc.) or from conversation history.

      CHECKS:
      - High-credibility ignoring: evidence ignored with credibility >0.85.
      - Low-credibility prioritization: evidence prioritized with credibility <0.60.
      - Coverage ratio: prioritized facts ÷ CER facts cited.
      - Compute integrity_score (0.0-1.0).
      """
  ).strip()
  schema = _json_directive(
      """
      {
        "persona_integrity": [
          {
            "persona_id": "a",
            "coverage_ratio": 0.46,
            "violations": [
              {
                "type": "high_credibility_ignoring",
                "fact_id": "CER-20250115-021",
                "credibility": 0.91,
                "severity": "critical"
              }
            ],
            "integrity_score": 0.71
          }
        ],
        "global_findings": {
          "high_credibility_ignored": ["CER-20250115-021"],
          "low_credibility_prioritized": ["CER-20250115-060"],
          "flagged_personas": ["b", "d"]
        }
      }
      """
  )
  return f'{preamble}\n{schema}'


def _build_evidence_adjudicator_instruction() -> str:
  preamble = dedent(
      """
      ROLE: EVIDENCE ADJUDICATOR

      OBJECTIVE: Resolve disagreements by comparing competing CER facts and
      determining which carry decisive weight.

      INPUT:
      - Access disagreement_analysis from previous agent output (key: "disagreement_analysis").
      - Access null_adjudications from previous agent output (key: "null_adjudications").

      TASKS:
      - For each divergence driver, map competing evidence sets.
      - Compare credibility, redundancy, and alignment with null rulings.
      - Classify resolution strength (strong | moderate | unresolvable).
      """
  ).strip()
  schema = _json_directive(
      """
      {
        "resolution_summary": [
          {
            "disagreement_id": "DD-01",
            "resolution": "strong | moderate | unresolvable",
            "winning_facts": ["CER-20250115-011"],
            "losing_facts": ["CER-20250115-019"],
            "justification": "string"
          }
        ],
        "load_bearing_facts": ["CER-20250115-011"],
        "unresolvable_conflicts": ["DD-03"]
      }
      """
  )
  return f'{preamble}\n{schema}'


def _build_case_file_instruction() -> str:
  preamble = dedent(
      """
      ROLE: CASE FILE ARCHITECT

      OBJECTIVE: Produce structured case file consolidating adjudicated evidence,
      disagreements, uncertainties, and directives for the arbiter.

      INPUT:
      - CRITICAL: Use the get_high_credibility_facts tool with min_credibility=0.80
        to retrieve facts from the CER registry. Populate section_1.established_facts
        with facts returned by this tool. Each fact should include fact_id and statement.
      - Access null hypotheses from null_hypotheses_result (key: "null_hypotheses_result")
        in conversation history or state.
      - Access gather_insights_result, disagreement_analysis, blindspot_analysis,
        and evidence_adjudication from previous agent outputs in conversation history.
      - CRITICAL: For section_2.competing_frameworks, you MUST include ALL disagreements
        from disagreement_analysis.divergence_drivers. Iterate through every entry
        in divergence_drivers and include each one with its disagreement_id.

      REQUIREMENTS:
      - Section 1: Empirically Settled (credibility >0.80). MUST be populated from
        cer_registry state. If cer_registry is empty or has no facts with credibility >0.80,
        established_facts must be an empty list [].
      - Section 2: Legitimately Contested (unresolved conflicts). MUST include ALL
        disagreements from disagreement_analysis.divergence_drivers. Missing any
        disagreement_id is a critical error.
      - Section 3: Irreducible Uncertainties (insufficient evidence).
      - Section 4: Directives for Arbiter (null summaries, insights).
      - Provide compression_report counts.
      """
  ).strip()
  schema = _json_directive(
      """
      {
        "section_1": {
          "established_facts": [
            {"fact_id": "CER-20250115-011", "statement": "string"}
          ]
        },
        "section_2": {
          "competing_frameworks": [
            {
              "disagreement_id": "DD-01",
              "positions": [
                {"persona_id": "a", "stance": "string", "evidence": ["CER-..."]}
              ]
            }
          ]
        },
        "section_3": {
          "irreducible_uncertainties": [
            {"description": "string", "impact": "string"}
          ]
        },
        "section_4": {
          "null_hypothesis_summary": [
            {"null_id": "NH-01", "ruling": "Reject", "implication": "string"}
          ],
          "transcendent_insights": ["string"]
        },
        "compression_report": {
          "facts_included": 24,
          "facts_registered": 38,
          "coverage_ratio": 0.63
        }
      }
      """
  )
  return f'{preamble}\n{schema}'


def _build_coverage_validator_instruction() -> str:
  preamble = dedent(
      """
      ROLE: COVERAGE VALIDATOR

      OBJECTIVE: Ensure case file preserves critical information.

      INPUT:
      - Access case_file from previous agent output (key: "case_file").
      - Access disagreement_analysis, null_adjudications, and gather_insights_result
        from previous agent outputs in conversation history.

      METRICS:
      - fact_preservation_rate ≥ 0.70 for high-credibility facts.
      - divergence_coverage ≥ 0.90.
      - null_coverage must equal 1.00.
      - transcendent insights must be fully preserved.
      - Report gaps for regeneration when failing thresholds.
      """
  ).strip()
  schema = _json_directive(
      """
      {
        "fact_preservation_rate": 0.78,
        "divergence_coverage": 0.92,
        "null_coverage": 1.0,
        "transcendent_insight_inclusion": 1.0,
        "passed": true,
        "gaps": ["string"]
      }
      """
  )
  return f'{preamble}\n{schema}'


def _build_robustness_instruction() -> str:
  preamble = dedent(
      """
      ROLE: DECISION ROBUSTNESS CALCULATOR

      OBJECTIVE: Quantify decision robustness, sensitivity, and brittleness.

      INPUT:
      - Access case_file and null_adjudications from previous agent outputs in
        conversation history.

      TASKS:
      - Calculate Decision Robustness Score (DRS) using load-bearing evidence.
      - Derive sensitivity score and flip scenarios.
      - Determine confidence_ceiling for final arbiter.
      """
  ).strip()
  schema = _json_directive(
      """
      {
        "decision_robustness_score": 0.73,
        "interpretation": "robust | moderate | fragile",
        "components": {
          "credibility_sum": 5.6,
          "unresolved_conflicts": 1,
          "accepted_nulls": 0
        },
        "sensitivity_score": 0.31,
        "confidence_ceiling": 0.72,
        "flip_scenarios": ["CER-20250115-019 credibility drops below 0.7"],
        "assumption_brittleness": [
          {"assumption": "string", "brittleness": 0.44}
        ]
      }
      """
  )
  return f'{preamble}\n{schema}'


def _build_final_arbiter_instruction() -> str:
  preamble = dedent(
      """
      ROLE: ADAPTIVE SYNTHESIS ARBITER

      OBJECTIVE: Deliver final judgment with quantified robustness, explicit
      sensitivity, and transparent uncertainty acknowledgement.

      INPUT:
      - Access case_file (key: "case_file") and robustness_metrics (key: "robustness_metrics")
        from previous agent outputs in conversation history.

      CONSTRAINTS:
      1. Confidence cannot exceed confidence_ceiling from robustness metrics.
      2. Provide three-step justification trace (empirical bedrock, conflict
         resolution, uncertainty handling).
      3. Include sensitivity disclosure describing flip conditions.
      4. Acknowledge accepted or undetermined null hypotheses explicitly.
      5. CRITICAL: Final answer must ONLY reference CER fact_ids that are explicitly
         present in case_file.section_1.established_facts. You MUST verify each fact_id
         you cite exists in that list. If case_file.section_1.established_facts is empty,
         you MUST NOT cite any fact_ids and instead explicitly state that conclusions
         are based on synthesis or persona agreement but lack formally registered evidence.
         Do NOT hallucinate or invent fact_ids that do not exist in established_facts.
      6. If no established_facts exist, acknowledge this limitation transparently in
         your final_answer and justification_trace.
      """
  ).strip()
  schema = _json_directive(
      """
      {
        "final_answer": "string (600-800 words)",
        "decision_robustness_score": 0.73,
        "confidence_percentage": 72,
        "confidence_ceiling": 72,
        "justification_trace": {
          "step_1_empirical_bedrock": {
            "fact_id": "CER-20250115-011",
            "explanation": "string"
          },
          "step_2_conflict_resolution": {
            "disagreement_id": "DD-01",
            "resolution": "string",
            "supporting_facts": ["CER-20250115-011"]
          },
          "step_3_uncertainty_handling": {
            "uncertainty": "string",
            "strategy": "hedge | assume | bound | pilot",
            "impact": "string"
          }
        },
        "sensitivity_disclosure": {
          "conclusion_flips_if": ["CER-20250115-019 credibility drops below 0.70"]
        },
        "null_hypothesis_acknowledgment": [
          {"null_id": "NH-02", "status": "Undetermined", "constraint": "string"}
        ]
      }
      """
  )
  return f'{preamble}\n{schema}'


def _build_analyze_blindspots_instruction() -> str:
  preamble = dedent(
      """
      ROLE: BLINDSPOT ANALYST

      OBJECTIVE: Detect uniformly ignored evidence, shared assumptions, and
      unanimous null rejections indicating groupthink.

      INPUT:
      - Access persona analyses from previous agent outputs (look for outputs with keys
        like "persona_analysis_a", "persona_analysis_b", etc.) or from conversation history.
      """
  ).strip()
  schema = _json_directive(
      """
      {
        "uniformly_ignored_facts": ["CER-20250115-070"],
        "shared_assumption_risks": [
          {
            "assumption": "string",
            "personas": ["a", "b", "c", "d", "e"],
            "similarity": 0.89
          }
        ],
        "null_rejection_uniformity": [
          {"null_id": "NH-03", "status": "Reject", "personas": ["a","b","c"]}
        ],
        "notes": "string"
      }
      """
  )
  return f'{preamble}\n{schema}'


def _build_search_inquiry_instruction() -> str:
  preamble = dedent(
      """
      ROLE: SEARCH INQUIRY STRATEGIST

      OBJECTIVE: Generate prioritized inquiry objectives leveraging disagreement,
      blindspot, and transcendent insights data.

      INPUT:
      - Access disagreement_analysis and blindspot_analysis from previous agent outputs
        in the conversation history.

      PRIORITIZATION ORDER:
      1. Transcendent insights requiring verification.
      2. Empirically testable core conflicts.
      3. Adversarial challenges.
      4. Load-bearing elements.
      5. Shared assumption risks.
      """
  ).strip()
  schema = _json_directive(
      """
      {
        "inquiry_objectives": [
          {
            "objective_id": "IO-01",
            "priority_rank": 1,
            "central_question": "string",
            "hallmarks_of_discriminating_evidence": ["string"],
            "linked_disagreements": ["DD-01"],
            "linked_blindspots": ["CER-20250115-070"]
          }
        ]
      }
      """
  )
  return f'{preamble}\n{schema}'


def _build_qa_instruction() -> str:
  preamble = dedent(
      """
      ROLE: QUALITY ASSURANCE AUDITOR

      OBJECTIVE: Stress test the case file and arbiter plan with adversarial
      questions and audit notes.

      INPUT:
      - Access case_file from previous agent output (key: "case_file").
      """
  ).strip()
  schema = _json_directive(
      """
      {
        "auditor_note_on_bedrock": "string",
        "auditor_note_on_dissent": "string",
        "auditor_note_on_uncertainty": "string",
        "auditor_note_red_team_challenge": ["string"],
        "value_of_information": [
          {"uncertainty": "string", "voi_estimate": 0.42}
        ]
      }
      """
  )
  return f'{preamble}\n{schema}'


# Agent definitions ---------------------------------------------------------

question_audit_agent = Agent(
    name='question_audit_gate',
    model='gemini-2.5-flash',
    instruction=_build_question_audit_instruction(),
    description='Validates that questions are answerable and well-formed.',
    output_key='question_audit_result',
    before_agent_callback=_bootstrap_workflow_state,
)

analyze_question_agent = Agent(
    name='analyze_question',
    model='gemini-2.5-flash',
    instruction=_build_analyze_question_instruction(),
    description='Analyzes question structure and creates research framework.',
    output_key='question_analysis',
    before_agent_callback=_enforce_audit_gate,
)

generate_nulls_agent = Agent(
    name='generate_null_hypotheses',
    model='gemini-2.5-flash',
    instruction=_build_generate_nulls_instruction(),
    description='Generates skeptical null hypotheses for falsification testing.',
    output_key='null_hypotheses_result',
)

gather_insights_agent = Agent(
    name='gather_insights',
    model='gemini-2.5-flash',
    instruction=_build_gather_insights_instruction(),
    description='Conducts comprehensive research and registers evidence in CER.',
    tools=[SEARCH_TOOL, register_evidence],
    output_key='gather_insights_result',
)

persona_allocator_agent = Agent(
    name='dynamic_persona_allocator',
    model='gemini-2.5-flash',
    instruction=_build_persona_allocator_instruction(),
    description='Allocates and designs diverse analytical personas.',
    output_key='persona_allocation',
)

persona_validator_agent = Agent(
    name='persona_divergence_validator',
    model='gemini-2.5-flash',
    instruction=_build_persona_validator_instruction(),
    description='Validates that personas have sufficient cognitive diversity.',
    output_key='persona_validation',
)


def create_persona_agent(
    persona_config: dict[str, Any],
    cer_facts: Iterable[dict[str, Any]],
) -> Agent:
  """Dynamically creates a persona agent with standardized judgment schema."""
  framework = persona_config['epistemological_framework']
  persona_name = persona_config.get('persona_name', persona_config['id'])
  cer_fact_ids = [fact['fact_id'] for fact in cer_facts]

  evidence_hint = json.dumps(cer_fact_ids, indent=2)
  framework_guidance = FRAMEWORK_REQUIREMENTS.get(
      framework,
      'Invoke the core heuristics of your framework explicitly.',
  )
  persona_instruction = dedent(
      f"""
      ROLE: {persona_name.upper()}
      FRAMEWORK: {framework}

      CONTEXT:
      - Available evidence restricted to CER fact ids listed below.
      - You must produce standardized judgment schema JSON with complete trace.
      - Reference CER ids verbatim (no paraphrase) when citing evidence.

      AVAILABLE_CER_FACT_IDS:
      {evidence_hint}

      FRAMEWORK EXPECTATIONS:
      - {framework_guidance}
      - Do not deviate from the methodological commitments of {framework}.
      - Make posterior confidence explicit and justify shifts.

      OUTPUT REQUIREMENTS:
      - Use Standardized Judgment Schema below.
      - Populate every required field. Use null only when unavoidable.
      - Ensure evidence sections reference valid CER fact ids.
      - After producing the JSON schema, call record_persona_analysis with the JSON payload.
      """
  ).strip()

  return Agent(
      name=f"persona_{persona_config['id']}",
      model='gemini-2.5-pro',
      instruction=f'{persona_instruction}\n{STANDARDIZED_JUDGMENT_SCHEMA}',
      description=f'Dynamic persona agent for {persona_name}.',
      tools=[record_persona_analysis],
      output_key=f"persona_analysis_{persona_config['id']}",
  )


synthesis_agent = Agent(
    name='synthesis_engine',
    model='gemini-2.5-flash',
    instruction=_build_synthesis_instruction(),
    description='Synthesizes conflicting analyses into conditional conclusions.',
    output_key='synthesis_result',
)

adversarial_injector_agent = Agent(
    name='adversarial_evidence_injector',
    model='gemini-2.5-flash',
    instruction=_build_adversarial_instruction(),
    description='Injects adversarial evidence exploiting persona blind spots.',
    output_key='adversarial_result',
)

analyze_disagreement_agent = Agent(
    name='analyze_disagreement',
    model='gemini-2.5-flash',
    instruction=_build_disagreement_instruction(),
    description='Maps convergence and divergence across personas and synthesis.',
    output_key='disagreement_analysis',
)

null_adjudicator_agent = Agent(
    name='null_hypothesis_adjudicator',
    model='gemini-2.5-flash',
    instruction=_build_null_adjudicator_instruction(),
    description='Adjudicates null hypotheses using aggregated persona evidence.',
    output_key='null_adjudications',
)

conduct_research_agent = Agent(
    name='conduct_research_dual_track',
    model='gemini-2.5-flash',
    instruction=_build_conduct_research_instruction(),
    description='Executes confirmatory and disconfirmatory research tracks.',
    tools=[SEARCH_TOOL, register_evidence],
    output_key='targeted_research',
)

evidence_consistency_enforcer_agent = Agent(
    name='evidence_consistency_enforcer',
    model='gemini-2.5-flash',
    instruction=_build_evidence_consistency_instruction(),
    description='Detects cherry-picking and calculates integrity scores.',
    output_key='evidence_consistency',
)

evidence_adjudicator_agent = Agent(
    name='evidence_adjudicator',
    model='gemini-2.5-flash',
    instruction=_build_evidence_adjudicator_instruction(),
    description='Resolves disagreements by weighing competing evidence.',
    output_key='evidence_adjudication',
)

case_file_agent = Agent(
    name='case_file_compiler',
    model='gemini-2.5-flash',
    instruction=_build_case_file_instruction(),
    description='Compiles case file sections with traceability to CER.',
    tools=[get_high_credibility_facts],
    output_key='case_file',
)

coverage_validator_agent = Agent(
    name='coverage_validator',
    model='gemini-2.5-flash',
    instruction=_build_coverage_validator_instruction(),
    description='Validates coverage thresholds before final synthesis.',
    output_key='coverage_validation',
)

robustness_calculator_agent = Agent(
    name='decision_robustness_calculator',
    model='gemini-2.5-flash',
    instruction=_build_robustness_instruction(),
    description='Calculates robustness metrics and confidence ceilings.',
    output_key='robustness_metrics',
)

final_arbiter_agent = Agent(
    name='final_arbiter',
    model='gemini-2.5-flash',
    instruction=_build_final_arbiter_instruction(),
    description='Produces final judgment with quantified robustness and bounds.',
    output_key='final_arbiter_output',
)

analyze_blindspots_agent = Agent(
    name='analyze_blindspots',
    model='gemini-2.5-flash',
    instruction=_build_analyze_blindspots_instruction(),
    description='Identifies uniformly ignored evidence and shared assumptions.',
    output_key='blindspot_analysis',
)

search_inquiry_strategist_agent = Agent(
    name='search_inquiry_strategist',
    model='gemini-2.5-flash',
    instruction=_build_search_inquiry_instruction(),
    description='Generates prioritized inquiry objectives for targeted research.',
    output_key='search_inquiry_plan',
)

qa_agent = Agent(
    name='qa_agent',
    model='gemini-2.5-flash',
    instruction=_build_qa_instruction(),
    description='Applies QA scrutiny and red-team challenges.',
    output_key='qa_notes',
)


# Create the custom workflow agent with conditional logic
root_agent = ThinkRemixWorkflowAgent(
    name='think_remix_v2',
    description=(
        'THINK Remix v2.0: Workflow with evidence registry, persona diversity, '
        'validation gates, conditional branching, parallel execution, and robustness scoring.'
    ),
)

