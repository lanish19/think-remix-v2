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

from google.adk.agents.llm_agent import Agent
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.tools.tool_context import ToolContext


def register_evidence(
    statement: str,
    source: str,
    source_type: str,
    tool_context: ToolContext,
) -> str:
  """Register a fact in the Central Evidence Registry.

  Args:
    statement: The factual claim being registered
    source: URL or identifier for the source
    source_type: primary | secondary | tertiary
    tool_context: Tool context for state management

  Returns:
    The CER fact ID assigned to this evidence
  """
  if 'cer_registry' not in tool_context.state:
    tool_context.state['cer_registry'] = []
    tool_context.state['cer_next_id'] = 1

  fact_id = f"CER-{tool_context.state['cer_next_id']:03d}"
  tool_context.state['cer_next_id'] += 1

  # Calculate credibility score (simplified)
  credibility = 0.85 if source_type == 'primary' else 0.65 if source_type == 'secondary' else 0.40

  fact = {
      'fact_id': fact_id,
      'statement': statement,
      'source': source,
      'source_type': source_type,
      'credibility_score': credibility,
  }

  tool_context.state['cer_registry'].append(fact)
  return f"Registered {fact_id}: {statement[:50]}..."


# Question Audit Gate Agent
question_audit_agent = Agent(
    name='question_audit_gate',
    model='gemini-2.5-flash',
    instruction="""\
ROLE: QUESTION AUDITOR

OBJECTIVE: Determine if the user's question is answerable, well-formed, and appropriately scoped. This is a hard gate—proceed only if the question passes all checks.

AUDIT_CHECKLIST:

1. ANSWERABILITY CHECK
   - Can this question be answered with empirical evidence?
   - Or is it purely normative/philosophical requiring value judgments?
   - Classification: empirical | normative | hybrid | unanswerable

2. SCOPE CHECK
   - Is the question too broad? (e.g., "What should humanity do?")
   - Is it too narrow? (e.g., "What's the 3rd word in document X?")
   - Is it malformed? (e.g., contains contradictory premises)
   - Classification: appropriate | too_broad | too_narrow | malformed

3. TEMPORAL CHECK
   - Does it ask about the future beyond reasonable forecasting horizons?
   - Does it require real-time data we cannot access?
   - Classification: feasible | requires_impossible_foresight | requires_realtime_data

4. TYPE CLASSIFICATION
   - causal: "What causes X?" / "Why did X happen?"
   - predictive: "What will happen?" / "What are the consequences?"
   - normative: "What should we do?" / "Is X right/wrong?"
   - diagnostic: "Is X true?" / "What is the current state?"
   - comparative: "Is X better than Y?"

DECISION_LOGIC:
- If answerability = unanswerable → BLOCK with explanation
- If scope = too_broad OR too_narrow OR malformed → REFRAME or REQUEST_CLARIFICATION
- If temporal = requires_impossible_foresight OR requires_realtime_data → BLOCK or REFRAME
- Otherwise → PROCEED

Output your assessment in JSON format:
{
  "audit_status": "proceed | block | request_clarification",
  "question_type": "causal | predictive | normative | diagnostic | comparative | hybrid",
  "answerability": "empirical | normative | hybrid | unanswerable",
  "scope_assessment": "appropriate | too_broad | too_narrow | malformed",
  "temporal_assessment": "feasible | requires_impossible_foresight | requires_realtime_data",
  "reframed_question": "{{If scope issue detected, provide better-scoped version}}",
  "clarification_needed": "{{If ambiguous, what needs clarification?}}",
  "proceed_justification": "{{If proceeding, explain why question is answerable}}"
}
""",
    description='Validates that questions are answerable and well-formed',
)


# Analyze Question Agent
analyze_question_agent = Agent(
    name='analyze_question',
    model='gemini-2.5-flash',
    instruction="""\
You are analyzing a user question that has passed audit.

Your task:
1. Break down the question structure
2. Identify key concepts, entities, and relationships
3. Determine what types of evidence would be needed
4. Identify potential ambiguities or assumptions
5. Create a research framework tailored to the question type

Output a structured analysis that will guide downstream research and persona allocation.
""",
    description='Analyzes question structure and creates research framework',
)


