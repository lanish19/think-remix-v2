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

"""Custom workflow agent for THINK Remix v2.0 with conditional logic."""

from __future__ import annotations

import logging
from typing import AsyncGenerator
from typing import ClassVar
from typing import Optional
from typing import Type

import json

from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.base_agent import BaseAgentState
from google.adk.agents.base_agent_config import BaseAgentConfig
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.parallel_agent import ParallelAgent
from google.adk.events.event import Event
from google.adk.utils.context_utils import Aclosing
from typing_extensions import override

from . import agent
from .config_loader import get_config
from .state_manager import initialize_state_mapping
from .validation import validate_agent_output_by_key

logger = logging.getLogger(__name__)


class ThinkRemixWorkflowState(BaseAgentState):
  """State for ThinkRemixWorkflowAgent."""

  phase: str = 'initialization'
  """Current workflow phase."""
  
  persona_allocator_attempts: int = 0
  """Number of times persona allocator has been called."""
  
  coverage_validator_attempts: int = 0
  """Number of times coverage validator has been called."""


class ThinkRemixWorkflowAgent(BaseAgent):
  """Custom workflow agent implementing conditional logic for THINK Remix v2.0."""

  config_type: ClassVar[Type[BaseAgentConfig]] = BaseAgentConfig
  """The config type for this agent."""
  
  def __init__(self, *args, **kwargs):
    """Initialize workflow agent with configuration."""
    super().__init__(*args, **kwargs)
    self._config = get_config()
  
  @property
  def max_validation_retries(self) -> int:
    """Maximum number of retries for validation failures."""
    return self._config.max_schema_validation_retries

  async def _run_agent_with_validation(
      self,
      agent_instance: BaseAgent,
      ctx: InvocationContext,
      max_retries: Optional[int] = None,
  ) -> AsyncGenerator[Event, None]:
    """Runs an agent and validates its output with retry logic.
    
    Args:
      agent_instance: The agent to run.
      ctx: Invocation context.
      max_retries: Maximum retry attempts (defaults to self.max_validation_retries).
    
    Yields:
      Events from agent execution.
    """
    if max_retries is None:
      max_retries = self.max_validation_retries
    
    retry_count = 0
    output_key = getattr(agent_instance, 'output_key', None)
    
    while retry_count <= max_retries:
      # Run the agent
      async with Aclosing(agent_instance.run_async(ctx)) as agen:
        last_event = None
        async for event in agen:
          yield event
          last_event = event
      
      # If no output key, skip validation
      if not output_key:
        break
      
      # Get the output from state
      agent_output = ctx.state.get(output_key)
      if agent_output is None:
        logger.warning('No output found in state for key %s from agent %s',
                      output_key, agent_instance.name)
        break
      
      # Convert to string if needed
      if isinstance(agent_output, dict):
        import json
        output_text = json.dumps(agent_output)
      elif isinstance(agent_output, str):
        output_text = agent_output
      else:
        output_text = str(agent_output)
      
      # Validate output
      validation_result = validate_agent_output_by_key(
          output_text,
          output_key,
          agent_instance.name,
      )
      
      if validation_result.valid:
        logger.debug('Validation passed for agent %s', agent_instance.name)
        break
      
      # Validation failed
      if retry_count < max_retries:
        retry_count += 1
        logger.warning(
            'Validation failed for agent %s (attempt %d/%d): %s. Retrying...',
            agent_instance.name,
            retry_count,
            max_retries + 1,
            validation_result.error,
        )
        # Add validation error to context for agent to see
        error_context = (
            f'Previous output failed validation: {validation_result.error}. '
            'Please ensure your output matches the required JSON schema exactly.'
        )
        # Store error in state so agent can access it
        ctx.state[f'{output_key}_validation_error'] = error_context
      else:
        logger.error(
            'Validation failed for agent %s after %d attempts: %s. Continuing anyway.',
            agent_instance.name,
            max_retries + 1,
            validation_result.error,
        )
        break

  @override
  async def _run_async_impl(
      self, ctx: InvocationContext
  ) -> AsyncGenerator[Event, None]:
    """Execute the THINK Remix workflow with conditional branching."""
    initialize_state_mapping(ctx.state)
    workflow_state = self._load_agent_state(ctx, ThinkRemixWorkflowState)
    if workflow_state is None:
      workflow_state = ThinkRemixWorkflowState()
      ctx.set_agent_state(self.name, agent_state=workflow_state)
      if ctx.is_resumable:
        yield self._create_agent_state_event(ctx)

    # Phase 1: Question Processing
    async for event in self._run_question_processing_phase(ctx, workflow_state):
      yield event
      if ctx.should_pause_invocation(event):
        return

    # Phase 2: Persona Allocation and Validation Loop
    async for event in self._run_persona_allocation_phase(ctx, workflow_state):
      yield event
      if ctx.should_pause_invocation(event):
        return

    # Phase 3: Dynamic Persona Execution (Parallel)
    async for event in self._run_persona_execution_phase(ctx, workflow_state):
      yield event
      if ctx.should_pause_invocation(event):
        return

    # Phase 4: Analysis and Synthesis
    async for event in self._run_analysis_phase(ctx, workflow_state):
      yield event
      if ctx.should_pause_invocation(event):
        return

    # Phase 5: Targeted Research
    async for event in self._run_research_phase(ctx, workflow_state):
      yield event
      if ctx.should_pause_invocation(event):
        return

    # Phase 6: Adjudication and Case File
    async for event in self._run_adjudication_phase(ctx, workflow_state):
      yield event
      if ctx.should_pause_invocation(event):
        return

    # Phase 7: Coverage Validation Loop
    async for event in self._run_coverage_validation_phase(ctx, workflow_state):
      yield event
      if ctx.should_pause_invocation(event):
        return

    # Phase 8: Final Synthesis
    async for event in self._run_final_phase(ctx, workflow_state):
      yield event
      if ctx.should_pause_invocation(event):
        return

    if ctx.is_resumable:
      ctx.set_agent_state(self.name, end_of_agent=True)
      yield self._create_agent_state_event(ctx)

  async def _run_question_processing_phase(
      self,
      ctx: InvocationContext,
      workflow_state: ThinkRemixWorkflowState,
  ) -> AsyncGenerator[Event, None]:
    """Phase 1: Question audit, analysis, null generation, and initial research."""
    workflow_state.phase = 'question_processing'
    
    # Question Audit Gate
    async for event in self._run_agent_with_validation(
        agent.question_audit_agent, ctx
    ):
      yield event

    # Check audit result and branch
    audit_result = ctx.state.get('question_audit_result')
    if audit_result:
      audit_status = audit_result.get('audit_status', '').lower()
      if audit_status == 'block':
        # Workflow stops - audit gate callback should have handled this
        return
      if audit_status == 'request_clarification':
        # Workflow stops - clarification needed
        return

    # Analyze Question
    async for event in self._run_agent_with_validation(
        agent.analyze_question_agent, ctx
    ):
      yield event

    # Generate Null Hypotheses
    async for event in self._run_agent_with_validation(
        agent.generate_nulls_agent, ctx
    ):
      yield event

    # Gather Insights (comprehensive research)
    async for event in self._run_agent_with_validation(
        agent.gather_insights_agent, ctx
    ):
      yield event

  async def _run_persona_allocation_phase(
      self,
      ctx: InvocationContext,
      workflow_state: ThinkRemixWorkflowState,
  ) -> AsyncGenerator[Event, None]:
    """Phase 2: Persona allocation with validation loop."""
    workflow_state.phase = 'persona_allocation'
    max_attempts = self._config.max_persona_validator_attempts

    while workflow_state.persona_allocator_attempts < max_attempts:
      workflow_state.persona_allocator_attempts += 1
      
      # Run Persona Allocator
      async for event in self._run_agent_with_validation(
          agent.persona_allocator_agent, ctx
      ):
        yield event

      # Run Persona Validator
      async for event in self._run_agent_with_validation(
          agent.persona_validator_agent, ctx
      ):
        yield event

      # Check validation result
      validation_result = ctx.state.get('persona_validation')
      if validation_result:
        validation_status = validation_result.get('validation_status', '').lower()
        if validation_status == 'approved':
          logger.info('Persona validation approved after %d attempts',
                      workflow_state.persona_allocator_attempts)
          break
        elif workflow_state.persona_allocator_attempts >= max_attempts:
          logger.warning('Persona validation failed after %d attempts, proceeding anyway',
                        max_attempts)
          break
        else:
          logger.info('Persona validation failed, retrying allocation (attempt %d/%d)',
                      workflow_state.persona_allocator_attempts, max_attempts)
      else:
        # No validation result, proceed anyway
        logger.warning('No persona validation result found, proceeding')
        break

  async def _run_persona_execution_phase(
      self,
      ctx: InvocationContext,
      workflow_state: ThinkRemixWorkflowState,
  ) -> AsyncGenerator[Event, None]:
    """Phase 3: Dynamically create and execute persona agents in parallel."""
    workflow_state.phase = 'persona_execution'
    
    # Get persona allocation result
    allocation_result = ctx.state.get('persona_allocation')
    if not allocation_result or 'personas' not in allocation_result:
      logger.error('No persona allocation found, cannot execute personas')
      return

    personas = allocation_result['personas']
    if not isinstance(personas, list) or len(personas) == 0:
      logger.error('Invalid personas list in allocation result')
      return

    # Get CER facts for persona agents
    cer_registry = ctx.state.get('cer_registry', [])
    
    # Dynamically create persona agents
    persona_agents = []
    for persona_config in personas:
      try:
        persona_agent = agent.create_persona_agent(persona_config, cer_registry)
        persona_agents.append(persona_agent)
      except Exception as e:
        logger.error('Failed to create persona agent for %s: %s',
                     persona_config.get('id', 'unknown'), e)
        continue

    if not persona_agents:
      logger.error('No persona agents created successfully')
      return

    logger.info('Created %d persona agents, executing in parallel', len(persona_agents))

    # Execute personas in parallel using ParallelAgent
    parallel_persona_agent = ParallelAgent(
        name='parallel_persona_execution',
        sub_agents=persona_agents,
    )

    async with Aclosing(parallel_persona_agent.run_async(ctx)) as agen:
      async for event in agen:
        yield event

  async def _run_analysis_phase(
      self,
      ctx: InvocationContext,
      workflow_state: ThinkRemixWorkflowState,
  ) -> AsyncGenerator[Event, None]:
    """Phase 4: Evidence consistency, synthesis, adversarial, disagreement analysis."""
    workflow_state.phase = 'analysis'
    
    # Evidence Consistency Enforcer
    async for event in self._run_agent_with_validation(
        agent.evidence_consistency_enforcer_agent, ctx
    ):
      yield event

    # Run Synthesis and Adversarial in parallel
    # ParallelAgent handles branching internally, so we can use the same ctx
    # Note: Validation happens after parallel execution completes
    parallel_analysis_agent = ParallelAgent(
        name='parallel_synthesis_adversarial',
        sub_agents=[
            agent.synthesis_agent,
            agent.adversarial_injector_agent,
        ],
    )

    async with Aclosing(parallel_analysis_agent.run_async(ctx)) as agen:
      async for event in agen:
        yield event
    
    # Validate parallel agent outputs
    for sub_agent in [agent.synthesis_agent, agent.adversarial_injector_agent]:
      if hasattr(sub_agent, 'output_key'):
        output = ctx.state.get(sub_agent.output_key)
        if output:
          output_text = json.dumps(output) if isinstance(output, dict) else str(output)
          validation_result = validate_agent_output_by_key(
              output_text, sub_agent.output_key, sub_agent.name
          )
          if not validation_result.valid:
            logger.warning('Validation failed for parallel agent %s: %s',
                          sub_agent.name, validation_result.error)

    # Analyze Disagreement
    async for event in self._run_agent_with_validation(
        agent.analyze_disagreement_agent, ctx
    ):
      yield event

    # Analyze Blindspots
    async for event in self._run_agent_with_validation(
        agent.analyze_blindspots_agent, ctx
    ):
      yield event

  async def _run_research_phase(
      self,
      ctx: InvocationContext,
      workflow_state: ThinkRemixWorkflowState,
  ) -> AsyncGenerator[Event, None]:
    """Phase 5: Search inquiry strategist and targeted research."""
    workflow_state.phase = 'research'
    
    # Search Inquiry Strategist
    async for event in self._run_agent_with_validation(
        agent.search_inquiry_strategist_agent, ctx
    ):
      yield event

    # Conduct Research (dual-track)
    async for event in self._run_agent_with_validation(
        agent.conduct_research_agent, ctx
    ):
      yield event

  async def _run_adjudication_phase(
      self,
      ctx: InvocationContext,
      workflow_state: ThinkRemixWorkflowState,
  ) -> AsyncGenerator[Event, None]:
    """Phase 6: Evidence adjudication, null adjudication, and case file creation."""
    workflow_state.phase = 'adjudication'
    
    # Run Evidence Adjudicator and Null Adjudicator in parallel
    parallel_adjudication_agent = ParallelAgent(
        name='parallel_adjudication',
        sub_agents=[
            agent.evidence_adjudicator_agent,
            agent.null_adjudicator_agent,
        ],
    )

    async with Aclosing(parallel_adjudication_agent.run_async(ctx)) as agen:
      async for event in agen:
        yield event
    
    # Validate parallel agent outputs
    for sub_agent in [agent.evidence_adjudicator_agent, agent.null_adjudicator_agent]:
      if hasattr(sub_agent, 'output_key'):
        output = ctx.state.get(sub_agent.output_key)
        if output:
          output_text = json.dumps(output) if isinstance(output, dict) else str(output)
          validation_result = validate_agent_output_by_key(
              output_text, sub_agent.output_key, sub_agent.name
          )
          if not validation_result.valid:
            logger.warning('Validation failed for parallel agent %s: %s',
                          sub_agent.name, validation_result.error)

    # Case File
    async for event in self._run_agent_with_validation(
        agent.case_file_agent, ctx
    ):
      yield event

  async def _run_coverage_validation_phase(
      self,
      ctx: InvocationContext,
      workflow_state: ThinkRemixWorkflowState,
  ) -> AsyncGenerator[Event, None]:
    """Phase 7: Coverage validation loop (regenerate case file if needed)."""
    workflow_state.phase = 'coverage_validation'
    max_attempts = self._config.max_coverage_validator_attempts

    while workflow_state.coverage_validator_attempts < max_attempts:
      workflow_state.coverage_validator_attempts += 1
      
      # Run Coverage Validator
      async for event in self._run_agent_with_validation(
          agent.coverage_validator_agent, ctx
      ):
        yield event

      # Check validation result
      validation_result = ctx.state.get('coverage_validation')
      if validation_result:
        passed = validation_result.get('passed', False)
        if passed:
          logger.info('Coverage validation passed after %d attempts',
                      workflow_state.coverage_validator_attempts)
          break
        elif workflow_state.coverage_validator_attempts >= max_attempts:
          logger.warning('Coverage validation failed after %d attempts, proceeding anyway',
                        max_attempts)
          break
        else:
          logger.info('Coverage validation failed, regenerating case file (attempt %d/%d)',
                      workflow_state.coverage_validator_attempts, max_attempts)
          # Regenerate case file
          async for event in self._run_agent_with_validation(
              agent.case_file_agent, ctx
          ):
            yield event
      else:
        # No validation result, proceed anyway
        logger.warning('No coverage validation result found, proceeding')
        break

  async def _run_final_phase(
      self,
      ctx: InvocationContext,
      workflow_state: ThinkRemixWorkflowState,
  ) -> AsyncGenerator[Event, None]:
    """Phase 8: Robustness calculation, QA, and final arbiter."""
    workflow_state.phase = 'final'
    
    # Robustness Calculator
    async for event in self._run_agent_with_validation(
        agent.robustness_calculator_agent, ctx
    ):
      yield event

    # QA Agent
    async for event in self._run_agent_with_validation(
        agent.qa_agent, ctx
    ):
      yield event

    # Final Arbiter
    async for event in self._run_agent_with_validation(
        agent.final_arbiter_agent, ctx
    ):
      yield event

  @override
  async def _run_live_impl(
      self, ctx: InvocationContext
  ) -> AsyncGenerator[Event, None]:
    """Live mode not supported for custom workflow."""
    raise NotImplementedError('Live mode not supported for ThinkRemixWorkflowAgent.')