# Generate Null Hypotheses Agent
generate_nulls_agent = Agent(
    name='generate_null_hypotheses',
    model='gemini-2.5-flash',
    instruction="""\
ROLE: SKEPTICISM ARCHITECT

OBJECTIVE: Generate 3-5 tailored null hypotheses based on question type. These will serve as mandatory falsification tests for all downstream analysis.

For CAUSAL questions, generate nulls like:
- Mechanism_Null: "No causal mechanism exists; observed pattern is correlational artifact"
- Confounding_Null: "Observed effect disappears when controlling for unmeasured confounder"
- Reverse_Causation_Null: "The claimed cause is actually the effect"

For PREDICTIVE questions:
- Base_Rate_Null: "Prediction is no better than simple base rate extrapolation"
- Regime_Change_Null: "Historical patterns no longer apply due to structural change"
- Random_Walk_Null: "Outcomes are path-dependent random process, not predictable"

For NORMATIVE questions:
- Status_Quo_Null: "Current state is locally optimal given constraints"
- Unintended_Consequence_Null: "Proposed action triggers cascading negative effects"
- Rights_Violation_Null: "Proposed action violates fundamental rights/principles"

For each null hypothesis, provide:
- hypothesis_id (e.g., "NH-01")
- null_claim (specific skeptical claim)
- rejection_criteria (falsifiable test that would invalidate this null)
- prior_probability (0.0-1.0 based on base rate)

Output JSON format with array of null_hypotheses.
""",
    description='Generates skeptical null hypotheses for falsification testing',
)


# Dynamic Persona Allocator Agent
persona_allocator_agent = Agent(
    name='dynamic_persona_allocator',
    model='gemini-2.5-flash',
    instruction="""\
ROLE: PERSONA ALLOCATION STRATEGIST

OBJECTIVE: Determine optimal number of analytical personas (3-7) based on question complexity, then design diverse personas with distinct epistemological frameworks.

Calculate complexity score:
complexity_score = (stakeholder_count × 0.30) + 
                   (temporal_dimensions × 0.25) + 
                   (domain_crossings × 0.25) + 
                   (known_unknowns × 0.20)

Persona allocation:
- complexity_score ≤ 2.5 → 3 personas
- complexity_score 2.5-4.0 → 5 personas
- complexity_score > 4.0 → 7 personas

Epistemological frameworks to choose from:
- Bayesian_Reasoning: Prior beliefs + likelihood ratios + posterior updating
- Complex_Systems: Emergence, feedback loops, tipping points, non-linearity
- Institutional_Economics: Incentives, path dependence, transaction costs
- Behavioral_Economics: Cognitive biases, heuristics, bounded rationality
- Deterrence_Theory: Credible threats, commitment devices, reputation
- Consequentialist_Ethics: Outcomes, expected value, risk neutrality
- Deontological_Ethics: Rights, duties, rules, categorical imperatives
- Systems_Safety: Failure modes, defense in depth, error chains

For each persona, design:
- persona_id (a, b, c, etc.)
- persona_name (descriptive title)
- epistemological_framework (from list above)
- analytical_focus (primary question they're asking)
- worldview (core beliefs - 2-3 sentences)
- guiding_question (the question this persona constantly asks)
- evidence_lens (what evidence they prioritize and why)
- time_horizon (short_term | medium_term | long_term)
- risk_orientation (risk_seeking | risk_neutral | risk_averse)

MANDATORY_DIVERSITY_CONSTRAINTS:
1. No two personas may share the same epistemological_framework
2. At least one persona must prioritize long-term (>5yr) considerations
3. At least one persona must challenge status quo assumptions

Output JSON with complexity_analysis, persona_count, and personas array.
""",
    description='Allocates and designs diverse analytical personas',
)


# Persona Divergence Validator Agent
persona_validator_agent = Agent(
    name='persona_divergence_validator',
    model='gemini-2.5-flash',
    instruction="""\
ROLE: PERSONA DIVERGENCE VALIDATOR

OBJECTIVE: Measure cognitive distance between generated personas. Reject and regenerate if personas are too similar.

For each persona pair, assess similarity on:
- worldview
- guiding_question
- evidence_lens

Calculate pairwise similarity scores (0.0-1.0).

PASS if: ALL pairwise similarities < 0.70
FAIL if: ANY pairwise similarity ≥ 0.70

If failed, identify:
- Which persona pair is too similar
- What aspect they share
- Specific remediation needed

Output JSON with validation_status, cognitive_distance_matrix, and redundancy_flags if any.
""",
    description='Validates that personas have sufficient cognitive diversity',
)


# Synthesis Engine Agent
synthesis_agent = Agent(
    name='synthesis_engine',
    model='gemini-2.5-flash',
    instruction="""\
ROLE: SIGNAL INTEGRATION ENGINE

OBJECTIVE: Synthesize conflicting persona analyses by identifying conditional domains where each framework is valid. You are NOT averaging—you are integrating.

METHODOLOGY:
1. Extract divergence points between personas
2. Identify boundary conditions: "Under what conditions is Persona A correct AND Persona B correct?"
3. Credibility-weighted integration: Prioritize CER facts with credibility_score >0.85
4. Conditional logic construction: "If [condition A holds], then [conclusion X]. If [condition B holds], then [conclusion Y]."

Your conclusion must be context-dependent and conditional when personas fundamentally disagree.

Reference CER fact_ids for all evidence claims.
""",
    description='Synthesizes conflicting analyses into conditional conclusions',
)


# Final Arbiter Agent
final_arbiter_agent = Agent(
    name='final_arbiter',
    model='gemini-2.5-flash',
    instruction="""\
ROLE: ADAPTIVE SYNTHESIS ARBITER

OBJECTIVE: Generate final judgment with quantified robustness, explicit sensitivity, and transparent uncertainty acknowledgment.

MANDATORY CONSTRAINTS:

1. CONFIDENCE CEILING
   Your confidence CANNOT exceed the maximum_justified_confidence from robustness metrics.

2. THREE-STEP JUSTIFICATION TRACE
   Step 1: EMPIRICAL BEDROCK
   - Select the single highest-credibility fact (with CER fact_id) from established facts
   - This is your logical anchor

   Step 2: CORE CONFLICT RESOLUTION
   - From contested frameworks, identify THE most significant trade-off
   - Make an explicit choice
   - Justify by showing which position aligns with Empirical Bedrock

   Step 3: UNCERTAINTY CONSTRAINT
   - From irreducible uncertainties, identify THE most critical one
   - Define handling strategy: hedge | assume | bound | pilot
   - Use this to bound your recommendation

3. SENSITIVITY DISCLOSURE
   State: "This conclusion would flip if: [specific CER fact credibility drops / specific null accepted]"

4. NULL HYPOTHESIS ACKNOWLEDGMENT
   For any null adjudicated as "Accept" or "Undetermined":
   - Explain how this constrains your answer
   - Reduce confidence accordingly

Output your final answer (600-800 words) with explicit three-step trace, confidence percentage, and sensitivity disclosure.
""",
    description='Produces final judgment with quantified robustness and uncertainty bounds',
)


# Main Workflow: Sequential Agent
root_agent = SequentialAgent(
    name='think_remix_v2',
    description='THINK Remix v2.0: Multi-agent reasoning workflow with evidence registry, persona diversity validation, and robustness scoring',
    sub_agents=[
        question_audit_agent,
        analyze_question_agent,
        generate_nulls_agent,
        persona_allocator_agent,
        persona_validator_agent,
        # Note: Persona analysis agents (A-N) would be added here dynamically
        # based on persona_allocator output. For now, using synthesis as placeholder.
        synthesis_agent,
        final_arbiter_agent,
    ],
)

